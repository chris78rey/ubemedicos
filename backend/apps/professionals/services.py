from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.audits.models import AuditEvent
from .models import (
    ProfessionalProfile,
    ProfessionalDocument,
    ProfessionalVerificationSubmission,
    ProfessionalVerificationEvent,
)


def _create_audit(
    *, actor, event_type: str, entity_type: str, entity_id: str, metadata: dict
):
    AuditEvent.objects.create(
        actor=actor,
        event_type=event_type,
        entity_type=entity_type,
        entity_id=str(entity_id),
        metadata=metadata or {},
    )


def _create_submission_event(
    *, submission, actor, event_type: str, payload: dict | None = None
):
    ProfessionalVerificationEvent.objects.create(
        submission=submission,
        event_type=event_type,
        event_payload=payload or {},
        created_by=actor,
    )


def _required_document_statuses(professional: ProfessionalProfile) -> dict:
    docs = {
        doc.document_type: doc.review_status for doc in professional.documents.all()
    }

    has_license_or_senescyt_approved = (
        docs.get(ProfessionalDocument.DocumentType.LICENSE)
        == ProfessionalDocument.ReviewStatus.APPROVED
        or docs.get(ProfessionalDocument.DocumentType.SENESCYT)
        == ProfessionalDocument.ReviewStatus.APPROVED
    )

    has_license_or_senescyt_pending = (
        docs.get(ProfessionalDocument.DocumentType.LICENSE)
        == ProfessionalDocument.ReviewStatus.PENDING
        or docs.get(ProfessionalDocument.DocumentType.SENESCYT)
        == ProfessionalDocument.ReviewStatus.PENDING
    )

    has_license_or_senescyt_rejected = (
        docs.get(ProfessionalDocument.DocumentType.LICENSE)
        == ProfessionalDocument.ReviewStatus.REJECTED
        or docs.get(ProfessionalDocument.DocumentType.SENESCYT)
        == ProfessionalDocument.ReviewStatus.REJECTED
    )

    return {
        "id": docs.get(ProfessionalDocument.DocumentType.ID),
        "title": docs.get(ProfessionalDocument.DocumentType.TITLE),
        "has_license_or_senescyt_approved": has_license_or_senescyt_approved,
        "has_license_or_senescyt_pending": has_license_or_senescyt_pending,
        "has_license_or_senescyt_rejected": has_license_or_senescyt_rejected,
    }


@transaction.atomic
def submit_professional_for_verification(*, professional: ProfessionalProfile, actor):
    allowed_source_statuses = {
        ProfessionalProfile.VerificationStatus.DRAFT,
        ProfessionalProfile.VerificationStatus.REJECTED,
        ProfessionalProfile.VerificationStatus.NEEDS_CORRECTION,
    }

    if professional.verification_status not in allowed_source_statuses:
        raise ValidationError(
            [
                "Solo se puede enviar a validación desde draft, rejected o needs_correction."
            ]
        )

    blockers = professional.get_submission_blockers()
    if blockers:
        raise ValidationError(blockers)

    previous_status = professional.verification_status

    professional.verification_status = ProfessionalProfile.VerificationStatus.SUBMITTED
    professional.public_profile_enabled = False
    professional.save(
        update_fields=["verification_status", "public_profile_enabled", "updated_at"]
    )

    submission = ProfessionalVerificationSubmission.objects.create(
        professional=professional,
        status=ProfessionalVerificationSubmission.Status.SUBMITTED,
    )

    _create_submission_event(
        submission=submission,
        actor=actor,
        event_type=ProfessionalVerificationEvent.EventType.SUBMITTED,
        payload={
            "professional_id": professional.id,
            "professional_email": professional.user.email,
            "document_count": professional.documents.count(),
        },
    )

    _create_audit(
        actor=actor,
        event_type="professional_verification_submitted",
        entity_type="ProfessionalVerificationSubmission",
        entity_id=submission.id,
        metadata={
            "professional_id": professional.id,
            "professional_status_before": previous_status,
            "professional_status_after": professional.verification_status,
            "public_profile_enabled": professional.public_profile_enabled,
        },
    )

    return submission


@transaction.atomic
def assign_verification_submission(
    *, submission: ProfessionalVerificationSubmission, actor, assignee
):
    if submission.status not in {
        ProfessionalVerificationSubmission.Status.SUBMITTED,
        ProfessionalVerificationSubmission.Status.UNDER_REVIEW,
    }:
        raise ValidationError(["Solo se puede asignar una solicitud abierta."])

    submission.assigned_admin = assignee
    submission.save(update_fields=["assigned_admin"])

    _create_submission_event(
        submission=submission,
        actor=actor,
        event_type=ProfessionalVerificationEvent.EventType.ASSIGNED,
        payload={
            "assigned_admin_id": assignee.id if assignee else None,
            "assigned_admin_email": assignee.email if assignee else None,
        },
    )

    _create_audit(
        actor=actor,
        event_type="professional_verification_assigned",
        entity_type="ProfessionalVerificationSubmission",
        entity_id=submission.id,
        metadata={
            "professional_id": submission.professional_id,
            "assigned_admin_id": assignee.id if assignee else None,
        },
    )

    return submission


@transaction.atomic
def start_verification_review(*, submission: ProfessionalVerificationSubmission, actor):
    if submission.status != ProfessionalVerificationSubmission.Status.SUBMITTED:
        raise ValidationError(
            ["Solo una solicitud submitted puede pasar a under_review."]
        )

    submission.status = ProfessionalVerificationSubmission.Status.UNDER_REVIEW
    if submission.assigned_admin_id is None:
        submission.assigned_admin = actor
    submission.save(update_fields=["status", "assigned_admin"])

    professional = submission.professional
    professional.verification_status = (
        ProfessionalProfile.VerificationStatus.UNDER_REVIEW
    )
    professional.save(update_fields=["verification_status", "updated_at"])

    _create_submission_event(
        submission=submission,
        actor=actor,
        event_type=ProfessionalVerificationEvent.EventType.COMMENT_ADDED,
        payload={"message": "Solicitud pasada a revisión administrativa."},
    )

    _create_audit(
        actor=actor,
        event_type="professional_verification_under_review",
        entity_type="ProfessionalVerificationSubmission",
        entity_id=submission.id,
        metadata={"professional_id": professional.id},
    )

    return submission


@transaction.atomic
def review_professional_document(
    *,
    submission: ProfessionalVerificationSubmission,
    document: ProfessionalDocument,
    actor,
    decision: str,
    notes: str = "",
):
    if submission.status not in {
        ProfessionalVerificationSubmission.Status.SUBMITTED,
        ProfessionalVerificationSubmission.Status.UNDER_REVIEW,
    }:
        raise ValidationError(
            ["Solo se pueden revisar documentos de solicitudes abiertas."]
        )

    if document.professional_id != submission.professional_id:
        raise ValidationError(
            ["El documento no pertenece al profesional de la solicitud."]
        )

    if decision not in {
        ProfessionalDocument.ReviewStatus.APPROVED,
        ProfessionalDocument.ReviewStatus.REJECTED,
    }:
        raise ValidationError(
            ["La decisión del documento debe ser approved o rejected."]
        )

    document.review_status = decision
    document.reviewer_notes = (notes or "").strip()
    document.reviewed_at = timezone.now()
    document.save(update_fields=["review_status", "reviewer_notes", "reviewed_at"])

    event_type = (
        ProfessionalVerificationEvent.EventType.DOCUMENT_APPROVED
        if decision == ProfessionalDocument.ReviewStatus.APPROVED
        else ProfessionalVerificationEvent.EventType.DOCUMENT_REJECTED
    )

    _create_submission_event(
        submission=submission,
        actor=actor,
        event_type=event_type,
        payload={
            "document_id": document.id,
            "document_type": document.document_type,
            "review_status": document.review_status,
            "reviewer_notes": document.reviewer_notes,
        },
    )

    _create_audit(
        actor=actor,
        event_type="professional_document_reviewed",
        entity_type="ProfessionalDocument",
        entity_id=document.id,
        metadata={
            "submission_id": submission.id,
            "professional_id": submission.professional_id,
            "decision": decision,
            "document_type": document.document_type,
        },
    )

    return document


@transaction.atomic
def request_submission_correction(
    *, submission: ProfessionalVerificationSubmission, actor, notes: str
):
    if submission.status not in {
        ProfessionalVerificationSubmission.Status.SUBMITTED,
        ProfessionalVerificationSubmission.Status.UNDER_REVIEW,
    }:
        raise ValidationError(
            ["Solo se puede pedir corrección sobre solicitudes abiertas."]
        )

    cleaned_notes = (notes or "").strip()
    if not cleaned_notes:
        raise ValidationError(
            ["La solicitud de corrección debe incluir observaciones."]
        )

    submission.status = ProfessionalVerificationSubmission.Status.NEEDS_CORRECTION
    submission.reviewed_by = actor
    submission.reviewed_at = timezone.now()
    submission.reviewer_notes = cleaned_notes
    submission.save(
        update_fields=["status", "reviewed_by", "reviewed_at", "reviewer_notes"]
    )

    professional = submission.professional
    professional.verification_status = (
        ProfessionalProfile.VerificationStatus.NEEDS_CORRECTION
    )
    professional.public_profile_enabled = False
    professional.save(
        update_fields=["verification_status", "public_profile_enabled", "updated_at"]
    )

    _create_submission_event(
        submission=submission,
        actor=actor,
        event_type=ProfessionalVerificationEvent.EventType.CORRECTION_REQUESTED,
        payload={"reviewer_notes": cleaned_notes},
    )

    _create_audit(
        actor=actor,
        event_type="professional_verification_correction_requested",
        entity_type="ProfessionalVerificationSubmission",
        entity_id=submission.id,
        metadata={
            "professional_id": professional.id,
            "reviewer_notes": cleaned_notes,
        },
    )

    return submission


@transaction.atomic
def approve_verification_submission(
    *, submission: ProfessionalVerificationSubmission, actor, notes: str = ""
):
    if submission.status not in {
        ProfessionalVerificationSubmission.Status.SUBMITTED,
        ProfessionalVerificationSubmission.Status.UNDER_REVIEW,
    }:
        raise ValidationError(["Solo se puede aprobar una solicitud abierta."])

    professional = submission.professional
    doc_matrix = _required_document_statuses(professional)

    blockers = []
    if doc_matrix["id"] != ProfessionalDocument.ReviewStatus.APPROVED:
        blockers.append("El documento de identidad debe estar aprobado.")
    if doc_matrix["title"] != ProfessionalDocument.ReviewStatus.APPROVED:
        blockers.append("El título profesional debe estar aprobado.")
    if not doc_matrix["has_license_or_senescyt_approved"]:
        if doc_matrix["has_license_or_senescyt_pending"]:
            blockers.append("Licencia profesional o SENESCYT sigue pendiente.")
        elif doc_matrix["has_license_or_senescyt_rejected"]:
            blockers.append("Licencia profesional o SENESCYT fue rechazado.")
        else:
            blockers.append("Debe existir licencia profesional o SENESCYT aprobado.")

    if blockers:
        raise ValidationError(blockers)

    submission.status = ProfessionalVerificationSubmission.Status.APPROVED
    submission.reviewed_by = actor
    submission.reviewed_at = timezone.now()
    submission.reviewer_notes = (notes or "").strip()
    submission.save(
        update_fields=["status", "reviewed_by", "reviewed_at", "reviewer_notes"]
    )

    professional.verification_status = ProfessionalProfile.VerificationStatus.APPROVED
    professional.public_profile_enabled = False
    professional.save(
        update_fields=["verification_status", "public_profile_enabled", "updated_at"]
    )

    _create_submission_event(
        submission=submission,
        actor=actor,
        event_type=ProfessionalVerificationEvent.EventType.APPROVED,
        payload={"reviewer_notes": submission.reviewer_notes},
    )

    _create_audit(
        actor=actor,
        event_type="professional_verification_approved",
        entity_type="ProfessionalVerificationSubmission",
        entity_id=submission.id,
        metadata={"professional_id": professional.id},
    )

    return submission


@transaction.atomic
def reject_verification_submission(
    *, submission: ProfessionalVerificationSubmission, actor, notes: str
):
    if submission.status not in {
        ProfessionalVerificationSubmission.Status.SUBMITTED,
        ProfessionalVerificationSubmission.Status.UNDER_REVIEW,
    }:
        raise ValidationError(["Solo se puede rechazar una solicitud abierta."])

    cleaned_notes = (notes or "").strip()
    if not cleaned_notes:
        raise ValidationError(["El rechazo debe incluir observaciones."])

    submission.status = ProfessionalVerificationSubmission.Status.REJECTED
    submission.reviewed_by = actor
    submission.reviewed_at = timezone.now()
    submission.reviewer_notes = cleaned_notes
    submission.save(
        update_fields=["status", "reviewed_by", "reviewed_at", "reviewer_notes"]
    )

    professional = submission.professional
    professional.verification_status = ProfessionalProfile.VerificationStatus.REJECTED
    professional.public_profile_enabled = False
    professional.save(
        update_fields=["verification_status", "public_profile_enabled", "updated_at"]
    )

    _create_submission_event(
        submission=submission,
        actor=actor,
        event_type=ProfessionalVerificationEvent.EventType.REJECTED,
        payload={"reviewer_notes": cleaned_notes},
    )

    _create_audit(
        actor=actor,
        event_type="professional_verification_rejected",
        entity_type="ProfessionalVerificationSubmission",
        entity_id=submission.id,
        metadata={
            "professional_id": professional.id,
            "reviewer_notes": cleaned_notes,
        },
    )

    return submission
