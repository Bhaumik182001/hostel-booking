from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from accounts.models import StudentProfile
from accounts.forms import StudentRegistrationForm

# Neutral mock fixture value satisfying Django's AUTH_PASSWORD_VALIDATORS
dummy_test_pass = 'MockFixturePass2026!'  # ggignore


class AccountsModelAndFormTests(TestCase):
    def test_student_profile_auto_creation_via_form(self):
        """Test StudentProfile is automatically created when StudentRegistrationForm saves."""
        form_data = {
            'username': 'john_doe',
            'first_name': 'John',
            'last_name': 'Doe',
            'email': 'john@example.com',
            'password1': dummy_test_pass,
            'password2': dummy_test_pass,
        }
        form = StudentRegistrationForm(data=form_data)
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()

        self.assertIsNotNone(user.pk)
        self.assertTrue(StudentProfile.objects.filter(user=user).exists())
        profile = StudentProfile.objects.get(user=user)
        self.assertEqual(profile.user.email, 'john@example.com')
        self.assertIsNone(profile.current_room)
        self.assertIn('john_doe', str(profile))


class AccountsAuthenticationAndAccessTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.password = dummy_test_pass
        self.user = User.objects.create_user(
            username='student1',
            email='student1@hostel.edu',
            password=self.password,
            first_name='Alex',
            last_name='Smith',
        )
        self.profile = StudentProfile.objects.create(user=self.user)
        self.login_url = reverse('accounts:login')
        self.logout_url = reverse('accounts:logout')
        self.dashboard_url = reverse('accounts:dashboard')

    def test_login_required_redirects_unauthenticated_user(self):
        """Unauthenticated user accessing protected dashboard must be redirected to login."""
        response = self.client.get(self.dashboard_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(self.login_url, response.url)

    def test_login_successful_and_redirects(self):
        """Valid credentials log in the user and redirect to dashboard."""
        response = self.client.post(self.login_url, {
            'username': 'student1',
            'password': self.password,
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['user'].is_authenticated)
        self.assertEqual(response.context['user'].username, 'student1')

    def test_logout_workflow(self):
        """Logging out terminates the session and redirects to login."""
        self.client.login(username='student1', password=self.password)
        response = self.client.get(self.logout_url, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['user'].is_authenticated)


class AccountsSessionAndCookieTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.password = dummy_test_pass
        self.user = User.objects.create_user(
            username='session_student',
            email='session@hostel.edu',
            password=self.password,
        )
        self.profile = StudentProfile.objects.create(user=self.user)
        self.client.login(username='session_student', password=self.password)

    def test_session_account_visits_counter(self):
        """Visits to dashboard must increment account_visits session state."""
        url = reverse('accounts:dashboard')

        # First visit
        response1 = self.client.get(url)
        self.assertEqual(response1.status_code, 200)
        self.assertEqual(self.client.session['account_visits'], 1)
        self.assertIn('last_activity', self.client.session)

        # Second visit
        response2 = self.client.get(url)
        self.assertEqual(response2.status_code, 200)
        self.assertEqual(self.client.session['account_visits'], 2)

    def test_set_preference_cookie_and_session_persistence(self):
        """Test cookie setting view and propagation into session upon login."""
        set_cookie_url = reverse('accounts:set_preference') + '?preferred_block=Block-B'
        response = self.client.get(set_cookie_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('preferred_block', response.cookies)
        self.assertEqual(response.cookies['preferred_block'].value, 'Block-B')

        # Logout and log in again with cookie set
        self.client.logout()
        self.client.cookies['preferred_block'] = 'Block-B'
        login_response = self.client.post(reverse('accounts:login'), {
            'username': 'session_student',
            'password': self.password,
        }, follow=True)
        self.assertEqual(login_response.status_code, 200)
        self.assertEqual(self.client.session.get('preferred_block'), 'Block-B')
