import json
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.catalogs.models import Specialty
from apps.patients.models import PatientProfile
from apps.professionals.models import ProfessionalProfile
from apps.payments.models import Payment
from .models import Appointment


class ProfessionalAppointmentLifecycleApiTests(TestCase):
    def setUp(self):
        User = get_user_model()

        self.specialty = Specialty.objects.create(name="Medicina General")

        self.prof_user = User.objects.create_user(
            email="prof.lifecycle@test.local",
            password="Profesional123!",
            first_name="Laura",
            last_name="Medica",
            role="professional",
            is_email_verified=True,
        )
        self.prof_profile = ProfessionalProfile.objects.create(
            user=self.prof_user,
            specialty=self.specialty,
            license_number="LIFE-001",
            city="Quito",
            province="Pichincha",
            verification_status=ProfessionalProfile.VerificationStatus.APPROVED,
            public_profile_enabled=True,
        )

        self.other_prof_user = User.objects.create_user(
            email="other.prof.lifecycle@test.local",
            password="Profesional123!",
            first_name="Carlos",
            last_name="Otro",
            role="professional",
            is_email_verified=True,
        )
        self.other_prof_profile = ProfessionalProfile.objects.create(
            user=self.other_prof_user,
            specialty=self.specialty,
            license_number="LIFE-002",
            city="Loja",
            province="Loja",
            verification_status=ProfessionalProfile.VerificationStatus.APPROVED,
            public_profile_enabled=True,
        )

        self.patient_user = User.objects.create_user(
            email="patient.lifecycle@test.local",
            password="Paciente123!",
            first_name="Ana",
            last_name="Paciente",
            role="patient",
            is_email_verified=True,
        )
        self.patient_profile = PatientProfile.objects.create(user=self.patient_user)

        self.future_dt = timezone.now() + timedelta(days=2)
        self.past_dt = timezone.now() - timedelta(days=2)

        self.pending_appointment = Appointment.objects.create(
            patient=self.patient_profile,
            professional=self.prof_profile,
            scheduled_at=self.future_dt,
            ends_at=self.future_dt + timedelta(minutes=30),
            modality=Appointment.Modality.IN_PERSON,
            status=Appointment.Status.PENDING_CONFIRMATION,
            price="25.00",
            is_paid=False,
        )

        self.confirmed_unpaid_appointment = Appointment.objects.create(
            patient=self.patient_profile,
            professional=self.prof_profile,
            scheduled_at=self.future_dt + timedelta(hours=1),
            ends_at=self.future_dt + timedelta(hours=1, minutes=30),
            modality=Appointment.Modality.IN_PERSON,
            status=Appointment.Status.CONFIRMED,
            price="25.00",
            is_paid=False,
        )

        self.confirmed_paid_appointment = Appointment.objects.create(
            patient=self.patient_profile,
            professional=self.prof_profile,
            scheduled_at=self.future_dt + timedelta(hours=2),
            ends_at=self.future_dt + timedelta(hours=2, minutes=30),
            modality=Appointment.Modality.IN_PERSON,
            status=Appointment.Status.CONFIRMED,
            price="25.00",
            is_paid=True,
        )

        self.past_confirmed_appointment = Appointment.objects.create(
            patient=self.patient_profile,
            professional=self.prof_profile,
            scheduled_at=self.past_dt,
            ends_at=self.past_dt + timedelta(minutes=30),
            modality=Appointment.Modality.IN_PERSON,
            status=Appointment.Status.CONFIRMED,
            price="25.00",
            is_paid=True,
        )

        self.foreign_appointment = Appointment.objects.create(
            patient=self.patient_profile,
            professional=self.other_prof_profile,
            scheduled_at=self.future_dt + timedelta(hours=3),
            ends_at=self.future_dt + timedelta(hours=3, minutes=30),
            modality=Appointment.Modality.IN_PERSON,
            status=Appointment.Status.PENDING_CONFIRMATION,
            price="25.00",
            is_paid=False,
        )

        self.prof_token = self._login("prof.lifecycle@test.local", "Profesional123!")
        self.patient_token = self._login("patient.lifecycle@test.local", "Paciente123!")

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

    def test_professional_can_confirm_pending_appointment(self):
        response = self.client.post(
            f"/api/v1/professional/appointments/{self.pending_appointment.id}/confirm",
            data=json.dumps({"notes": "Confirmada"}),
            content_type="application/json",
            **self._auth_headers(self.prof_token),
        )
        self.assertEqual(response.status_code, 200)

        self.pending_appointment.refresh_from_db()
        self.assertEqual(
            self.pending_appointment.status,
            Appointment.Status.CONFIRMED,
        )

    def test_professional_can_cancel_unpaid_active_appointment(self):
        response = self.client.post(
            f"/api/v1/professional/appointments/{self.confirmed_unpaid_appointment.id}/cancel",
            data=json.dumps({"reason": "Agenda interna"}),
            content_type="application/json",
            **self._auth_headers(self.prof_token),
        )
        self.assertEqual(response.status_code, 200)

        self.confirmed_unpaid_appointment.refresh_from_db()
        self.assertEqual(
            self.confirmed_unpaid_appointment.status,
            Appointment.Status.CANCELLED_BY_PROFESSIONAL,
        )

    def test_professional_cannot_cancel_paid_appointment(self):
        response = self.client.post(
            f"/api/v1/professional/appointments/{self.confirmed_paid_appointment.id}/cancel",
            data=json.dumps({"reason": "No debería permitir"}),
            content_type="application/json",
            **self._auth_headers(self.prof_token),
        )
        self.assertEqual(response.status_code, 409)

        self.confirmed_paid_appointment.refresh_from_db()
        self.assertEqual(
            self.confirmed_paid_appointment.status,
            Appointment.Status.CONFIRMED,
        )

    def test_professional_can_complete_past_confirmed_appointment(self):
        response = self.client.post(
            f"/api/v1/professional/appointments/{self.past_confirmed_appointment.id}/complete",
            data=json.dumps({"notes": "Consulta realizada"}),
            content_type="application/json",
            **self._auth_headers(self.prof_token),
        )
        self.assertEqual(response.status_code, 200)

        self.past_confirmed_appointment.refresh_from_db()
        self.assertEqual(
            self.past_confirmed_appointment.status,
            Appointment.Status.COMPLETED,
        )

    def test_professional_can_mark_patient_no_show(self):
        response = self.client.post(
            f"/api/v1/professional/appointments/{self.past_confirmed_appointment.id}/mark-no-show-patient",
            data=json.dumps({"reason": "Paciente ausente"}),
            content_type="application/json",
            **self._auth_headers(self.prof_token),
        )
        self.assertEqual(response.status_code, 200)

        self.past_confirmed_appointment.refresh_from_db()
        self.assertEqual(
            self.past_confirmed_appointment.status,
            Appointment.Status.NO_SHOW_PATIENT,
        )

    def test_professional_cannot_touch_foreign_appointment(self):
        response = self.client.post(
            f"/api/v1/professional/appointments/{self.foreign_appointment.id}/confirm",
            **self._auth_headers(self.prof_token),
        )
        self.assertEqual(response.status_code, 404)

    def test_patient_cannot_use_professional_lifecycle_routes(self):
        response = self.client.post(
            f"/api/v1/professional/appointments/{self.pending_appointment.id}/confirm",
            **self._auth_headers(self.patient_token),
        )
        self.assertEqual(response.status_code, 403)

    def test_future_appointment_cannot_be_completed(self):
        response = self.client.post(
            f"/api/v1/professional/appointments/{self.confirmed_unpaid_appointment.id}/complete",
            **self._auth_headers(self.prof_token),
        )
        self.assertEqual(response.status_code, 409)

    def test_professional_list_includes_resolution_summary_for_refunded_appointment(self):
        Payment.objects.create(
            appointment=self.confirmed_paid_appointment,
            external_reference="demo_reference_040",
            amount=self.confirmed_paid_appointment.price,
            currency="USD",
            status=Payment.Status.REFUNDED,
            paid_at=timezone.now(),
            raw_response={
                "decision": "refund_and_cancel_appointment",
                "cancel_as": "professional",
                "refunded_at": timezone.now().isoformat(),
                "appointment_status_after": Appointment.Status.CANCELLED_BY_PROFESSIONAL,
            },
        )

        self.confirmed_paid_appointment.status = Appointment.Status.CANCELLED_BY_PROFESSIONAL
        self.confirmed_paid_appointment.is_paid = False
        self.confirmed_paid_appointment.save(update_fields=["status", "is_paid"])

        response = self.client.get(
            "/api/v1/professional/appointments",
            **self._auth_headers(self.prof_token),
        )
        self.assertEqual(response.status_code, 200)

        items = response.json()["items"]
        target = [item for item in items if item["id"] == self.confirmed_paid_appointment.id][0]

        self.assertEqual(
            target["resolution_summary"]["kind"],
            "refunded_and_cancelled",
        )
        self.assertEqual(
            target["resolution_summary"]["cancelled_as"],
            "professional",
        )
        self.assertEqual(
            target["resolution_summary"]["appointment_status_after"],
            Appointment.Status.CANCELLED_BY_PROFESSIONAL,
        )
