from django.db import models
from django.conf import settings


class ProfessionalProfile(models.Model):
    class VerificationStatus(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        UNDER_REVIEW = "under_review", "Under Review"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        NEEDS_CORRECTION = "needs_correction", "Needs Correction"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="professional_profile",
    )
    specialty = models.ForeignKey(
        "catalogs.Specialty",
        on_delete=models.PROTECT,
        related_name="professionals",
    )
    license_number = models.CharField(max_length=100, unique=True)
    bio = models.TextField(blank=True)
    city = models.CharField(max_length=120, blank=True)
    province = models.CharField(max_length=120, blank=True)
    public_profile_enabled = models.BooleanField(default=False)
    verification_status = models.CharField(
        max_length=30,
        choices=VerificationStatus.choices,
        default=VerificationStatus.DRAFT,
    )
    consultation_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    teleconsultation_fee = models.DecimalField(
        max_digits=10, decimal_places=2, default=0
    )
    is_accepting_patients = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "professionals_profile"
        indexes = [
            models.Index(fields=["verification_status"], name="idx_prof_verify"),
            models.Index(fields=["city"], name="idx_prof_city"),
            models.Index(fields=["province"], name="idx_prof_province"),
            models.Index(fields=["public_profile_enabled"], name="idx_prof_public"),
        ]

    def __str__(self):
        return f"Profesional: {self.user.email}"


class ProfessionalDocument(models.Model):
    class DocumentType(models.TextChoices):
        ID = "id", "ID"
        TITLE = "title", "Title"
        LICENSE = "license", "License"
        SENESCYT = "senescyt", "Senescyt"
        OTHER = "other", "Other"

    class ReviewStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    professional = models.ForeignKey(
        ProfessionalProfile,
        on_delete=models.CASCADE,
        related_name="documents",
    )
    document_type = models.CharField(max_length=30, choices=DocumentType.choices)
    file_path = models.CharField(max_length=500)
    original_name = models.CharField(max_length=255)
    review_status = models.CharField(
        max_length=30,
        choices=ReviewStatus.choices,
        default=ReviewStatus.PENDING,
    )
    reviewer_notes = models.TextField(blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "professionals_document"
        indexes = [
            models.Index(fields=["document_type"], name="idx_doc_type"),
            models.Index(fields=["review_status"], name="idx_doc_review"),
        ]
