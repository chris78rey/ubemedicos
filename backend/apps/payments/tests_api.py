import json
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.appointments.models import Appointment, AvailabilitySlot
from apps.catalogs.models import Specialty
from apps.patients.models import PatientProfile
from apps.professionals.models import ProfessionalProfile
from .models import Payment


class PaymentDemoApiTests(TestCase):
    def setUp(self):
        User = get_user_model()

        self.admin_user = User.objects.create_user(
            email="admin.payments@test.local",
            password="Admin123!",
            role="admin",
            is_staff=True,
        )
        self.patient_user = User.objects.create_user(
            email="patient.payments@test.local",
            password="Patient123!",
            role="patient",
            is_email_verified=True,
            first_name="Paciente",
            last_name="Pagos",
        )
        self.other_patient_user = User.objects.create_user(
            email="patient.other@test.local",
            password="Patient123!",
            role="patient",
            is_email_verified=True,
            first_name="Otro",
            last_name="Paciente",
        )
        self.prof_user = User.objects.create_user(
            email="professional.payments@test.local",
            password="Professional123!",
            role="professional",
            is_email_verified=True,
            first_name="Ana",
            last_name="Medica",
        )

        specialty = Specialty.objects.create(name="Medicina General")
        self.professional = ProfessionalProfile.objects.create(
            user=self.prof_user,
            specialty=specialty,
            license_number="MED-001",
            city="Quito",
            province="Pichincha",
            verification_status=ProfessionalProfile.VerificationStatus.APPROVED,
            public_profile_enabled=True,
            consultation_fee=25.00,
            teleconsultation_fee=20.00,
        )

        self.patient_profile = PatientProfile.objects.create(user=self.patient_user)
        self.other_patient_profile = PatientProfile.objects.create(user=self.other_patient_user)

        next_day = timezone.now() + timedelta(days=1)
        slot_start = (next_day.replace(hour=9, minute=0, second=0, microsecond=0))
        slot_end = slot_start + timedelta(hours=3)

        AvailabilitySlot.objects.create(
            professional=self.professional,
            weekday=slot_start.weekday(),
            start_time=slot_start.time(),
            end_time=slot_end.time(),
            modality=Appointment.Modality.IN_PERSON,
            is_active=True,
        )

        self.appointment = Appointment.objects.create(
            patient=self.patient_profile,
            professional=self.professional,
            scheduled_at=slot_start,
            ends_at=slot_start + timedelta(minutes=30),
            modality=Appointment.Modality.IN_PERSON,
            status=Appointment.Status.PENDING_CONFIRMATION,
            price=25.00,
            is_paid=False,
        )

        self.other_appointment = Appointment.objects.create(
            patient=self.other_patient_profile,
            professional=self.professional,
            scheduled_at=slot_start + timedelta(minutes=30),
            ends_at=slot_start + timedelta(minutes=60),
            modality=Appointment.Modality.IN_PERSON,
            status=Appointment.Status.PENDING_CONFIRMATION,
            price=25.00,
            is_paid=False,
        )

        self.admin_token = self._login("admin.payments@test.local", "Admin123!")
        self.patient_token = self._login("patient.payments@test.local", "Patient123!")
        self.prof_token = self._login("professional.payments@test.local", "Professional123!")

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

    def test_patient_create_payment_intent_success(self):
        response = self.client.post(
            f"/api/v1/patient/appointments/{self.appointment.id}/payment-intent",
            **self._auth_headers(self.patient_token),
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(Payment.objects.filter(appointment=self.appointment).exists())

    def test_patient_create_payment_intent_is_idempotent_while_pending(self):
        first = self.client.post(
            f"/api/v1/patient/appointments/{self.appointment.id}/payment-intent",
            **self._auth_headers(self.patient_token),
        )
        self.assertEqual(first.status_code, 201)

        second = self.client.post(
            f"/api/v1/patient/appointments/{self.appointment.id}/payment-intent",
            **self._auth_headers(self.patient_token),
        )
        self.assertEqual(second.status_code, 200)
        self.assertEqual(Payment.objects.filter(appointment=self.appointment).count(), 1)

    def test_patient_cannot_create_payment_for_other_patient_appointment(self):
        response = self.client.post(
            f"/api/v1/patient/appointments/{self.other_appointment.id}/payment-intent",
            **self._auth_headers(self.patient_token),
        )
        self.assertEqual(response.status_code, 404)

    def test_admin_mark_payment_succeeded_updates_appointment(self):
        payment = Payment.objects.create(
            appointment=self.appointment,
            external_reference="demo_reference_001",
            amount=self.appointment.price,
            currency="USD",
            status=Payment.Status.PENDING,
        )

        response = self.client.post(
            f"/api/v1/admin/payments/{payment.id}/mark-succeeded",
            data=json.dumps({"notes": "Validado manualmente"}),
            content_type="application/json",
            **self._auth_headers(self.admin_token),
        )
        self.assertEqual(response.status_code, 200)

        payment.refresh_from_db()
        self.appointment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.SUCCEEDED)
        self.assertIsNotNone(payment.paid_at)
        self.assertTrue(self.appointment.is_paid)
        self.assertEqual(self.appointment.status, Appointment.Status.CONFIRMED)

    def test_admin_mark_payment_failed_keeps_appointment_unpaid(self):
        payment = Payment.objects.create(
            appointment=self.appointment,
            external_reference="demo_reference_002",
            amount=self.appointment.price,
            currency="USD",
            status=Payment.Status.PENDING,
        )

        response = self.client.post(
            f"/api/v1/admin/payments/{payment.id}/mark-failed",
            data=json.dumps({"notes": "Tarjeta rechazada en validación demo"}),
            content_type="application/json",
            **self._auth_headers(self.admin_token),
        )
        self.assertEqual(response.status_code, 200)

        payment.refresh_from_db()
        self.appointment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.FAILED)
        self.assertFalse(self.appointment.is_paid)
        self.assertEqual(self.appointment.status, Appointment.Status.PENDING_CONFIRMATION)

    def test_admin_mark_payment_refunded_updates_appointment_as_unpaid(self):
        payment = Payment.objects.create(
            appointment=self.appointment,
            external_reference="demo_reference_006",
            amount=self.appointment.price,
            currency="USD",
            status=Payment.Status.SUCCEEDED,
            paid_at=timezone.now(),
        )

        self.appointment.status = Appointment.Status.CONFIRMED
        self.appointment.is_paid = True
        self.appointment.save(update_fields=["status", "is_paid"])

        response = self.client.post(
            f"/api/v1/admin/payments/{payment.id}/mark-refunded",
            data=json.dumps({"notes": "Reembolso administrativo demo"}),
            content_type="application/json",
            **self._auth_headers(self.admin_token),
        )
        self.assertEqual(response.status_code, 200)

        payment.refresh_from_db()
        self.appointment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.REFUNDED)
        self.assertIsNotNone(payment.paid_at)
        self.assertFalse(self.appointment.is_paid)
        self.assertEqual(self.appointment.status, Appointment.Status.CONFIRMED)

    def test_admin_cannot_refund_non_succeeded_payment(self):
        payment = Payment.objects.create(
            appointment=self.appointment,
            external_reference="demo_reference_007",
            amount=self.appointment.price,
            currency="USD",
            status=Payment.Status.PENDING,
        )

        response = self.client.post(
            f"/api/v1/admin/payments/{payment.id}/mark-refunded",
            data=json.dumps({"notes": "No debe permitir"}),
            content_type="application/json",
            **self._auth_headers(self.admin_token),
        )
        self.assertEqual(response.status_code, 409)

        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.PENDING)

    def test_patient_list_payments(self):
        Payment.objects.create(
            appointment=self.appointment,
            external_reference="demo_reference_003",
            amount=self.appointment.price,
            currency="USD",
            status=Payment.Status.PENDING,
        )
        Payment.objects.create(
            appointment=self.other_appointment,
            external_reference="demo_reference_004",
            amount=self.other_appointment.price,
            currency="USD",
            status=Payment.Status.PENDING,
        )

        response = self.client.get(
            "/api/v1/patient/payments",
            **self._auth_headers(self.patient_token),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["items"]), 1)
        self.assertEqual(response.json()["items"][0]["appointment"]["id"], self.appointment.id)

    def test_failed_payment_can_be_reopened_by_patient(self):
        payment = Payment.objects.create(
            appointment=self.appointment,
            external_reference="demo_reference_005",
            amount=self.appointment.price,
            currency="USD",
            status=Payment.Status.FAILED,
        )

        response = self.client.post(
            f"/api/v1/patient/appointments/{self.appointment.id}/payment-intent",
            **self._auth_headers(self.patient_token),
        )
        self.assertEqual(response.status_code, 200)

        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.PENDING)
        self.assertNotEqual(payment.external_reference, "demo_reference_005")

    def test_refunded_payment_can_be_reopened_by_patient(self):
        payment = Payment.objects.create(
            appointment=self.appointment,
            external_reference="demo_reference_008",
            amount=self.appointment.price,
            currency="USD",
            status=Payment.Status.REFUNDED,
            paid_at=timezone.now(),
        )

        response = self.client.post(
            f"/api/v1/patient/appointments/{self.appointment.id}/payment-intent",
            **self._auth_headers(self.patient_token),
        )
        self.assertEqual(response.status_code, 200)

        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.PENDING)
        self.assertNotEqual(payment.external_reference, "demo_reference_008")

    def test_professional_forbidden_on_admin_payments(self):
        response = self.client.get(
            "/api/v1/admin/payments",
            **self._auth_headers(self.prof_token),
        )
        self.assertEqual(response.status_code, 403)

    def test_admin_refund_and_cancel_paid_appointment_as_patient(self):
        payment = Payment.objects.create(
            appointment=self.appointment,
            external_reference="demo_reference_020",
            amount=self.appointment.price,
            currency="USD",
            status=Payment.Status.SUCCEEDED,
            paid_at=timezone.now(),
        )

        self.appointment.status = Appointment.Status.CONFIRMED
        self.appointment.is_paid = True
        self.appointment.save(update_fields=["status", "is_paid"])

        response = self.client.post(
            f"/api/v1/admin/payments/{payment.id}/refund-and-cancel-appointment",
            data=json.dumps({
                "cancel_as": "patient",
                "notes": "Resolución administrativa unificada",
            }),
            content_type="application/json",
            **self._auth_headers(self.admin_token),
        )
        self.assertEqual(response.status_code, 200)

        payment.refresh_from_db()
        self.appointment.refresh_from_db()

        self.assertEqual(payment.status, Payment.Status.REFUNDED)
        self.assertEqual(
            self.appointment.status,
            Appointment.Status.CANCELLED_BY_PATIENT,
        )
        self.assertFalse(self.appointment.is_paid)

    def test_admin_refund_and_cancel_paid_appointment_as_professional(self):
        payment = Payment.objects.create(
            appointment=self.appointment,
            external_reference="demo_reference_021",
            amount=self.appointment.price,
            currency="USD",
            status=Payment.Status.SUCCEEDED,
            paid_at=timezone.now(),
        )

        self.appointment.status = Appointment.Status.CONFIRMED
        self.appointment.is_paid = True
        self.appointment.save(update_fields=["status", "is_paid"])

        response = self.client.post(
            f"/api/v1/admin/payments/{payment.id}/refund-and-cancel-appointment",
            data=json.dumps({
                "cancel_as": "professional",
                "notes": "Resolución administrativa por agenda",
            }),
            content_type="application/json",
            **self._auth_headers(self.admin_token),
        )
        self.assertEqual(response.status_code, 200)

        payment.refresh_from_db()
        self.appointment.refresh_from_db()

        self.assertEqual(payment.status, Payment.Status.REFUNDED)
        self.assertEqual(
            self.appointment.status,
            Appointment.Status.CANCELLED_BY_PROFESSIONAL,
        )
        self.assertFalse(self.appointment.is_paid)

    def test_admin_cannot_refund_and_cancel_pending_payment(self):
        payment = Payment.objects.create(
            appointment=self.appointment,
            external_reference="demo_reference_022",
            amount=self.appointment.price,
            currency="USD",
            status=Payment.Status.PENDING,
        )

        response = self.client.post(
            f"/api/v1/admin/payments/{payment.id}/refund-and-cancel-appointment",
            data=json.dumps({
                "cancel_as": "patient",
                "notes": "No debe permitir",
            }),
            content_type="application/json",
            **self._auth_headers(self.admin_token),
        )
        self.assertEqual(response.status_code, 409)

        payment.refresh_from_db()
        self.appointment.refresh_from_db()

        self.assertEqual(payment.status, Payment.Status.PENDING)
        self.assertEqual(self.appointment.status, Appointment.Status.PENDING_CONFIRMATION)

    def test_admin_cannot_refund_and_cancel_completed_appointment(self):
        payment = Payment.objects.create(
            appointment=self.appointment,
            external_reference="demo_reference_023",
            amount=self.appointment.price,
            currency="USD",
            status=Payment.Status.SUCCEEDED,
            paid_at=timezone.now(),
        )

        self.appointment.status = Appointment.Status.COMPLETED
        self.appointment.is_paid = True
        self.appointment.save(update_fields=["status", "is_paid"])

        response = self.client.post(
            f"/api/v1/admin/payments/{payment.id}/refund-and-cancel-appointment",
            data=json.dumps({
                "cancel_as": "patient",
                "notes": "No debe permitir cita cerrada",
            }),
            content_type="application/json",
            **self._auth_headers(self.admin_token),
        )
        self.assertEqual(response.status_code, 409)

        payment.refresh_from_db()
        self.appointment.refresh_from_db()

        self.assertEqual(payment.status, Payment.Status.SUCCEEDED)
        self.assertEqual(self.appointment.status, Appointment.Status.COMPLETED)
