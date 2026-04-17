import json

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.catalogs.models import Specialty
from .models import ProfessionalProfile


class ProfessionalProfileApiTests(TestCase):
    def setUp(self):
        User = get_user_model()

        self.specialty_1 = Specialty.objects.create(name="Cardiología", is_active=True)
        self.specialty_2 = Specialty.objects.create(name="Neurología", is_active=True)
        self.specialty_inactive = Specialty.objects.create(name="Inactiva", is_active=False)

        self.prof_user = User.objects.create_user(
            email="profile.prof@test.local",
            password="Profesional123!",
            first_name="Ana",
            last_name="Medica",
            phone="0990000001",
            role="professional",
            is_email_verified=True,
        )
        self.profile = ProfessionalProfile.objects.create(
            user=self.prof_user,
            specialty=self.specialty_1,
            license_number="CARD-001",
            city="Quito",
            province="Pichincha",
            bio="Perfil inicial",
            consultation_fee="25.00",
            teleconsultation_fee="20.00",
            is_accepting_patients=True,
        )

        self.other_prof_user = User.objects.create_user(
            email="other.prof@test.local",
            password="Profesional123!",
            first_name="Luis",
            last_name="Otro",
            role="professional",
            is_email_verified=True,
        )
        self.other_profile = ProfessionalProfile.objects.create(
            user=self.other_prof_user,
            specialty=self.specialty_1,
            license_number="CARD-999",
            city="Loja",
            province="Loja",
        )

        self.patient_user = User.objects.create_user(
            email="patient.profile@test.local",
            password="Paciente123!",
            first_name="Paciente",
            last_name="Uno",
            role="patient",
        )

        self.prof_token = self._login("profile.prof@test.local", "Profesional123!")
        self.patient_token = self._login("patient.profile@test.local", "Paciente123!")

    def _login(self, email, password):
        response = self.client.post(
            "/api/v1/auth/login",
            data=json.dumps({"email": email, "password": password}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        return response.json()["access_token"]

    def _auth_headers(self, token):
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def test_professional_can_get_own_profile(self):
        response = self.client.get(
            "/api/v1/professional/profile",
            **self._auth_headers(self.prof_token),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["profile"]["license_number"], "CARD-001")

    def test_professional_can_patch_own_profile(self):
        response = self.client.patch(
            "/api/v1/professional/profile",
            data=json.dumps(
                {
                    "first_name": "Ana Maria",
                    "specialty_id": self.specialty_2.id,
                    "license_number": "NEURO-777",
                    "city": "Guayaquil",
                    "province": "Guayas",
                    "consultation_fee": "35.50",
                    "teleconsultation_fee": "30.00",
                    "public_profile_enabled": True,
                }
            ),
            content_type="application/json",
            **self._auth_headers(self.prof_token),
        )
        self.assertEqual(response.status_code, 200)

        self.profile.refresh_from_db()
        self.prof_user.refresh_from_db()

        self.assertEqual(self.prof_user.first_name, "Ana Maria")
        self.assertEqual(self.profile.specialty_id, self.specialty_2.id)
        self.assertEqual(self.profile.license_number, "NEURO-777")
        self.assertEqual(self.profile.city, "Guayaquil")
        self.assertEqual(str(self.profile.consultation_fee), "35.50")

    def test_professional_cannot_use_duplicate_license(self):
        response = self.client.patch(
            "/api/v1/professional/profile",
            data=json.dumps({"license_number": "CARD-999"}),
            content_type="application/json",
            **self._auth_headers(self.prof_token),
        )
        self.assertEqual(response.status_code, 409)

    def test_professional_cannot_use_inactive_specialty(self):
        response = self.client.patch(
            "/api/v1/professional/profile",
            data=json.dumps({"specialty_id": self.specialty_inactive.id}),
            content_type="application/json",
            **self._auth_headers(self.prof_token),
        )
        self.assertEqual(response.status_code, 400)

    def test_patient_cannot_access_professional_profile_route(self):
        response = self.client.get(
            "/api/v1/professional/profile",
            **self._auth_headers(self.patient_token),
        )
        self.assertEqual(response.status_code, 403)
