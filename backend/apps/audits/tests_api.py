import json

from django.contrib.auth import get_user_model
from django.test import TestCase

from .models import AuditEvent


class AuditApiTests(TestCase):
    def setUp(self):
        User = get_user_model()

        self.admin_user = User.objects.create_user(
            email="admin.audit@test.local",
            password="Admin123!",
            first_name="Admin",
            last_name="Audit",
            role="admin",
            is_staff=True,
        )

        self.super_admin_user = User.objects.create_user(
            email="super.audit@test.local",
            password="Admin123!",
            first_name="Super",
            last_name="Audit",
            role="super_admin",
            is_staff=True,
            is_superuser=True,
        )

        self.privacy_user = User.objects.create_user(
            email="privacy.audit@test.local",
            password="Privacy123!",
            first_name="Privacy",
            last_name="Auditor",
            role="privacy_auditor",
        )

        self.professional_user = User.objects.create_user(
            email="professional.audit@test.local",
            password="Profesional123!",
            first_name="Doctor",
            last_name="Audit",
            role="professional",
        )

        self.patient_user = User.objects.create_user(
            email="patient.audit@test.local",
            password="Paciente123!",
            first_name="Paciente",
            last_name="Audit",
            role="patient",
        )

        self.admin_token = self._login("admin.audit@test.local", "Admin123!")
        self.super_admin_token = self._login("super.audit@test.local", "Admin123!")
        self.privacy_token = self._login("privacy.audit@test.local", "Privacy123!")
        self.prof_token = self._login(
            "professional.audit@test.local",
            "Profesional123!",
        )
        self.patient_token = self._login("patient.audit@test.local", "Paciente123!")

        self.event_admin = AuditEvent.objects.create(
            actor=self.admin_user,
            event_type="availability_slot_created",
            entity_type="AvailabilitySlot",
            entity_id="10",
            metadata={"weekday": 1, "modality": "in_person"},
        )

        self.event_patient = AuditEvent.objects.create(
            actor=self.patient_user,
            event_type="payment_intent_created",
            entity_type="Payment",
            entity_id="20",
            metadata={"amount": "25.00", "currency": "USD"},
        )

        self.event_professional = AuditEvent.objects.create(
            actor=self.professional_user,
            event_type="professional_verification_submitted",
            entity_type="ProfessionalVerificationSubmission",
            entity_id="30",
            metadata={"professional_id": 99},
        )

        self.event_system = AuditEvent.objects.create(
            actor=None,
            event_type="system_seed",
            entity_type="SeedCommand",
            entity_id="seed-1",
            metadata={"source": "seed_initial_data"},
        )

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

    def test_admin_can_list_audit_logs(self):
        response = self.client.get(
            "/api/v1/admin/audits/access-logs",
            **self._auth_headers(self.admin_token),
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("items", response.json())
        self.assertGreaterEqual(len(response.json()["items"]), 4)

    def test_super_admin_can_list_audit_logs(self):
        response = self.client.get(
            "/api/v1/admin/audits/access-logs",
            **self._auth_headers(self.super_admin_token),
        )
        self.assertEqual(response.status_code, 200)

    def test_privacy_auditor_can_list_audit_logs(self):
        response = self.client.get(
            "/api/v1/admin/audits/access-logs",
            **self._auth_headers(self.privacy_token),
        )
        self.assertEqual(response.status_code, 200)

    def test_professional_cannot_access_admin_audit_logs(self):
        response = self.client.get(
            "/api/v1/admin/audits/access-logs",
            **self._auth_headers(self.prof_token),
        )
        self.assertEqual(response.status_code, 403)

    def test_admin_can_filter_by_actor_email(self):
        response = self.client.get(
            "/api/v1/admin/audits/access-logs?actor_email=patient.audit@test.local",
            **self._auth_headers(self.admin_token),
        )
        self.assertEqual(response.status_code, 200)

        items = response.json()["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["actor"]["email"], "patient.audit@test.local")
        self.assertEqual(items[0]["event_type"], "payment_intent_created")

    def test_admin_can_filter_by_event_type(self):
        response = self.client.get(
            "/api/v1/admin/audits/access-logs?event_type=availability_slot_created",
            **self._auth_headers(self.admin_token),
        )
        self.assertEqual(response.status_code, 200)

        items = response.json()["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["id"], self.event_admin.id)

    def test_admin_can_view_audit_log_detail(self):
        response = self.client.get(
            f"/api/v1/admin/audits/access-logs/{self.event_patient.id}",
            **self._auth_headers(self.admin_token),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], self.event_patient.id)
        self.assertEqual(response.json()["entity_type"], "Payment")

    def test_admin_can_export_csv(self):
        response = self.client.get(
            "/api/v1/admin/audits/access-logs/export.csv?limit=3",
            **self._auth_headers(self.admin_token),
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response["Content-Type"])
        self.assertEqual(response["X-Export-Row-Limit"], "3")
        self.assertIn("payment_intent_created", response.content.decode("utf-8"))

    def test_me_audit_events_only_returns_current_user_events(self):
        response = self.client.get(
            "/api/v1/users/me/audit-events",
            **self._auth_headers(self.patient_token),
        )
        self.assertEqual(response.status_code, 200)

        items = response.json()["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["actor"]["email"], "patient.audit@test.local")
        self.assertEqual(items[0]["event_type"], "payment_intent_created")

    def test_me_audit_events_requires_auth(self):
        from django.test import Client
        fresh_client = Client()
        response = fresh_client.get("/api/v1/users/me/audit-events")
        self.assertEqual(response.status_code, 401)

    def test_invalid_page_size_returns_400(self):
        response = self.client.get(
            "/api/v1/admin/audits/access-logs?page_size=9999",
            **self._auth_headers(self.admin_token),
        )
        self.assertEqual(response.status_code, 400)
