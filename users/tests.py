from django.test import TestCase, override_settings, RequestFactory
from django.urls import reverse
from django.conf import settings
from django.contrib.sessions.middleware import SessionMiddleware
from unittest.mock import patch

from .models import User, FishermanProfile, CustomerProfile, BeachChairmanProfile

try:
    from allauth.socialaccount.models import SocialAccount, SocialLogin, SocialApp
except ImportError:
    SocialAccount = SocialLogin = SocialApp = None

try:
    from users.adapters import RechiroSocialAccountAdapter
except ImportError:
    RechiroSocialAccountAdapter = None


class AuthEndpointsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='authuser',
            password='testpass123',
            role='customer',
            email='auth@example.com',
            phone='0700000999',
        )

    def test_login_register_pages_accessible(self):
        self.assertEqual(self.client.get(reverse('users:login')).status_code, 200)
        self.assertEqual(self.client.get(reverse('users:register')).status_code, 200)

    def test_email_password_login_works(self):
        response = self.client.post(reverse('users:login'), {
            'username': 'authuser',
            'password': 'testpass123',
        })
        self.assertEqual(response.status_code, 302)

    def test_profile_requires_authentication(self):
        response = self.client.get(reverse('users:profile'))
        self.assertEqual(response.status_code, 302)

    @override_settings(GOOGLE_CLIENT_ID='test-client-id', GOOGLE_CLIENT_SECRET='test-client-secret')
    def test_google_oauth_entrypoint_accessible_when_enabled(self):
        if not getattr(settings, 'ALLAUTH_INSTALLED', False) or SocialApp is None:
            self.skipTest('allauth not installed in this environment')
        from django.contrib.sites.models import Site
        app, _ = SocialApp.objects.get_or_create(
            provider='google',
            defaults={
                'name': 'Google',
                'client_id': settings.GOOGLE_CLIENT_ID,
                'secret': settings.GOOGLE_CLIENT_SECRET,
            }
        )
        app.sites.add(Site.objects.get_current())
        response = self.client.get('/accounts/google/login/')
        self.assertIn(response.status_code, [200, 302])

    def test_resend_email_verification_requires_login(self):
        response = self.client.post(reverse('users:resend_email_verification'))
        self.assertEqual(response.status_code, 302)

    def test_logged_in_user_can_trigger_resend_email_verification(self):
        self.client.login(username='authuser', password='testpass123')
        response = self.client.post(reverse('users:resend_email_verification'))
        self.assertEqual(response.status_code, 302)

    def test_email_verification_page_requires_login(self):
        response = self.client.get(reverse('users:email_verification'))
        self.assertEqual(response.status_code, 302)

    def test_email_verification_page_is_accessible_for_logged_in_user(self):
        self.client.login(username='authuser', password='testpass123')
        response = self.client.get(reverse('users:email_verification'))
        self.assertEqual(response.status_code, 200)

    def test_phone_verification_page_requires_login(self):
        response = self.client.get(reverse('users:phone_verification'))
        self.assertEqual(response.status_code, 302)

    @patch('users.views._initiate_phone_verification_stk')
    def test_fisherman_can_trigger_phone_verification_stk(self, mock_initiate):
        fisher = User.objects.create_user(
            username='fisherauth',
            password='testpass123',
            role='fisherman',
            email='fisherauth@example.com',
            phone='0700012345',
            phone_verified=False,
        )
        mock_initiate.return_value = {'success': True}
        self.client.login(username='fisherauth', password='testpass123')
        response = self.client.post(reverse('users:resend_phone_verification'))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(mock_initiate.called)


class RoleEndpointsTests(TestCase):
    def setUp(self):
        self.password = 'RolePass123!'
        self.users_by_role = {}
        roles = ['fisherman', 'customer', 'delivery', 'chairman', 'admin']
        for role in roles:
                user = User.objects.create_user(
                    username=f'{role}user',
                    password=self.password,
                    role=role,
                    email=f'{role}@rechiro.test',
                    phone='0712345678',
                )
                if role == 'admin':
                    user.is_staff = True
                    user.save(update_fields=['is_staff'])
                self.users_by_role[role] = user

        FishermanProfile.objects.create(
            user=self.users_by_role['fisherman'],
            phone=self.users_by_role['fisherman'].phone,
            landing_site='Lake',
            location='Lake Victoria',
            contact_details='Dock 1',
        )
        CustomerProfile.objects.create(
            user=self.users_by_role['customer'],
            phone=self.users_by_role['customer'].phone,
            delivery_location='Nairobi',
            delivery_address='Test Address',
            preferred_fulfillment='delivery',
        )
        BeachChairmanProfile.objects.create(
            user=self.users_by_role['chairman'],
            beach_name='Lake Beach',
            phone=self.users_by_role['chairman'].phone,
        )

    def _login_and_get(self, username, url):
        logged_in = self.client.login(username=username, password=self.password)
        self.assertTrue(logged_in, f'Unable to log in {username}')
        response = self.client.get(url)
        self.client.logout()
        return response

    def test_fisherman_dashboard_accessible(self):
        response = self._login_and_get('fishermanuser', reverse('fishing:fisherman_dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_customer_dashboard_accessible(self):
        response = self._login_and_get('customeruser', reverse('fishing:customer_dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_delivery_dashboard_accessible(self):
        response = self._login_and_get('deliveryuser', reverse('fishing:delivery_dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_chairman_queue_accessible(self):
        response = self._login_and_get('chairmanuser', reverse('fishing:chairman_approval_queue'))
        self.assertEqual(response.status_code, 200)

    def test_rechiro_adapter_marks_google_new_user_for_role_choice(self):
        factory = RequestFactory()
        request = factory.get('/accounts/google/login/')
        middleware = SessionMiddleware(lambda req: None)
        middleware.process_request(request)
        request.session.save()
        if not (RechiroSocialAccountAdapter and SocialAccount and SocialLogin):
            self.skipTest('django-allauth is unavailable for adapter tests')
        adapter = RechiroSocialAccountAdapter()
        user = User(username='googlenew', email='googlenew@example.com', role='customer')
        account = SocialAccount(provider='google', uid='googleuid-test', user=user)
        sociallogin = SocialLogin(account=account, user=user)
        adapter.save_user(request, sociallogin)
        refreshed = User.objects.get(username='googlenew')
        self.assertEqual(refreshed.role, '')
        self.assertTrue(request.session.get('needs_role_selection'))

    def test_admin_dashboard_accessible(self):
        response = self._login_and_get('adminuser', reverse('fishing:admin_dashboard'))
        self.assertEqual(response.status_code, 200)
