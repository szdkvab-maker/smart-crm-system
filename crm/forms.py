from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.files.base import ContentFile
from django.core.exceptions import ValidationError
from django.db import transaction
from PIL import Image, ImageOps
from io import BytesIO
from django.contrib.auth.models import User
from .models import Client, ClientPortalProfile, Deal, PortalRequest, RegistrationRequest, Task


class LimitedImageField(forms.ImageField):
    def to_python(self, data):
        if data and getattr(data, 'size', 0) > 5 * 1024 * 1024:
            raise forms.ValidationError('Максимальный размер — 5 МБ.')
        return super().to_python(data)


class ClientForm(forms.ModelForm):
    photo = LimitedImageField(
        required=False, label='Фото или логотип',
        widget=forms.FileInput(attrs={'accept': 'image/jpeg,image/png,image/webp'}),
    )
    class Meta:
        model = Client
        fields = ['kind', 'name', 'photo', 'company', 'position', 'industry', 'contact_person',
                  'email', 'phone', 'website', 'city', 'notes']
        widgets = {
            'photo': forms.FileInput(attrs={'accept': 'image/jpeg,image/png,image/webp'}),
            'notes': forms.Textarea(attrs={'rows': 4}),
        }

    remove_photo = forms.BooleanField(required=False, label='Удалить текущее фото')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['photo'].help_text = 'JPG, PNG или WebP, до 5 МБ и 16 мегапикселей. Фото необязательно.'
        self.fields['name'].widget.attrs['autofocus'] = True
        self.fields['phone'].widget.attrs.update({'type': 'tel', 'placeholder': '+7 700 123 45 67'})
        if not self.instance.photo:
            self.fields.pop('remove_photo', None)

    def clean_photo(self):
        photo = self.cleaned_data.get('photo')
        if not photo or not hasattr(photo, 'image'):
            return photo
        if photo.size > 5 * 1024 * 1024:
            raise forms.ValidationError('Максимальный размер — 5 МБ.')
        if photo.image.format not in ('JPEG', 'PNG', 'WEBP'):
            raise forms.ValidationError('Используйте JPG, PNG или WebP.')
        if photo.image.width * photo.image.height > 16_000_000:
            raise forms.ValidationError('Изображение слишком большое: максимум 16 мегапикселей.')
        try:
            photo.seek(0)
            with Image.open(photo) as source:
                oriented = ImageOps.exif_transpose(source).convert('RGBA')
                picture = Image.new('RGB', oriented.size, 'white')
                picture.paste(oriented, mask=oriented.getchannel('A'))
                picture.thumbnail((1000, 1000))
                output = BytesIO()
                picture.save(output, format='JPEG', quality=88)
            return ContentFile(output.getvalue(), name='photo.jpg')
        except (OSError, ValueError):
            raise forms.ValidationError('Не удалось прочитать изображение.')

    def clean(self):
        data = super().clean()
        # Existing clients keep all legacy fields; switching type never silently erases data.
        if data.get('remove_photo'):
            if self.files.get('photo'):
                self.add_error('photo', 'Выберите загрузку или удаление фото, не оба действия.')
            else:
                data['photo'] = False
        return data


class DealForm(forms.ModelForm):
    expected_close_date = forms.DateField(
        label='Плановая дата закрытия',
        required=False,
        input_formats=['%d.%m.%Y', '%Y-%m-%d'],
        widget=forms.DateInput(
            format='%d.%m.%Y',
            attrs={
                'placeholder': 'ДД.ММ.ГГГГ',
                'inputmode': 'numeric',
                'data-date-mask': 'ddmmyyyy',
            },
        ),
    )

    class Meta:
        model = Deal
        fields = ['title', 'client', 'amount', 'status', 'expected_close_date']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound and not self.instance.pk:
            self.initial['amount'] = ''

    def clean_amount(self):
        amount = self.cleaned_data['amount']
        if amount < 0:
            raise forms.ValidationError('Сумма не может быть отрицательной.')
        return amount


class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ['title', 'client', 'description', 'due_date', 'priority', 'is_completed']
        widgets = {'due_date': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'})}


class ClientRegistrationForm(forms.Form):
    username = forms.CharField(label='Имя пользователя', max_length=150)
    email = forms.EmailField(label='Email')
    full_name = forms.CharField(label='Ваше имя', max_length=150)
    company = forms.CharField(label='Компания', max_length=150, required=False)
    phone = forms.CharField(label='Телефон', max_length=30, required=False)
    password1 = forms.CharField(label='Пароль', widget=forms.PasswordInput)
    password2 = forms.CharField(label='Повторите пароль', widget=forms.PasswordInput)

    def clean_username(self):
        username = self.cleaned_data['username']
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError('Это имя пользователя уже занято.')
        return username

    def clean_email(self):
        email = self.cleaned_data['email']
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('Этот email уже зарегистрирован.')
        return email

    def clean(self):
        data = super().clean()
        password = data.get('password1')
        if password and password != data.get('password2'):
            self.add_error('password2', 'Пароли не совпадают.')
        elif password:
            try:
                validate_password(password, user=User(username=data.get('username', '')))
            except ValidationError as error:
                self.add_error('password1', error)
        return data

    @transaction.atomic
    def save(self):
        user = User.objects.create_user(
            username=self.cleaned_data['username'],
            email=self.cleaned_data['email'],
            password=self.cleaned_data['password1'],
            is_active=False,
        )
        ClientPortalProfile.objects.create(user=user)
        RegistrationRequest.objects.create(
            user=user,
            full_name=self.cleaned_data['full_name'],
            company=self.cleaned_data['company'],
            phone=self.cleaned_data['phone'],
        )
        return user


class PortalDealRequestForm(forms.ModelForm):
    class Meta:
        model = PortalRequest
        fields = ['title', 'description', 'amount']
        widgets = {'description': forms.Textarea(attrs={'rows': 3})}

    def clean_amount(self):
        amount = self.cleaned_data['amount']
        if amount is not None and amount < 0:
            raise forms.ValidationError('Сумма не может быть отрицательной.')
        return amount


class PortalTaskRequestForm(forms.ModelForm):
    class Meta:
        model = PortalRequest
        fields = ['title', 'description', 'due_date']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'due_date': forms.DateInput(attrs={'type': 'date'}),
        }
