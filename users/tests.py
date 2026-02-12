from django.test import TestCase
from django.urls import reverse
from django.conf import settings

from .models import User


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

    def test_google_oauth_entrypoint_accessible_when_enabled(self):
        if not getattr(settings, 'ALLAUTH_INSTALLED', False):
            self.skipTest('allauth not installed in this environment')
        response = self.client.get('/accounts/google/login/')
        self.assertIn(response.status_code, [200, 302])

    def test_resend_email_verification_requires_login(self):
        response = self.client.post(reverse('users:resend_email_verification'))
        self.assertEqual(response.status_code, 302)

    def test_logged_in_user_can_trigger_resend_email_verification(self):
        self.client.login(username='authuser', password='testpass123')
        response = self.client.post(reverse('users:resend_email_verification'))
        self.assertEqual(response.status_code, 302)
