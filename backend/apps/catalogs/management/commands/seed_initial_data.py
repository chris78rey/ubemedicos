from decimal import Decimal
from datetime import time
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from apps.catalogs.models import Specialty
from apps.patients.models import PatientProfile
from apps.professionals.models import (
    ProfessionalProfile,
    ProfessionalVerificationSubmission,
)
from apps.appointments.models import AvailabilitySlot


SPECIALTIES = [
    "Medicina General",
    "Pediatría",
    "Ginecología",
    "Cardiología",
    "Dermatología",
    "Traumatología",
    "Psicología",
    "Nutrición",
]

DEMO_USERS = {
    "super_admin": {
        "email": "superadmin@demo.local",
        "password": "Admin123!",
        "first_name": "Super",
        "last_name": "Admin",
        "role": "super_admin",
        "is_staff": True,
        "is_superuser": True,
        "is_email_verified": True,
    },
    "admin": {
        "email": "admin@demo.local",
        "password": "Admin123!",
        "first_name": "Admin",
        "last_name": "Operativo",
        "role": "admin",
        "is_staff": True,
        "is_superuser": False,
        "is_email_verified": True,
    },
    "privacy_auditor": {
        "email": "privacy@demo.local",
        "password": "Privacy123!",
        "first_name": "Auditor",
        "last_name": "Privacidad",
        "role": "privacy_auditor",
        "is_staff": True,
        "is_superuser": False,
        "is_email_verified": True,
    },
    "patient": {
        "email": "paciente@demo.local",
        "password": "Paciente123!",
        "first_name": "Paciente",
        "last_name": "Demo",
        "role": "patient",
        "is_staff": False,
        "is_superuser": False,
        "is_email_verified": True,
    },
    "professional": {
        "email": "profesional@demo.local",
        "password": "Profesional123!",
        "first_name": "Carla",
        "last_name": "Mendoza",
        "role": "professional",
        "is_staff": False,
        "is_superuser": False,
        "is_email_verified": True,
    },
}

DEMO_LICENSE = "DEMO-MED-0001"


class Command(BaseCommand):
    help = "Carga catálogos y datos demo iniciales de manera idempotente"

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset-demo",
            action="store_true",
            help="Elimina solamente los datos demo creados por este comando",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options["reset_demo"]:
            self._reset_demo()
            self.stdout.write(
                self.style.SUCCESS("Datos demo eliminados correctamente.")
            )
            return

        self._seed_specialties()
        created_users = self._seed_users()
        self._seed_patient_profile(created_users["patient"])
        self._seed_professional_profile(
            created_users["professional"], created_users["admin"]
        )

        self.stdout.write(self.style.SUCCESS("Carga inicial completada correctamente."))
        self.stdout.write("")
        self.stdout.write("Credenciales demo:")
        self.stdout.write("  superadmin@demo.local / Admin123!")
        self.stdout.write("  admin@demo.local / Admin123!")
        self.stdout.write("  privacy@demo.local / Privacy123!")
        self.stdout.write("  paciente@demo.local / Paciente123!")
        self.stdout.write("  profesional@demo.local / Profesional123!")

    def _seed_specialties(self):
        for specialty_name in SPECIALTIES:
            Specialty.objects.get_or_create(
                name=specialty_name,
                defaults={"is_active": True},
            )

    def _seed_users(self):
        User = get_user_model()
        users = {}

        for key, payload in DEMO_USERS.items():
            email = payload["email"]
            password = payload["password"]

            defaults = {
                "first_name": payload["first_name"],
                "last_name": payload["last_name"],
                "role": payload["role"],
                "is_staff": payload["is_staff"],
                "is_superuser": payload["is_superuser"],
                "is_active": True,
                "is_email_verified": payload["is_email_verified"],
            }

            user, _ = User.objects.update_or_create(
                email=email,
                defaults=defaults,
            )

            user.set_password(password)
            user.save(update_fields=["password"])

            users[key] = user

        return users

    def _seed_patient_profile(self, patient_user):
        PatientProfile.objects.update_or_create(
            user=patient_user,
            defaults={
                "gender": "F",
                "national_id": "DEMO-PAC-0001",
                "emergency_contact_name": "Contacto Demo",
                "emergency_contact_phone": "0999999999",
            },
        )

    def _seed_professional_profile(self, professional_user, admin_user):
        specialty = Specialty.objects.get(name="Medicina General")

        profile, _ = ProfessionalProfile.objects.update_or_create(
            user=professional_user,
            defaults={
                "specialty": specialty,
                "license_number": DEMO_LICENSE,
                "bio": "Profesional demo para validación inicial del sistema.",
                "city": "Quito",
                "province": "Pichincha",
                "public_profile_enabled": True,
                "verification_status": ProfessionalProfile.VerificationStatus.APPROVED,
                "consultation_fee": Decimal("25.00"),
                "teleconsultation_fee": Decimal("20.00"),
                "is_accepting_patients": True,
            },
        )

        ProfessionalVerificationSubmission.objects.update_or_create(
            professional=profile,
            status=ProfessionalProfile.VerificationStatus.APPROVED,
            defaults={
                "reviewed_by": admin_user,
                "reviewed_at": timezone.now(),
                "reviewer_notes": "Aprobación demo inicial.",
            },
        )

        demo_slots = [
            {
                "weekday": 0,
                "start_time": time(8, 0),
                "end_time": time(12, 0),
                "modality": AvailabilitySlot.Modality.IN_PERSON,
            },
            {
                "weekday": 1,
                "start_time": time(14, 0),
                "end_time": time(18, 0),
                "modality": AvailabilitySlot.Modality.TELECONSULTATION,
            },
            {
                "weekday": 3,
                "start_time": time(9, 0),
                "end_time": time(13, 0),
                "modality": AvailabilitySlot.Modality.IN_PERSON,
            },
            {
                "weekday": 4,
                "start_time": time(15, 0),
                "end_time": time(19, 0),
                "modality": AvailabilitySlot.Modality.TELECONSULTATION,
            },
        ]

        for slot in demo_slots:
            AvailabilitySlot.objects.update_or_create(
                professional=profile,
                weekday=slot["weekday"],
                start_time=slot["start_time"],
                end_time=slot["end_time"],
                modality=slot["modality"],
                defaults={"is_active": True},
            )

    def _reset_demo(self):
        User = get_user_model()

        professional_user = User.objects.filter(
            email=DEMO_USERS["professional"]["email"]
        ).first()
        if professional_user:
            professional_profile = ProfessionalProfile.objects.filter(
                user=professional_user
            ).first()
            if professional_profile:
                AvailabilitySlot.objects.filter(
                    professional=professional_profile
                ).delete()
                ProfessionalVerificationSubmission.objects.filter(
                    professional=professional_profile
                ).delete()
                professional_profile.delete()

        patient_user = User.objects.filter(email=DEMO_USERS["patient"]["email"]).first()
        if patient_user:
            PatientProfile.objects.filter(user=patient_user).delete()

        demo_emails = [payload["email"] for payload in DEMO_USERS.values()]
        User.objects.filter(email__in=demo_emails).delete()
