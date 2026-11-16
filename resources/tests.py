from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Resource, ResourceCategory


class ResourceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_mindcheck", stdout=StringIO())
        cls.category = ResourceCategory.objects.get(slug="campus-counselling")

    def valid_data(self, **extra):
        data = {
            "name": "Hostel Peer Support", "category": self.category.pk,
            "description": "Trained student volunteers who listen.", "phone": "98765 43210",
            "city": "Phagwara", "hours": "Daily 18:00-22:00", "is_free": "on",
            "last_verified": timezone.localdate().isoformat(),
        }
        data.update(extra)
        return data

    def test_directory_lists_and_searches(self):
        response = self.client.get(reverse("resources:list"), {"q": "tele"})
        self.assertContains(response, "Tele-MANAS")
        self.assertNotContains(response, "Civil Hospital")

    def test_search_with_no_match(self):
        response = self.client.get(reverse("resources:list"), {"q": "zzzz"})
        self.assertContains(response, "No resources match")

    def test_crisis_only_filter_and_category_url(self):
        response = self.client.get(reverse("resources:list"), {"crisis_only": "on"})
        names = [r.name for r in response.context["page_obj"]]
        self.assertTrue(all(Resource.objects.get(name=n).is_crisis_line for n in names))
        response = self.client.get(reverse("resources:by_category", args=["hospital"]))
        self.assertContains(response, "Civil Hospital")

    def test_unknown_category_404(self):
        self.assertEqual(self.client.get(reverse("resources:by_category", args=["nope"])).status_code, 404)

    def test_detail_and_missing_detail(self):
        r = Resource.objects.first()
        self.assertContains(self.client.get(r.get_absolute_url()), r.phone)
        self.assertEqual(self.client.get(reverse("resources:detail", args=[9999])).status_code, 404)

    def test_member_cannot_create(self):
        self.client.login(username="demo_member", password="MindCheck@2026")
        response = self.client.post(reverse("resources:create"), self.valid_data())
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Resource.objects.filter(name="Hostel Peer Support").exists())

    def test_counsellor_full_crud(self):
        self.client.login(username="counsellor1", password="MindCheck@2026")
        # Create
        response = self.client.post(reverse("resources:create"), self.valid_data())
        resource = Resource.objects.get(name="Hostel Peer Support")
        self.assertRedirects(response, resource.get_absolute_url())
        self.assertEqual(resource.created_by.username, "counsellor1")
        # Update
        self.client.post(reverse("resources:update", args=[resource.pk]), self.valid_data(hours="24/7"))
        resource.refresh_from_db()
        self.assertEqual(resource.hours, "24/7")
        # Delete
        self.client.post(reverse("resources:delete", args=[resource.pk]))
        self.assertFalse(Resource.objects.filter(pk=resource.pk).exists())

    def test_validation_rules(self):
        self.client.login(username="counsellor1", password="MindCheck@2026")
        future = (timezone.localdate() + timedelta(days=3)).isoformat()
        response = self.client.post(reverse("resources:create"), self.valid_data(last_verified=future))
        self.assertContains(response, "cannot be in the future")
        response = self.client.post(reverse("resources:create"), self.valid_data(phone="call me"))
        self.assertContains(response, "digits")
        response = self.client.post(reverse("resources:create"), self.valid_data(alt_phone="98765 43210"))
        self.assertContains(response, "must be different")

    def test_crisis_line_cannot_be_deleted_by_category_cascade(self):
        from django.db.models import ProtectedError
        with self.assertRaises(ProtectedError):
            ResourceCategory.objects.get(slug="national-helpline").delete()


@override_settings(DEBUG=False)
class ErrorPageTests(TestCase):
    def test_custom_404_page(self):
        response = self.client.get("/this-page-does-not-exist/")
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "couldn't find that page", status_code=404)
        self.assertTemplateUsed(response, "errors/404.html")

    def test_custom_403_page(self):
        response = self.client.get(reverse("resources:create"))  # not signed in -> login redirect
        self.assertEqual(response.status_code, 302)
