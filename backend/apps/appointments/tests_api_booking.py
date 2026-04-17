import json
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.catalogs.models import Specialty
from apps.professionals.models import ProfessionalProfile, ProfessionalDocument
from apps.patients.models import PatientProfile
from .models import AvailabilitySlot, AvailabilityBlock, Appointment


class AppointmentBookingApiTests(TestCase):
    def setUp(self):
        User = get_user_model()

        # Admin for setup
        self.admin = User.objects.create_user(
            email="admin.booking@test.local",
            password="Admin123!",
            role="admin",
            is_staff=True,
        )

        # Professional
        self.prof_user = User.objects.create_user(
            email="prof.booking@test.local",
            password="Pro123456!",
            first_name="Doctor",
            last_name="Booking",
            role="professional",
            is_email_verified=True,
        )
        self.specialty = Specialty.objects.create(name="Cardiología")
        self.prof_profile = ProfessionalProfile.objects.create(
            user=self.prof_user,
            specialty=self.specialty,
            license_number="CARDIO-999",
            verification_status=ProfessionalProfile.VerificationStatus.APPROVED,
            public_profile_enabled=True,
            consultation_fee=50.00,
            teleconsultation_fee=40.00,
        )

        # Patient
        self.pat_user = User.objects.create_user(
            email="pat.booking@test.local",
            password="Pat123456!",
            first_name="Paciente",
            last_name="Pruebas",
            role="patient",
            is_email_verified=True,
        )
        self.pat_profile = PatientProfile.objects.create(user=self.pat_user)

        # Availability for Professional (Monday 08:00 - 12:00)
        # Next Monday
        today = timezone.now().date()
        days_ahead = 0 - today.weekday()
        if days_ahead <= 0: days_ahead += 7
        self.next_monday = today + timedelta(days=days_ahead)

        AvailabilitySlot.objects.create(
            professional=self.prof_profile,
            weekday=0, # Monday
            start_time="08:00",
            end_time="12:00",
            modality="in_person",
            is_active=True,
        )

        # Tokens
        self.pat_token = self._get_token("pat.booking@test.local", "Pat123456!")
        self.prof_token = self._get_token("prof.booking@test.local", "Pro123456!")

    def _get_token(self, email, password):
        login = self.client.post(
            "/api/v1/auth/login",
            data=json.dumps({"email": email, "password": password}),
            content_type="application/json",
        )
        return login.json()["access_token"]

    def _auth_headers(self, token):
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def test_public_professionals_list(self):
        response = self.client.get("/api/v1/professionals/public")
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(len(response.json()["items"]), 1)

    def test_get_available_slots(self):
        url = f"/api/v1/professionals/public/{self.prof_profile.id}/available-slots?date={self.next_monday.isoformat()}&modality=in_person"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        # 08:00 to 12:00 = 8 slots of 30 min
        self.assertEqual(len(response.json()["items"]), 8)

    def test_book_appointment_success(self):
        dt = timezone.make_aware(timezone.datetime.combine(self.next_monday, timezone.datetime.strptime("09:00", "%H:%M").time()))
        response = self.client.post(
            "/api/v1/patient/appointments",
            data=json.dumps({
                "professional_id": self.prof_profile.id,
                "scheduled_at": dt.isoformat(),
                "modality": "in_person",
                "notes": "Test appointment"
            }),
            content_type="application/json",
            **self._auth_headers(self.pat_token)
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(Appointment.objects.filter(patient=self.pat_profile).exists())

    def test_book_appointment_conflict(self):
        dt = timezone.make_aware(timezone.datetime.combine(self.next_monday, timezone.datetime.strptime("09:00", "%H:%M").time()))
        # Create one first
        Appointment.objects.create(
            patient=self.pat_profile,
            professional=self.prof_profile,
            scheduled_at=dt,
            ends_at=dt + timedelta(minutes=30),
            modality="in_person",
            status=Appointment.Status.CONFIRMED,
            price=50.00
        )

        # Try to book same slot
        response = self.client.post(
            "/api/v1/patient/appointments",
            data=json.dumps({
                "professional_id": self.prof_profile.id,
                "scheduled_at": dt.isoformat(),
                "modality": "in_person",
            }),
            content_type="application/json",
            **self._auth_headers(self.pat_token)
        )
        self.assertEqual(response.status_code, 409)

    def test_cancel_appointment(self):
        dt = timezone.make_aware(
            timezone.datetime.combine(
                self.next_monday,
                timezone.datetime.strptime("10:00", "%H:%M").time(),
            )
        )
        app = Appointment.objects.create(
            patient=self.pat_profile,
            professional=self.prof_profile,
            scheduled_at=dt,
            ends_at=dt + timedelta(minutes=30),
            modality="in_person",
            status=Appointment.Status.CONFIRMED,
            price=50.00,
            is_paid=False,
        )

        response = self.client.post(
            f"/api/v1/patient/appointments/{app.id}/cancel",
            **self._auth_headers(self.pat_token)
        )
        self.assertEqual(response.status_code, 200)

        app.refresh_from_db()
        self.assertEqual(app.status, Appointment.Status.CANCELLED_BY_PATIENT)

    def test_cannot_cancel_paid_appointment(self):
        dt = timezone.make_aware(
            timezone.datetime.combine(
                self.next_monday,
                timezone.datetime.strptime("10:30", "%H:%M").time(),
            )
        )
        app = Appointment.objects.create(
            patient=self.pat_profile,
            professional=self.prof_profile,
            scheduled_at=dt,
            ends_at=dt + timedelta(minutes=30),
            modality="in_person",
            status=Appointment.Status.CONFIRMED,
            price=50.00,
            is_paid=True,
        )

        response = self.client.post(
            f"/api/v1/patient/appointments/{app.id}/cancel",
            **self._auth_headers(self.pat_token)
        )
        self.assertEqual(response.status_code, 409)

        app.refresh_from_db()
        self.assertEqual(app.status, Appointment.Status.CONFIRMED)

    def test_professional_list_appointments(self):
        response = self.client.get(
            "/api/v1/professional/appointments",
            **self._auth_headers(self.prof_token)
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("items", response.json())
