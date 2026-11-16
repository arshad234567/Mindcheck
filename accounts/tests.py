from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from accounts.models import Profile
from screening.models import Assessment


class AccountTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_mindcheck", stdout=StringIO())

    def test_new_user_gets_member_profile(self):
        user = User.objects.create_user("newbie", "n@example.com", "Str0ng-pass!")
        self.assertEqual(user.profile.role, Profile.Role.MEMBER)
        self.assertFalse(user.profile.has_consented)

    def test_register_logs_in_and_asks_for_consent(self):
        response = self.client.post(reverse("accounts:register"), {
            "username": "riya", "first_name": "Riya", "email": "riya@example.com",
            "password1": "Calm-River-2026", "password2": "Calm-River-2026",
        })
        self.assertRedirects(response, reverse("screening:consent"))
        self.assertEqual(User.objects.get(username="riya").profile.role, "member")

    def test_register_rejects_duplicate_email_and_weak_password(self):
        response = self.client.post(reverse("accounts:register"), {
            "username": "copy", "email": "member@mindcheck.local",
            "password1": "123", "password2": "123",
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already exists")
        self.assertFalse(User.objects.filter(username="copy").exists())

    def test_passwords_are_hashed(self):
        user = User.objects.get(username="demo_member")
        self.assertNotEqual(user.password, "MindCheck@2026")
        self.assertTrue(user.password.startswith(("pbkdf2_", "argon2", "bcrypt")))

    def test_login_and_logout(self):
        response = self.client.post(reverse("accounts:login"),
                                    {"username": "demo_member", "password": "MindCheck@2026"})
        self.assertRedirects(response, reverse("accounts:dashboard"))
        self.client.post(reverse("accounts:logout"))
        self.assertEqual(self.client.get(reverse("accounts:dashboard")).status_code, 302)

    def test_wrong_password_shows_error(self):
        response = self.client.post(reverse("accounts:login"), {"username": "demo_member", "password": "nope"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "correct username and password")

    def test_counsellor_dashboard_redirect(self):
        self.client.login(username="counsellor1", password="MindCheck@2026")
        self.assertRedirects(self.client.get(reverse("accounts:dashboard")), reverse("screening:counsellor"))

    def test_delete_all_results(self):
        self.client.login(username="demo_member", password="MindCheck@2026")
        self.assertGreater(Assessment.objects.filter(user__username="demo_member").count(), 0)
        self.client.post(reverse("accounts:delete_my_data"), {"action": "results"})
        self.assertEqual(Assessment.objects.filter(user__username="demo_member").count(), 0)
        self.assertTrue(User.objects.filter(username="demo_member").exists())

    def test_delete_account_removes_everything(self):
        self.client.login(username="demo_member", password="MindCheck@2026")
        self.client.post(reverse("accounts:delete_my_data"), {"action": "account"})
        self.assertFalse(User.objects.filter(username="demo_member").exists())
        self.assertEqual(Assessment.objects.filter(user__username="demo_member").count(), 0)

    def test_logout_needs_post_and_csrf(self):
        csrf_client = self.client_class(enforce_csrf_checks=True)
        csrf_client.login(username="demo_member", password="MindCheck@2026")
        response = csrf_client.post(reverse("accounts:logout"))
        self.assertEqual(response.status_code, 403)  # no CSRF token -> rejected
        self.assertEqual(self.client.get(reverse("accounts:logout")).status_code, 405)
