from django.test import TestCase

from .models import Specialty


class CatalogsApiTests(TestCase):
    def test_only_active_specialties_are_listed(self):
        Specialty.objects.create(name="Cardiología", is_active=True)
        Specialty.objects.create(name="Neurología", is_active=True)
        Specialty.objects.create(name="Temporal", is_active=False)

        response = self.client.get("/api/v1/catalogs/specialties")
        self.assertEqual(response.status_code, 200)

        names = [item["name"] for item in response.json()["items"]]
        self.assertIn("Cardiología", names)
        self.assertIn("Neurología", names)
        self.assertNotIn("Temporal", names)
