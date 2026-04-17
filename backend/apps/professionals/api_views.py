import os
import uuid
from pathlib import Path

from django.core.files.uploadedfile import UploadedFile
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from apps.users.api_auth import api_roles_required
from .models import (
    ProfessionalProfile,
    ProfessionalDocument,
    ProfessionalVerificationSubmission,
    ProfessionalVerificationEvent,
)
from .services import submit_professional_for_verification


BASE_BACKEND_DIR = Path(__file__).resolve().parents[2]
PROFESSIONAL_UPLOADS_DIR = BASE_BACKEND_DIR / "media" / "professional_documents"


def _json_error(message, status=400, extra=None):
    payload = {"detail": message}
    if extra:
        payload.update(extra)
    return JsonResponse(payload, status=status)


def _get_professional_profile(user):
    try:
        return user.professional_profile
    except ProfessionalProfile.DoesNotExist:
        return None


def _serialize_document(doc: ProfessionalDocument):
    return {
        "id": doc.id,
        "document_type": doc.document_type,
        "file_path": doc.file_path,
        "original_name": doc.original_name,
        "review_status": doc.review_status,
        "reviewer_notes": doc.reviewer_notes,
        "uploaded_at": doc.uploaded_at.isoformat() if doc.uploaded_at else None,
        "reviewed_at": doc.reviewed_at.isoformat() if doc.reviewed_at else None,
    }


def _serialize_submission(submission: ProfessionalVerificationSubmission):
    return {
        "id": submission.id,
        "status": submission.status,
        "submitted_at": submission.submitted_at.isoformat()
        if submission.submitted_at
        else None,
        "assigned_admin_id": submission.assigned_admin_id,
        "reviewed_by_id": submission.reviewed_by_id,
        "reviewed_at": submission.reviewed_at.isoformat()
        if submission.reviewed_at
        else None,
        "reviewer_notes": submission.reviewer_notes,
    }


def _serialize_event(event: ProfessionalVerificationEvent):
    return {
        "id": event.id,
        "event_type": event.event_type,
        "event_payload": event.event_payload,
        "created_by_id": event.created_by_id,
        "created_at": event.created_at.isoformat() if event.created_at else None,
    }


def _allowed_document_types():
    return {choice[0] for choice in ProfessionalDocument.DocumentType.choices}


def _write_uploaded_file(professional_id: int, uploaded_file: UploadedFile) -> str:
    suffix = Path(uploaded_file.name).suffix or ".bin"
    target_dir = PROFESSIONAL_UPLOADS_DIR / str(professional_id)
    target_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{timezone.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex}{suffix}"
    full_path = target_dir / filename

    with open(full_path, "wb+") as destination:
        for chunk in uploaded_file.chunks():
            destination.write(chunk)

    return str(full_path)


@require_http_methods(["GET"])
@api_roles_required("professional")
def professional_verification_status_view(request):
    professional = _get_professional_profile(request.api_user)
    if not professional:
        return _json_error("El usuario no tiene perfil profesional.", status=404)

    latest_submission = professional.verification_submissions.order_by("-submitted_at").first()

    return JsonResponse(
        {
            "profile": {
                "professional_id": professional.id,
                "verification_status": professional.verification_status,
                "public_profile_enabled": professional.public_profile_enabled,
                "can_submit_for_verification": professional.can_submit_for_verification(),
                "submission_blockers": professional.get_submission_blockers(),
                "specialty_id": professional.specialty_id,
                "license_number": professional.license_number,
                "city": professional.city,
                "province": professional.province,
            },
            "latest_submission": _serialize_submission(latest_submission)
            if latest_submission
            else None,
        },
        status=200,
    )


@require_http_methods(["GET", "POST"])
@api_roles_required("professional")
def professional_documents_collection_view(request):
    professional = _get_professional_profile(request.api_user)
    if not professional:
        return _json_error("El usuario no tiene perfil profesional.", status=404)

    if request.method == "GET":
        documents = professional.documents.order_by("-uploaded_at", "-id")
        return JsonResponse(
            {
                "items": [_serialize_document(doc) for doc in documents],
            },
            status=200,
        )

    document_type = (request.POST.get("document_type") or "").strip()
    uploaded_file = request.FILES.get("file")

    if document_type not in _allowed_document_types():
        return _json_error(
            "document_type inválido.",
            status=400,
            extra={"allowed_document_types": sorted(_allowed_document_types())},
        )

    if uploaded_file is None:
        return _json_error("file es obligatorio.", status=400)

    saved_path = _write_uploaded_file(professional.id, uploaded_file)

    # Regla conservadora:
    # - Para documentos obligatorios y SENESCYT se reutiliza un solo registro por tipo.
    # - Para OTHER se permite crear varios registros.
    if document_type == ProfessionalDocument.DocumentType.OTHER:
        document = ProfessionalDocument.objects.create(
            professional=professional,
            document_type=document_type,
            file_path=saved_path,
            original_name=uploaded_file.name,
            review_status=ProfessionalDocument.ReviewStatus.PENDING,
            reviewer_notes="",
            reviewed_at=None,
        )
    else:
        document, _ = ProfessionalDocument.objects.update_or_create(
            professional=professional,
            document_type=document_type,
            defaults={
                "file_path": saved_path,
                "original_name": uploaded_file.name,
                "review_status": ProfessionalDocument.ReviewStatus.PENDING,
                "reviewer_notes": "",
                "reviewed_at": None,
            },
        )

    return JsonResponse(_serialize_document(document), status=201)


@require_http_methods(["PATCH"])
@api_roles_required("professional")
def professional_document_replace_view(request, document_id: int):
    professional = _get_professional_profile(request.api_user)
    if not professional:
        return _json_error("El usuario no tiene perfil profesional.", status=404)

    try:
        document = ProfessionalDocument.objects.get(
            id=document_id,
            professional=professional,
        )
    except ProfessionalDocument.DoesNotExist:
        return _json_error("Documento no encontrado.", status=404)

    uploaded_file = request.FILES.get("file")
    if uploaded_file is None:
        return _json_error("file es obligatorio.", status=400)

    saved_path = _write_uploaded_file(professional.id, uploaded_file)

    document.file_path = saved_path
    document.original_name = uploaded_file.name
    document.review_status = ProfessionalDocument.ReviewStatus.PENDING
    document.reviewer_notes = ""
    document.reviewed_at = None
    document.save(
        update_fields=[
            "file_path",
            "original_name",
            "review_status",
            "reviewer_notes",
            "reviewed_at",
        ]
    )

    return JsonResponse(_serialize_document(document), status=200)


@require_http_methods(["POST"])
@api_roles_required("professional")
def professional_verification_submit_view(request):
    professional = _get_professional_profile(request.api_user)
    if not professional:
        return _json_error("El usuario no tiene perfil profesional.", status=404)

    try:
        submission = submit_professional_for_verification(
            professional=professional,
            actor=request.api_user,
        )
    except ValidationError as exc:
        messages = list(exc.messages) if hasattr(exc, "messages") else [str(exc)]
        return JsonResponse(
            {
                "detail": "No se pudo enviar a revisión.",
                "errors": messages,
                "submission_blockers": professional.get_submission_blockers(),
            },
            status=400,
        )

    return JsonResponse(
        {
            "detail": "Expediente enviado a revisión correctamente.",
            "submission": _serialize_submission(submission),
        },
        status=201,
    )


@require_http_methods(["GET"])
@api_roles_required("professional")
def professional_verification_events_view(request):
    professional = _get_professional_profile(request.api_user)
    if not professional:
        return _json_error("El usuario no tiene perfil profesional.", status=404)

    events = ProfessionalVerificationEvent.objects.filter(
        submission__professional=professional
    ).order_by("-created_at", "-id")

    return JsonResponse(
        {
            "items": [_serialize_event(event) for event in events],
        },
        status=200,
    )
