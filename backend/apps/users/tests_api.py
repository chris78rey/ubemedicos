import json

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.patients.models import PatientProfile
from apps.professionals.models import ProfessionalProfile


class UsersApiAuthTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin_user = User.objects.create_user(
            email="admin@test.local",
            password="Admin12345!",
            first_name="Admin",
            last_name="Test",
            role="admin",
            is_staff=True,
            is_email_verified=True,
        )

        self.prof_user = User.objects.create_user(
            email="pro@test.local",
            password="Pro123456!",
            first_name="Ana",
            last_name="Ruiz",
            role="professional",
            is_email_verified=True,
        )

    def test_login_returns_access_token_and_user(self):
        response = self.client.post(
            "/api/v1/auth/login",
            data=json.dumps(
                {
                    "email": "admin@test.local",
                    "password": "Admin12345!",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("access_token", payload)
        self.assertEqual(payload["token_type"], "bearer")
        self.assertEqual(payload["user"]["email"], "admin@test.local")
        self.assertIn("admin_validation", payload["user"]["role_codes"])

    def test_login_fails_with_invalid_credentials(self):
        response = self.client.post(
            "/api/v1/auth/login",
            data=json.dumps(
                {
                    "email": "admin@test.local",
                    "password": "wrong-password",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)

    def test_auth_me_requires_token(self):
        response = self.client.get("/api/v1/auth/me")
        self.assertEqual(response.status_code, 401)

    def test_auth_me_works_with_bearer_token(self):
        login = self.client.post(
            "/api/v1/auth/login",
            data=json.dumps(
                {
                    "email": "pro@test.local",
                    "password": "Pro123456!",
                }
            ),
            content_type="application/json",
        )
        token = login.json()["access_token"]

        response = self.client.get(
            "/api/v1/auth/me",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["email"], "pro@test.local")
        self.assertIn("professional", payload["role_codes"])

    def test_users_me_fallback_works(self):
        login = self.client.post(
            "/api/v1/auth/login",
            data=json.dumps(
                {
                    "email": "admin@test.local",
                    "password": "Admin12345!",
                }
            ),
            content_type="application/json",
        )
        token = login.json()["access_token"]

        response = self.client.get(
            "/api/v1/users/me",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["email"], "admin@test.local")

    def test_logout_returns_200(self):
        response = self.client.post("/api/v1/auth/logout")
        self.assertEqual(response.status_code, 200)

    def test_register_patient_creates_profile(self):
        response = self.client.post(
            "/api/v1/auth/register/patient",
            data=json.dumps(
                {
                    "email": "patient.register@test.local",
                    "password": "Paciente123!",
                    "first_name": "Registro",
                    "last_name": "Paciente",
                    "national_id": "1111111111",
                    "phone": "0999999999",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        User = get_user_model()
        user = User.objects.get(email="patient.register@test.local")
        self.assertEqual(user.role, "patient")
        self.assertTrue(PatientProfile.objects.filter(user=user).exists())

    def test_register_professional_creates_draft_profile(self):
        response = self.client.post(
            "/api/v1/auth/register/professional",
            data=json.dumps(
                {
                    "email": "professional.register@test.local",
                    "password": "Profesional123!",
                    "first_name": "Registro",
                    "last_name": "Profesional",
                    "national_id": "2222222222",
                    "phone": "0999999998",
                    "professional_type": "general",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        User = get_user_model()
        user = User.objects.get(email="professional.register@test.local")
        profile = ProfessionalProfile.objects.get(user=user)

        self.assertEqual(user.role, "professional")
        self.assertEqual(
            profile.verification_status, ProfessionalProfile.VerificationStatus.DRAFT
        )
        self.assertFalse(profile.public_profile_enabled)
        self.assertTrue(profile.license_number.startswith("TEMP-LIC-"))
