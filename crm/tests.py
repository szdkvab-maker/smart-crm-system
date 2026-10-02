from decimal import Decimal
from django.contrib.auth.models import User
from django.test import Client as Browser, TestCase
from .models import Client, ClientPortalProfile, Deal, PortalRequest, RegistrationRequest, Task


class CRMTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('adlet', password='Test-password-42')
        self.other = User.objects.create_user('other', password='Test-password-42')
        self.own = Client.objects.create(owner=self.user, name='Local client')
        self.foreign = Client.objects.create(owner=self.other, name='Private client')
        self.client.force_login(self.user)

    def test_login_required(self):
        self.client.logout()
        for path in ['/', '/clients/', '/deals/', '/tasks/']:
            self.assertEqual(self.client.get(path).status_code, 302)

    def test_all_pages_render(self):
        for path in ['/', '/clients/', '/deals/', '/tasks/', '/clients/new/', '/deals/new/', '/tasks/new/']:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)

    def test_new_deal_amount_starts_empty(self):
        response = self.client.get('/deals/new/')
        self.assertEqual(response.context['form']['amount'].value(), '')

    def test_client_crud(self):
        self.assertEqual(self.client.post('/clients/new/', {'name': 'New', 'kind': 'person'}).status_code, 302)
        obj = Client.objects.get(name='New')
        self.assertEqual(obj.owner, self.user)
        self.client.post(f'/clients/{obj.pk}/edit/', {'name': 'Updated', 'kind': 'person'})
        obj.refresh_from_db()
        self.assertEqual(obj.name, 'Updated')
        self.client.get(f'/clients/{obj.pk}/delete/')
        self.assertTrue(Client.objects.filter(pk=obj.pk).exists())
        self.client.post(f'/clients/{obj.pk}/delete/')
        self.assertFalse(Client.objects.filter(pk=obj.pk).exists())

    def test_foreign_objects_inaccessible(self):
        objects = {'clients': self.foreign,
            'deals': Deal.objects.create(owner=self.other, client=self.foreign, title='Secret'),
            'tasks': Task.objects.create(owner=self.other, title='Secret')}
        for kind, obj in objects.items():
            for action in ['edit', 'delete']:
                self.assertEqual(self.client.get(f'/{kind}/{obj.pk}/{action}/').status_code, 404)
                self.assertEqual(self.client.post(f'/{kind}/{obj.pk}/{action}/', {}).status_code, 404)
        self.assertNotContains(self.client.get('/clients/'), 'Private client')

    def test_foreign_client_rejected(self):
        for kind, data in [('deals', {'title': 'Test', 'amount': '10', 'status': 'new'}), ('tasks', {'title': 'Test', 'priority': 'low'})]:
            data['client'] = self.foreign.pk
            self.assertEqual(self.client.post(f'/{kind}/new/', data).status_code, 200)
        self.assertEqual(Deal.objects.count(), 0)
        self.assertEqual(Task.objects.count(), 0)

    def test_deal_lifecycle(self):
        data = {'client': self.own.pk, 'title': 'Sale', 'amount': '123.45', 'status': 'new'}
        self.assertEqual(self.client.post('/deals/new/', data).status_code, 302)
        obj = Deal.objects.get()
        data['status'] = 'won'
        self.client.post(f'/deals/{obj.pk}/edit/', data)
        self.assertEqual(self.client.get('/').context['revenue'], Decimal('123.45'))
        self.assertContains(self.client.get('/deals/?status=won'), 'Sale')
        self.assertNotContains(self.client.get('/deals/?status=lost'), 'Sale')
        self.client.post(f'/deals/{obj.pk}/delete/')
        self.assertFalse(Deal.objects.exists())

    def test_deal_date_uses_day_month_year(self):
        deal = Deal.objects.create(
            owner=self.user, client=self.own, title='Dated deal',
            expected_close_date='2026-10-02',
        )
        response = self.client.get(f'/deals/{deal.pk}/edit/')
        self.assertContains(response, 'name="expected_close_date" value="02.10.2026"')
        self.assertEqual(response.context['form'].fields['expected_close_date'].widget.input_type, 'text')

        self.client.post(f'/deals/{deal.pk}/edit/', {
            'client': self.own.pk, 'title': 'Dated deal', 'amount': '0', 'status': 'new',
            'expected_close_date': '03.10.2026',
        })
        deal.refresh_from_db()
        self.assertEqual(deal.expected_close_date.isoformat(), '2026-10-03')

    def test_task_lifecycle(self):
        data = {'title': 'Call', 'priority': 'high', 'due_date': '2026-10-01'}
        self.assertEqual(self.client.post('/tasks/new/', data).status_code, 302)
        obj = Task.objects.get()
        data['is_completed'] = 'on'
        self.client.post(f'/tasks/{obj.pk}/edit/', data)
        obj.refresh_from_db()
        self.assertTrue(obj.is_completed)
        self.assertNotContains(self.client.get('/tasks/?status=open'), 'Call')
        self.client.post(f'/tasks/{obj.pk}/delete/')
        self.assertFalse(Task.objects.exists())

    def test_negative_amount_rejected(self):
        self.client.post('/deals/new/', {'client': self.own.pk, 'title': 'Bad', 'amount': '-1', 'status': 'new'})
        self.assertFalse(Deal.objects.exists())

    def test_search(self):
        self.assertContains(self.client.get('/clients/?q=Local'), 'Local client')
        self.assertNotContains(self.client.get('/clients/?q=missing'), 'Local client')

    def test_csrf(self):
        browser = Browser(enforce_csrf_checks=True)
        browser.force_login(self.user)
        self.assertEqual(browser.post('/clients/new/', {'name': 'Invalid'}).status_code, 403)

    def test_delete_client_cascade(self):
        Deal.objects.create(owner=self.user, client=self.own, title='Deal')
        task = Task.objects.create(owner=self.user, client=self.own, title='Task')
        self.client.post(f'/clients/{self.own.pk}/delete/')
        self.assertFalse(Deal.objects.exists())
        task.refresh_from_db()
        self.assertIsNone(task.client_id)

    def test_client_registration_requires_staff_approval(self):
        self.client.logout()
        response = self.client.post('/register/', {
            'username': 'newclient', 'email': 'client@example.com', 'full_name': 'New Client',
            'company': 'Client Co', 'phone': '123',
            'password1': 'Strong-pass-2026!', 'password2': 'Strong-pass-2026!',
        })
        self.assertRedirects(response, '/accounts/login/')
        registration = RegistrationRequest.objects.get(user__username='newclient')
        self.assertFalse(registration.user.is_active)

        admin = User.objects.create_superuser('reviewer', 'reviewer@example.com', 'Admin-pass-2026!')
        reviewer = Browser()
        reviewer.force_login(admin)
        response = reviewer.post(f'/management/registrations/{registration.pk}/approve/')
        self.assertRedirects(response, '/management/requests/')
        registration.refresh_from_db()
        self.assertEqual(registration.status, RegistrationRequest.Status.APPROVED)
        self.assertTrue(registration.user.is_active)
        self.assertEqual(registration.user.portal_profile.client.name, 'New Client')

    def test_client_requests_need_approval_and_cannot_access_crm(self):
        customer = User.objects.create_user('portaluser', password='Portal-pass-2026!')
        ClientPortalProfile.objects.create(user=customer, client=self.own)
        portal = Browser()
        portal.force_login(customer)

        self.assertRedirects(portal.get('/deals/'), '/portal/')
        self.assertRedirects(portal.post('/deals/new/', {
            'client': self.own.pk, 'title': 'Blocked deal', 'amount': '1', 'status': 'new',
        }), '/portal/')
        self.assertEqual(portal.get('/management/requests/').status_code, 403)
        self.assertEqual(portal.post('/portal/requests/deal/new/', {
            'title': 'Negative deal', 'description': '', 'amount': '-1',
        }).status_code, 200)
        portal.post('/portal/requests/deal/new/', {
            'title': 'Requested deal', 'description': 'Discuss proposal', 'amount': '125.50',
        })
        portal.post('/portal/requests/deal/new/', {
            'title': 'Requested deal without amount', 'description': '', 'amount': '',
        })
        portal.post('/portal/requests/task/new/', {
            'title': 'Requested call', 'description': 'Call about proposal', 'due_date': '2026-10-10',
        })
        self.assertEqual(PortalRequest.objects.filter(requester=customer).count(), 3)
        self.assertEqual(Deal.objects.count(), 0)
        self.assertEqual(Task.objects.count(), 0)

        admin = User.objects.create_superuser('reviewer', 'reviewer@example.com', 'Admin-pass-2026!')
        reviewer = Browser()
        reviewer.force_login(admin)
        for portal_request in PortalRequest.objects.filter(requester=customer):
            response = reviewer.post(f'/management/requests/{portal_request.pk}/approve/')
            self.assertRedirects(response, '/management/requests/')
        self.assertEqual(Deal.objects.filter(title='Requested deal').get().amount, Decimal('125.50'))
        self.assertEqual(Deal.objects.filter(title='Requested deal without amount').get().amount, Decimal('0'))
        self.assertEqual(Task.objects.get().title, 'Requested call')
        self.assertEqual(PortalRequest.objects.filter(status=PortalRequest.Status.APPROVED).count(), 3)
