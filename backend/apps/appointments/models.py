from django.db import models


class AvailabilitySlot(models.Model):
    class Modality(models.TextChoices):
        IN_PERSON = "in_person", "In Person"
        TELECONSULTATION = "teleconsultation", "Teleconsultation"

    professional = models.ForeignKey(
        "professionals.ProfessionalProfile",
        on_delete=models.CASCADE,
        related_name="availability_slots",
    )
    weekday = models.PositiveSmallIntegerField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    modality = models.CharField(max_length=30, choices=Modality.choices)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "appointments_availability_slot"
        indexes = [
            models.Index(fields=["professional", "weekday"], name="idx_slot_prof_day"),
            models.Index(fields=["modality"], name="idx_slot_modality"),
        ]


class AvailabilityBlock(models.Model):
    professional = models.ForeignKey(
        "professionals.ProfessionalProfile",
        on_delete=models.CASCADE,
        related_name="availability_blocks",
    )
    start_at = models.DateTimeField()
    end_at = models.DateTimeField()
    reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "appointments_availability_block"
        indexes = [
            models.Index(
                fields=["professional", "start_at"], name="idx_block_prof_start"
            ),
        ]


class Appointment(models.Model):
    class Status(models.TextChoices):
        PENDING_CONFIRMATION = "pending_confirmation", "Pending Confirmation"
        CONFIRMED = "confirmed", "Confirmed"
        CANCELLED_BY_PATIENT = "cancelled_by_patient", "Cancelled by Patient"
        CANCELLED_BY_PROFESSIONAL = (
            "cancelled_by_professional",
            "Cancelled by Professional",
        )
        COMPLETED = "completed", "Completed"
        NO_SHOW_PATIENT = "no_show_patient", "No Show Patient"
        NO_SHOW_PROFESSIONAL = "no_show_professional", "No Show Professional"

    class Modality(models.TextChoices):
        IN_PERSON = "in_person", "In Person"
        TELECONSULTATION = "teleconsultation", "Teleconsultation"

    patient = models.ForeignKey(
        "patients.PatientProfile",
        on_delete=models.PROTECT,
        related_name="appointments",
    )
    professional = models.ForeignKey(
        "professionals.ProfessionalProfile",
        on_delete=models.PROTECT,
        related_name="appointments",
    )
    scheduled_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    modality = models.CharField(max_length=30, choices=Modality.choices)
    status = models.CharField(
        max_length=40,
        choices=Status.choices,
        default=Status.PENDING_CONFIRMATION,
    )
    notes = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_paid = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "appointments_appointment"
        indexes = [
            models.Index(
                fields=["professional", "scheduled_at"], name="idx_app_prof_time"
            ),
            models.Index(
                fields=["patient", "scheduled_at"], name="idx_app_patient_time"
            ),
            models.Index(fields=["status"], name="idx_app_status"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["professional", "scheduled_at"],
                name="uq_professional_slot_once",
            )
        ]
