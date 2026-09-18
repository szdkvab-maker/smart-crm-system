from django import forms
from .models import Client, Deal, Task


class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = ['name', 'company', 'email', 'phone', 'notes']


class DealForm(forms.ModelForm):
    class Meta:
        model = Deal
        fields = ['title', 'client', 'amount', 'status', 'expected_close_date']
        widgets = {'expected_close_date': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'})}

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
