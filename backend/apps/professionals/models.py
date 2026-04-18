from django.db import models
from django.db.models import Q
from django.conf import settings


class ProfessionalProfile(models.Model):
    class VerificationStatus(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        UNDER_REVIEW = "under_review", "Under Review"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        NEEDS_CORRECTION = "needs_correction", "Needs Correction"
        SUSPENDED = "suspended", "Suspended"

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
    office_address = models.CharField(max_length=255, blank=True)
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

    def get_submission_blockers(self) -> list[str]:
        blockers: list[str] = []

        if not self.specialty_id:
            blockers.append("Debe seleccionar la especialidad.")
        if not (self.license_number or "").strip():
            blockers.append("Debe registrar el número de licencia profesional.")
        if not (self.city or "").strip():
            blockers.append("Debe registrar la ciudad.")
        if not (self.province or "").strip():
            blockers.append("Debe registrar la provincia.")
        if not (self.office_address or "").strip():
            blockers.append("Debe registrar la dirección del consultorio para modalidades presenciales.")
        if not (self.user.first_name or "").strip():
            blockers.append("El usuario del profesional debe tener nombres.")
        if not (self.user.last_name or "").strip():
            blockers.append("El usuario del profesional debe tener apellidos.")

        current_doc_types = set(self.documents.values_list("document_type", flat=True))

        if ProfessionalDocument.DocumentType.ID not in current_doc_types:
            blockers.append("Debe subir documento de identidad.")
        if ProfessionalDocument.DocumentType.TITLE not in current_doc_types:
            blockers.append("Debe subir el título profesional.")
        if not (
            ProfessionalDocument.DocumentType.LICENSE in current_doc_types
            or ProfessionalDocument.DocumentType.SENESCYT in current_doc_types
        ):
            blockers.append("Debe subir licencia profesional o documento SENESCYT.")

        rejected_required_docs = self.documents.filter(
            document_type__in=[
                ProfessionalDocument.DocumentType.ID,
                ProfessionalDocument.DocumentType.TITLE,
                ProfessionalDocument.DocumentType.LICENSE,
                ProfessionalDocument.DocumentType.SENESCYT,
            ],
            review_status=ProfessionalDocument.ReviewStatus.REJECTED,
        )
        if rejected_required_docs.exists():
            blockers.append(
                "Existen documentos obligatorios rechazados. Deben corregirse antes de reenviar."
            )

        open_submission_exists = self.verification_submissions.filter(
            status__in=[
                ProfessionalVerificationSubmission.Status.SUBMITTED,
                ProfessionalVerificationSubmission.Status.UNDER_REVIEW,
            ]
        ).exists()
        if open_submission_exists:
            blockers.append("Ya existe una solicitud abierta de validación.")

        return blockers

    def can_submit_for_verification(self) -> bool:
        return len(self.get_submission_blockers()) == 0


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

    def __str__(self):
        return f"{self.professional_id} - {self.document_type}"


class ProfessionalVerificationSubmission(models.Model):
    class Status(models.TextChoices):
        SUBMITTED = "submitted", "Submitted"
        UNDER_REVIEW = "under_review", "Under Review"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        NEEDS_CORRECTION = "needs_correction", "Needs Correction"
        SUSPENDED = "suspended", "Suspended"

    professional = models.ForeignKey(
        ProfessionalProfile,
        on_delete=models.CASCADE,
        related_name="verification_submissions",
    )
    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.SUBMITTED,
    )
    submitted_at = models.DateTimeField(auto_now_add=True)
    assigned_admin = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_professional_verification_submissions",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_professional_verification_submissions",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewer_notes = models.TextField(blank=True)

    class Meta:
        db_table = "professionals_verification_submission"
        indexes = [
            models.Index(fields=["status"], name="idx_verif_status"),
            models.Index(fields=["submitted_at"], name="idx_verif_submitted"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["professional"],
                condition=Q(status__in=["submitted", "under_review"]),
                name="uq_prof_verif_open_submission",
            )
        ]

    def __str__(self):
        return f"Submission {self.id} - {self.professional_id} - {self.status}"


class ProfessionalVerificationEvent(models.Model):
    class EventType(models.TextChoices):
        SUBMITTED = "submitted", "Submitted"
        ASSIGNED = "assigned", "Assigned"
        COMMENT_ADDED = "comment_added", "Comment Added"
        DOCUMENT_APPROVED = "document_approved", "Document Approved"
        DOCUMENT_REJECTED = "document_rejected", "Document Rejected"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        CORRECTION_REQUESTED = "correction_requested", "Correction Requested"
        SUSPENDED = "suspended", "Suspended"

    submission = models.ForeignKey(
        ProfessionalVerificationSubmission,
        on_delete=models.CASCADE,
        related_name="events",
    )
    event_type = models.CharField(max_length=40, choices=EventType.choices)
    event_payload = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="professional_verification_events",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "professionals_verification_event"
        indexes = [
            models.Index(fields=["event_type"], name="idx_verif_event_type"),
            models.Index(fields=["created_at"], name="idx_verif_event_created"),
        ]

    def __str__(self):
        return f"{self.submission_id} - {self.event_type}"
