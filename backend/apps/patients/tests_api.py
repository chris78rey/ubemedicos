import json

from django.contrib.auth import get_user_model
from django.test import TestCase

from .models import PatientProfile


class PatientProfileApiTests(TestCase):
    def setUp(self):
        User = get_user_model()

        self.patient_user = User.objects.create_user(
            email="patient.self@test.local",
            password="Paciente123!",
            first_name="Maria",
            last_name="Paciente",
            phone="0980000000",
            role="patient",
        )
        self.profile = PatientProfile.objects.create(
            user=self.patient_user,
            national_id="1711111111",
        )

        self.prof_user = User.objects.create_user(
            email="doctor.self@test.local",
            password="Profesional123!",
            first_name="Doctor",
            last_name="Uno",
            role="professional",
        )

        self.patient_token = self._login("patient.self@test.local", "Paciente123!")
        self.prof_token = self._login("doctor.self@test.local", "Profesional123!")

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

    def test_patient_can_get_own_profile(self):
        response = self.client.get(
            "/api/v1/patient/profile",
            **self._auth_headers(self.patient_token),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["profile"]["national_id"], "1711111111")

    def test_patient_can_patch_own_profile(self):
        response = self.client.patch(
            "/api/v1/patient/profile",
            data=json.dumps(
                {
                    "first_name": "Maria Jose",
                    "phone": "0991234567",
                    "birth_date": "1995-08-23",
                    "gender": "female",
                    "emergency_contact_name": "Pedro Paciente",
                    "emergency_contact_phone": "0987654321",
                }
            ),
            content_type="application/json",
            **self._auth_headers(self.patient_token),
        )
        self.assertEqual(response.status_code, 200)

        self.patient_user.refresh_from_db()
        self.profile.refresh_from_db()

        self.assertEqual(self.patient_user.first_name, "Maria Jose")
        self.assertEqual(self.patient_user.phone, "0991234567")
        self.assertEqual(self.profile.birth_date.isoformat(), "1995-08-23")
        self.assertEqual(self.profile.emergency_contact_name, "Pedro Paciente")

    def test_patient_birth_date_validation(self):
        response = self.client.patch(
            "/api/v1/patient/profile",
            data=json.dumps({"birth_date": "23/08/1995"}),
            content_type="application/json",
            **self._auth_headers(self.patient_token),
        )
        self.assertEqual(response.status_code, 400)

    def test_professional_cannot_access_patient_profile_route(self):
        response = self.client.get(
            "/api/v1/patient/profile",
            **self._auth_headers(self.prof_token),
        )
        self.assertEqual(response.status_code, 403)
