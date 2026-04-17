import json

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.catalogs.models import Specialty
from apps.professionals.models import ProfessionalProfile
from .models import AvailabilitySlot


class ProfessionalAvailabilityApiTests(TestCase):
    def setUp(self):
        User = get_user_model()

        self.user = User.objects.create_user(
            email="availability.prof@test.local",
            password="Profesional123!",
            first_name="Horario",
            last_name="Profesional",
            role="professional",
            is_email_verified=True,
        )

        specialty = Specialty.objects.create(name="Medicina General")

        self.profile = ProfessionalProfile.objects.create(
            user=self.user,
            specialty=specialty,
            license_number="AVAIL-001",
            city="Quito",
            province="Pichincha",
        )

        login = self.client.post(
            "/api/v1/auth/login",
            data=json.dumps(
                {
                    "email": "availability.prof@test.local",
                    "password": "Profesional123!",
                }
            ),
            content_type="application/json",
        )
        self.token = login.json()["access_token"]

    def _auth_headers(self):
        return {"HTTP_AUTHORIZATION": f"Bearer {self.token}"}

    def test_list_availability_returns_200(self):
        response = self.client.get(
            "/api/v1/professional/availability",
            **self._auth_headers(),
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("items", response.json())

    def test_create_availability_slot(self):
        response = self.client.post(
            "/api/v1/professional/availability",
            data=json.dumps(
                {
                    "weekday": 1,
                    "start_time": "08:00",
                    "end_time": "12:00",
                    "modality": "in_person",
                    "is_active": True,
                }
            ),
            content_type="application/json",
            **self._auth_headers(),
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            AvailabilitySlot.objects.filter(
                professional=self.profile,
                weekday=1,
                modality="in_person",
            ).exists()
        )

    def test_create_overlapping_slot_returns_409(self):
        AvailabilitySlot.objects.create(
            professional=self.profile,
            weekday=1,
            start_time="08:00",
            end_time="12:00",
            modality="in_person",
            is_active=True,
        )

        response = self.client.post(
            "/api/v1/professional/availability",
            data=json.dumps(
                {
                    "weekday": 1,
                    "start_time": "11:00",
                    "end_time": "13:00",
                    "modality": "in_person",
                    "is_active": True,
                }
            ),
            content_type="application/json",
            **self._auth_headers(),
        )
        self.assertEqual(response.status_code, 409)

    def test_update_slot(self):
        slot = AvailabilitySlot.objects.create(
            professional=self.profile,
            weekday=2,
            start_time="08:00",
            end_time="10:00",
            modality="teleconsultation",
            is_active=True,
        )

        response = self.client.patch(
            f"/api/v1/professional/availability/{slot.id}",
            data=json.dumps(
                {
                    "start_time": "09:00",
                    "end_time": "11:00",
                }
            ),
            content_type="application/json",
            **self._auth_headers(),
        )

        self.assertEqual(response.status_code, 200)
        slot.refresh_from_db()
        self.assertEqual(slot.start_time.strftime("%H:%M:%S"), "09:00:00")
        self.assertEqual(slot.end_time.strftime("%H:%M:%S"), "11:00:00")

    def test_delete_slot_soft_deactivates(self):
        slot = AvailabilitySlot.objects.create(
            professional=self.profile,
            weekday=3,
            start_time="15:00",
            end_time="18:00",
            modality="in_person",
            is_active=True,
        )

        response = self.client.delete(
            f"/api/v1/professional/availability/{slot.id}",
            **self._auth_headers(),
        )

        self.assertEqual(response.status_code, 200)
        slot.refresh_from_db()
        self.assertFalse(slot.is_active)
