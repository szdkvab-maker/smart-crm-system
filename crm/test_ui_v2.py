from datetime import timedelta
from decimal import Decimal
from io import BytesIO
from tempfile import TemporaryDirectory

from PIL import Image
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from .models import Client, Deal, Task
from .templatetags.crm_ui import money


def picture():
    buf = BytesIO()
    Image.new('RGB', (40, 40), '#9988ff').save(buf, format='PNG')
    return SimpleUploadedFile('portrait.png', buf.getvalue(), content_type='image/png')


class ClientCardTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('card-owner', password='Test-only-789!')
        self.other = User.objects.create_user('other-owner')
        self.client.force_login(self.user)
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.settings_override = override_settings(MEDIA_ROOT=self.directory.name)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)

    def add_client(self, **extra):
        payload = {'kind': 'person', 'name': 'Алия Тестовая', **extra}
        response = self.client.post('/clients/new/', payload)
        self.assertEqual(response.status_code, 302)
        return Client.objects.get(name=payload['name'])

    def test_company_creation_and_detail(self):
        company = self.add_client(kind='company', name='Тестовая студия',
                                  industry='Дизайн', contact_person='Алия',
                                  website='https://example.com', city='Астана')
        for path in [f'/clients/{company.pk}/', f'/clients/{company.pk}/?panel=1']:
            response = self.client.get(path)
            self.assertContains(response, 'Тестовая студия')
            self.assertContains(response, 'Дизайн')
            self.assertContains(response, 'Алия')
        self.assertContains(self.client.get('/clients/'), 'Тестовая студия')

    def test_photo_is_reencoded_and_owner_scoped(self):
        obj = self.add_client(photo=picture())
        self.assertTrue(obj.photo.name.endswith('.jpg'))
        with Image.open(obj.photo.path) as actual:
            self.assertEqual(actual.format, 'JPEG')
        response = self.client.get(f'/clients/{obj.pk}/photo/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Cache-Control'], 'private, no-store')
        response.close()
        self.client.force_login(self.other)
        for path in [f'/clients/{obj.pk}/photo/', f'/clients/{obj.pk}/', f'/clients/{obj.pk}/?panel=1']:
            self.assertEqual(self.client.get(path).status_code, 404)
        self.client.logout()
        self.assertEqual(self.client.get(f'/clients/{obj.pk}/photo/').status_code, 302)

    def test_invalid_and_large_photos(self):
        invalid = SimpleUploadedFile('bad.jpg', b'<svg onload="alert(1)">', content_type='image/jpeg')
        response = self.client.post('/clients/new/', {'kind': 'person', 'name': 'Bad', 'photo': invalid})
        self.assertEqual(response.status_code, 200)
        self.assertIn('photo', response.context['form'].errors)
        large = SimpleUploadedFile('large.png', b'x' * (5 * 1024 * 1024 + 1), content_type='image/png')
        response = self.client.post('/clients/new/', {'kind': 'person', 'name': 'Large', 'photo': large})
        self.assertContains(response, 'Максимальный размер')
        self.assertEqual(Client.objects.count(), 0)

    def test_photo_preserved_replaced_and_removed(self):
        obj = self.add_client(photo=picture())
        original = obj.photo.name
        data = {'kind': 'person', 'name': obj.name, 'notes': 'Заметка'}
        self.client.post(f'/clients/{obj.pk}/edit/', data)
        obj.refresh_from_db()
        self.assertEqual(obj.photo.name, original)
        self.client.post(f'/clients/{obj.pk}/edit/', {**data, 'photo': picture()})
        obj.refresh_from_db()
        self.assertNotEqual(obj.photo.name, original)
        self.client.post(f'/clients/{obj.pk}/edit/', {**data, 'remove_photo': 'on'})
        obj.refresh_from_db()
        self.assertFalse(obj.photo)
        self.assertEqual(self.client.get(f'/clients/{obj.pk}/photo/').status_code, 404)

    def test_missing_photo_file_returns_404(self):
        obj = self.add_client()
        obj.photo = 'clients/missing.jpg'
        obj.save()
        self.assertEqual(self.client.get(f'/clients/{obj.pk}/photo/').status_code, 404)

    def test_filters_sorting_pagination_and_table(self):
        for n in range(14):
            Client.objects.create(owner=self.user, name=f'Person {n:02}')
        company = self.add_client(kind='company', name='Company')
        Client.objects.create(owner=self.other, name='SECRET')
        first = self.client.get('/clients/?sort=name')
        self.assertEqual(len(first.context['objects']), 12)
        self.assertEqual(first.context['objects'][0], company)
        self.assertNotContains(first, 'SECRET')
        self.assertEqual(len(self.client.get('/clients/?page=2').context['objects']), 3)
        self.assertEqual(len(self.client.get('/clients/?type=company').context['objects']), 1)
        self.assertContains(self.client.get('/clients/?mode=table&type=company'), '<table>')
        self.assertEqual(self.client.get('/clients/?page=nonsense').status_code, 200)

    def test_dashboard_onboarding_and_real_totals(self):
        self.assertContains(self.client.get('/'), 'Большие дела начинаются')
        obj = self.add_client()
        Deal.objects.create(owner=self.user, client=obj, title='Success', amount='50000', status='won')
        Deal.objects.create(owner=self.other, client=obj, title='Hidden', amount='9000', status='won')
        Task.objects.create(owner=self.user, title='Call', due_date=timezone.localdate())
        response = self.client.get('/')
        self.assertNotContains(response, 'Большие дела начинаются')
        self.assertContains(response, '50 000 ₸')
        self.assertEqual(response.context['won_count'], 1)
        self.assertEqual(response.context['today_count'], 1)
        panel = self.client.get(f'/clients/{obj.pk}/')
        self.assertNotContains(panel, 'Hidden')

    def test_periods_and_active_deals(self):
        obj = self.add_client()
        for status in ['new', 'in_progress', 'won', 'lost']:
            Deal.objects.create(owner=self.user, client=obj, title=status, status=status)
        self.assertEqual(len(self.client.get('/deals/?status=active').context['objects']), 2)
        today = timezone.localdate()
        for days in [-1, 0, 3, 8]:
            Task.objects.create(owner=self.user, title=str(days), due_date=today + timedelta(days=days))
        self.assertEqual(len(self.client.get('/tasks/?period=today').context['objects']), 1)
        self.assertEqual(len(self.client.get('/tasks/?period=overdue').context['objects']), 1)
        self.assertEqual(len(self.client.get('/tasks/?period=week').context['objects']), 2)

    def test_untrusted_notes_are_escaped(self):
        obj = self.add_client(notes='<script>alert(1)</script>')
        response = self.client.get(f'/clients/{obj.pk}/?panel=1')
        self.assertNotContains(response, '<script>alert(1)</script>')
        self.assertContains(response, '&lt;script&gt;')

    def test_currency_formatting(self):
        self.assertEqual(money(50000), '50 000 ₸')
        self.assertEqual(money(Decimal('50000.25')), '50 000,25 ₸')
        self.assertEqual(money(0), '0 ₸')


class UpgradeTests(TransactionTestCase):
    def test_v1_data_survives_migration(self):
        executor = MigrationExecutor(connection)
        executor.migrate([('crm', '0001_initial')])
        old = executor.loader.project_state([('crm', '0001_initial')]).apps
        user = old.get_model('auth', 'User').objects.create(username='legacy')
        customer = old.get_model('crm', 'Client').objects.create(owner_id=user.pk, name='Старый клиент', notes='Сохранить')
        deal = old.get_model('crm', 'Deal').objects.create(owner_id=user.pk, client_id=customer.pk, title='Старая сделка', amount='15000')
        task = old.get_model('crm', 'Task').objects.create(owner_id=user.pk, client_id=customer.pk, title='Старая задача')
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        actual = Client.objects.get(pk=customer.pk)
        self.assertEqual(actual.name, 'Старый клиент')
        self.assertEqual(actual.notes, 'Сохранить')
        self.assertEqual(actual.kind, 'person')
        self.assertFalse(actual.photo)
        self.assertEqual(Deal.objects.get(pk=deal.pk).client_id, customer.pk)
        self.assertEqual(Task.objects.get(pk=task.pk).client_id, customer.pk)
