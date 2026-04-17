import json
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.catalogs.models import Specialty
from apps.patients.models import PatientProfile
from apps.professionals.models import ProfessionalProfile
from .models import Appointment, AvailabilityBlock


class ProfessionalAvailabilityBlocksApiTests(TestCase):
    def setUp(self):
        User = get_user_model()

        self.specialty = Specialty.objects.create(name="Medicina General")

        self.prof_user = User.objects.create_user(
            email="prof.blocks@test.local",
            password="Profesional123!",
            first_name="Laura",
            last_name="Medica",
            role="professional",
            is_email_verified=True,
        )
        self.prof_profile = ProfessionalProfile.objects.create(
            user=self.prof_user,
            specialty=self.specialty,
            license_number="BLOCK-001",
            city="Quito",
            province="Pichincha",
            verification_status=ProfessionalProfile.VerificationStatus.APPROVED,
            public_profile_enabled=True,
        )

        self.patient_user = User.objects.create_user(
            email="patient.blocks@test.local",
            password="Paciente123!",
            first_name="Ana",
            last_name="Paciente",
            role="patient",
            is_email_verified=True,
        )
        self.patient_profile = PatientProfile.objects.create(user=self.patient_user)

        # Base block
        self.base_start = timezone.now() + timedelta(days=5)
        self.base_end = self.base_start + timedelta(hours=2)
        self.block = AvailabilityBlock.objects.create(
            professional=self.prof_profile,
            start_at=self.base_start,
            end_at=self.base_end,
            reason="Congreso Médico",
        )

        # Active appointment
        self.appointment_start = timezone.now() + timedelta(days=6)
        self.appointment_end = self.appointment_start + timedelta(minutes=30)
        self.appointment = Appointment.objects.create(
            patient=self.patient_profile,
            professional=self.prof_profile,
            scheduled_at=self.appointment_start,
            ends_at=self.appointment_end,
            modality=Appointment.Modality.IN_PERSON,
            status=Appointment.Status.CONFIRMED,
            price="25.00",
            is_paid=False,
        )

        # Login
        response = self.client.post(
            "/api/v1/auth/login",
            data=json.dumps(
                {"email": "prof.blocks@test.local", "password": "Profesional123!"}
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.prof_token = response.json()["access_token"]

    def _auth_headers(self):
        return {"HTTP_AUTHORIZATION": f"Bearer {self.prof_token}"}

    def test_list_blocks_returns_200(self):
        response = self.client.get(
            "/api/v1/professional/availability/blocks",
            **self._auth_headers(),
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("items", response.json())
        self.assertGreaterEqual(len(response.json()["items"]), 1)

    def test_create_block_success(self):
        start_at = timezone.now() + timedelta(days=7)
        end_at = start_at + timedelta(hours=1)

        response = self.client.post(
            "/api/v1/professional/availability/blocks",
            data=json.dumps(
                {
                    "start_at": start_at.isoformat(),
                    "end_at": end_at.isoformat(),
                    "reason": "Vacaciones",
                }
            ),
            content_type="application/json",
            **self._auth_headers(),
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            AvailabilityBlock.objects.filter(
                professional=self.prof_profile,
                reason="Vacaciones",
            ).exists()
        )

    def test_create_block_overlapping_existing_block_returns_409(self):
        response = self.client.post(
            "/api/v1/professional/availability/blocks",
            data=json.dumps(
                {
                    "start_at": self.base_start.isoformat(),
                    "end_at": (self.base_start + timedelta(minutes=30)).isoformat(),
                    "reason": "Cruce",
                }
            ),
            content_type="application/json",
            **self._auth_headers(),
        )
        self.assertEqual(response.status_code, 409)

    def test_create_block_overlapping_active_appointment_returns_409(self):
        response = self.client.post(
            "/api/v1/professional/availability/blocks",
            data=json.dumps(
                {
                    "start_at": self.appointment_start.isoformat(),
                    "end_at": (self.appointment_start + timedelta(minutes=30)).isoformat(),
                    "reason": "No debe permitir",
                }
            ),
            content_type="application/json",
            **self._auth_headers(),
        )
        self.assertEqual(response.status_code, 409)

    def test_update_block_success(self):
        new_end = self.base_end + timedelta(hours=1)

        response = self.client.patch(
            f"/api/v1/professional/availability/blocks/{self.block.id}",
            data=json.dumps(
                {
                    "end_at": new_end.isoformat(),
                    "reason": "Congreso extendido",
                }
            ),
            content_type="application/json",
            **self._auth_headers(),
        )
        self.assertEqual(response.status_code, 200)

        self.block.refresh_from_db()
        self.assertEqual(self.block.reason, "Congreso extendido")

    def test_delete_block_success(self):
        response = self.client.delete(
            f"/api/v1/professional/availability/blocks/{self.block.id}",
            **self._auth_headers(),
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            AvailabilityBlock.objects.filter(id=self.block.id).exists()
        )
