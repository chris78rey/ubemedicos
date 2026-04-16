from django.db import models
from django.conf import settings


class PatientProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="patient_profile",
    )
    birth_date = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=30, blank=True)
    national_id = models.CharField(max_length=30, blank=True)
    emergency_contact_name = models.CharField(max_length=120, blank=True)
    emergency_contact_phone = models.CharField(max_length=30, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "patients_profile"
        indexes = [
            models.Index(fields=["national_id"], name="idx_patient_nid"),
        ]

    def __str__(self):
        return f"Paciente: {self.user.email}"
