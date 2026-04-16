import json
import uuid
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.storage import FileSystemStorage
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils.text import slugify
from django.views.decorators.http import require_http_methods

from apps.catalogs.models import Specialty
from apps.users.api_auth import api_roles_required
from .models import (
    ProfessionalProfile,
    ProfessionalDocument,
    ProfessionalVerificationSubmission,
)
from .services import (
    submit_professional_for_verification,
    assign_verification_submission,
    start_verification_review,
    review_professional_document,
    request_submission_correction,
    approve_verification_submission,
    reject_verification_submission,
)


def _json_error(message, status=400, extra=None):
    payload = {"detail": message}
    if extra:
        payload.update(extra)
    return JsonResponse(payload, status=status)


def _parse_json_body(request):
    if not request.body:
        return {}
    try:
        return json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        raise ValueError("JSON inválido.")


def _iso(value):
    return value.isoformat() if value else None


def _parse_bool(value, field_name: str) -> bool:
    if isinstance(value, bool):
        return value

    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "si", "sí"}:
            return True
        if normalized in {"false", "0", "no"}:
            return False

    raise ValueError(f"{field_name} debe ser booleano.")


def _parse_decimal(value, field_name: str) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"{field_name} debe ser numérico.")


def _serialize_user(user):
    if not user:
        return None

    return {
        "id": str(user.id),
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "phone": user.phone,
        "role": user.role,
    }


def _serialize_document(document: ProfessionalDocument):
    return {
        "id": document.id,
        "document_type": document.document_type,
        "original_name": document.original_name,
        "file_path": document.file_path,
        "review_status": document.review_status,
        "reviewer_notes": document.reviewer_notes,
        "uploaded_at": _iso(document.uploaded_at),
        "reviewed_at": _iso(document.reviewed_at),
    }


def _serialize_event(event):
    return {
        "id": event.id,
        "event_type": event.event_type,
        "event_payload": event.event_payload,
        "created_at": _iso(event.created_at),
        "created_by": _serialize_user(event.created_by),
    }


def _serialize_submission(
    submission: ProfessionalVerificationSubmission,
    include_documents=False,
    include_events=False,
):
    data = {
        "id": submission.id,
        "status": submission.status,
        "submitted_at": _iso(submission.submitted_at),
        "reviewed_at": _iso(submission.reviewed_at),
        "reviewer_notes": submission.reviewer_notes,
        "assigned_admin": _serialize_user(submission.assigned_admin),
        "reviewed_by": _serialize_user(submission.reviewed_by),
        "professional": {
            "id": submission.professional.id,
            "email": submission.professional.user.email,
            "verification_status": submission.professional.verification_status,
            "specialty": submission.professional.specialty.name,
        },
    }

    if include_documents:
        documents = submission.professional.documents.order_by("-uploaded_at", "-id")
        data["documents"] = [_serialize_document(doc) for doc in documents]

    if include_events:
        events = submission.events.select_related("created_by").order_by(
            "created_at", "id"
        )
        data["events"] = [_serialize_event(event) for event in events]

    return data


def _latest_submission(profile: ProfessionalProfile):
    return (
        profile.verification_submissions.select_related(
            "assigned_admin",
            "reviewed_by",
            "professional__user",
            "professional__specialty",
        )
        .order_by("-submitted_at", "-id")
        .first()
    )


def _serialize_profile(profile: ProfessionalProfile, include_blockers=True):
    latest_submission = _latest_submission(profile)

    data = {
        "id": profile.id,
        "user": _serialize_user(profile.user),
        "specialty": {
            "id": profile.specialty_id,
            "name": profile.specialty.name,
        }
        if profile.specialty_id
        else None,
        "license_number": profile.license_number,
        "bio": profile.bio,
        "city": profile.city,
        "province": profile.province,
        "public_profile_enabled": profile.public_profile_enabled,
        "verification_status": profile.verification_status,
        "consultation_fee": str(profile.consultation_fee),
        "teleconsultation_fee": str(profile.teleconsultation_fee),
        "is_accepting_patients": profile.is_accepting_patients,
        "created_at": _iso(profile.created_at),
        "updated_at": _iso(profile.updated_at),
        "latest_submission": _serialize_submission(latest_submission)
        if latest_submission
        else None,
    }

    if include_blockers:
        data["can_submit_for_verification"] = profile.can_submit_for_verification()
        data["submission_blockers"] = profile.get_submission_blockers()

    return data


def _get_professional_profile_for_user(user):
    return get_object_or_404(
        ProfessionalProfile.objects.select_related(
            "user", "specialty"
        ).prefetch_related(
            "documents",
            "verification_submissions",
        ),
        user=user,
    )


def _get_admin_submission(submission_id: int):
    return get_object_or_404(
        ProfessionalVerificationSubmission.objects.select_related(
            "professional__user",
            "professional__specialty",
            "assigned_admin",
            "reviewed_by",
        ).prefetch_related(
            "professional__documents",
            "events__created_by",
        ),
        pk=submission_id,
    )


def _get_documents_root() -> Path:
    return Path(settings.MEDIA_ROOT) / "professional_documents"


def _store_uploaded_pdf(*, professional: ProfessionalProfile, uploaded_file):
    extension = Path(uploaded_file.name).suffix.lower()
    if extension != ".pdf":
        raise ValueError("Solo se permite archivo PDF.")

    folder = _get_documents_root() / str(professional.id)
    folder.mkdir(parents=True, exist_ok=True)

    base_name = slugify(Path(uploaded_file.name).stem) or "documento"
    target_name = f"{uuid.uuid4().hex}_{base_name}.pdf"

    storage = FileSystemStorage(location=str(folder))
    stored_name = storage.save(target_name, uploaded_file)

    return str(folder / stored_name), uploaded_file.name


def _upsert_professional_document(
    *, professional: ProfessionalProfile, document_type: str, uploaded_file
):
    latest_open_submission = (
        professional.verification_submissions.filter(
            status__in=[
                ProfessionalVerificationSubmission.Status.SUBMITTED,
                ProfessionalVerificationSubmission.Status.UNDER_REVIEW,
            ]
        )
        .order_by("-submitted_at", "-id")
        .first()
    )

    if latest_open_submission:
        raise ValueError(
            "No se puede reemplazar documentos mientras exista una solicitud abierta en revisión."
        )

    file_path, original_name = _store_uploaded_pdf(
        professional=professional,
        uploaded_file=uploaded_file,
    )

    document = (
        professional.documents.filter(document_type=document_type)
        .order_by("-uploaded_at", "-id")
        .first()
    )

    if document:
        document.file_path = file_path
        document.original_name = original_name
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
        return document

    return ProfessionalDocument.objects.create(
        professional=professional,
        document_type=document_type,
        file_path=file_path,
        original_name=original_name,
        review_status=ProfessionalDocument.ReviewStatus.PENDING,
    )


@require_http_methods(["GET", "PATCH"])
@api_roles_required("professional")
def professional_me_profile_view(request):
    profile = _get_professional_profile_for_user(request.api_user)

    if request.method == "GET":
        return JsonResponse({"profile": _serialize_profile(profile)}, status=200)

    try:
        payload = _parse_json_body(request)
    except ValueError as exc:
        return _json_error(str(exc), status=400)

    changed_profile_fields = []
    changed_user_fields = []

    if "first_name" in payload:
        request.api_user.first_name = (payload.get("first_name") or "").strip()
        if not request.api_user.first_name:
            return _json_error("first_name es obligatorio.", status=400)
        changed_user_fields.append("first_name")

    if "last_name" in payload:
        request.api_user.last_name = (payload.get("last_name") or "").strip()
        if not request.api_user.last_name:
            return _json_error("last_name es obligatorio.", status=400)
        changed_user_fields.append("last_name")

    if "phone" in payload:
        request.api_user.phone = (payload.get("phone") or "").strip()
        changed_user_fields.append("phone")

    if "specialty_id" in payload:
        specialty_id = payload.get("specialty_id")
        specialty = Specialty.objects.filter(pk=specialty_id, is_active=True).first()
        if not specialty:
            return _json_error("specialty_id no existe o está inactiva.", status=400)
        profile.specialty = specialty
        changed_profile_fields.append("specialty")

    if "license_number" in payload:
        license_number = (payload.get("license_number") or "").strip()
        if not license_number:
            return _json_error("license_number es obligatorio.", status=400)

        exists = (
            ProfessionalProfile.objects.exclude(pk=profile.pk)
            .filter(license_number=license_number)
            .exists()
        )
        if exists:
            return _json_error("license_number ya existe.", status=409)

        profile.license_number = license_number
        changed_profile_fields.append("license_number")

    if "bio" in payload:
        profile.bio = (payload.get("bio") or "").strip()
        changed_profile_fields.append("bio")

    if "city" in payload:
        profile.city = (payload.get("city") or "").strip()
        changed_profile_fields.append("city")

    if "province" in payload:
        profile.province = (payload.get("province") or "").strip()
        changed_profile_fields.append("province")

    if "consultation_fee" in payload:
        profile.consultation_fee = _parse_decimal(
            payload.get("consultation_fee"), "consultation_fee"
        )
        changed_profile_fields.append("consultation_fee")

    if "teleconsultation_fee" in payload:
        profile.teleconsultation_fee = _parse_decimal(
            payload.get("teleconsultation_fee"),
            "teleconsultation_fee",
        )
        changed_profile_fields.append("teleconsultation_fee")

    if "is_accepting_patients" in payload:
        profile.is_accepting_patients = _parse_bool(
            payload.get("is_accepting_patients"),
            "is_accepting_patients",
        )
        changed_profile_fields.append("is_accepting_patients")

    if "public_profile_enabled" in payload:
        desired_public = _parse_bool(
            payload.get("public_profile_enabled"), "public_profile_enabled"
        )
        if (
            desired_public
            and profile.verification_status
            != ProfessionalProfile.VerificationStatus.APPROVED
        ):
            return _json_error(
                "Solo un profesional aprobado puede habilitar el perfil público.",
                status=400,
            )
        profile.public_profile_enabled = desired_public
        changed_profile_fields.append("public_profile_enabled")

    if changed_user_fields:
        request.api_user.save(update_fields=changed_user_fields)

    if changed_profile_fields:
        changed_profile_fields.append("updated_at")
        profile.save(update_fields=changed_profile_fields)

    profile.refresh_from_db()
    return JsonResponse({"profile": _serialize_profile(profile)}, status=200)


@require_http_methods(["GET", "POST"])
@api_roles_required("professional")
def professional_me_documents_view(request):
    profile = _get_professional_profile_for_user(request.api_user)

    if request.method == "GET":
        documents = profile.documents.order_by("-uploaded_at", "-id")
        return JsonResponse(
            {
                "results": [_serialize_document(doc) for doc in documents],
                "count": documents.count(),
                "can_submit_for_verification": profile.can_submit_for_verification(),
                "submission_blockers": profile.get_submission_blockers(),
            },
            status=200,
        )

    document_type = (request.POST.get("document_type") or "").strip()
    uploaded_file = request.FILES.get("file")

    if document_type not in ProfessionalDocument.DocumentType.values:
        return _json_error("document_type inválido.", status=400)

    if not uploaded_file:
        return _json_error("file es obligatorio.", status=400)

    try:
        document = _upsert_professional_document(
            professional=profile,
            document_type=document_type,
            uploaded_file=uploaded_file,
        )
    except ValueError as exc:
        return _json_error(str(exc), status=400)

    profile.refresh_from_db()
    return JsonResponse(
        {
            "document": _serialize_document(document),
            "can_submit_for_verification": profile.can_submit_for_verification(),
            "submission_blockers": profile.get_submission_blockers(),
        },
        status=201,
    )


@require_http_methods(["POST"])
@api_roles_required("professional")
def professional_me_submit_verification_view(request):
    profile = _get_professional_profile_for_user(request.api_user)

    try:
        submission = submit_professional_for_verification(
            professional=profile,
            actor=request.api_user,
        )
    except ValidationError as exc:
        return _json_error(
            "No se pudo enviar a validación.",
            status=400,
            extra={"errors": exc.messages},
        )

    profile.refresh_from_db()
    submission = _get_admin_submission(submission.id)

    return JsonResponse(
        {
            "submission": _serialize_submission(
                submission, include_documents=True, include_events=True
            ),
            "profile": _serialize_profile(profile),
        },
        status=201,
    )


@require_http_methods(["GET"])
@api_roles_required("admin", "super_admin")
def admin_verification_submissions_view(request):
    status_filter = (request.GET.get("status") or "").strip()

    queryset = ProfessionalVerificationSubmission.objects.select_related(
        "professional__user",
        "professional__specialty",
        "assigned_admin",
        "reviewed_by",
    ).order_by("-submitted_at", "-id")

    if status_filter:
        queryset = queryset.filter(status=status_filter)

    results = [_serialize_submission(submission) for submission in queryset]

    return JsonResponse({"results": results, "count": len(results)}, status=200)


@require_http_methods(["GET"])
@api_roles_required("admin", "super_admin")
def admin_verification_submission_detail_view(request, submission_id: int):
    submission = _get_admin_submission(submission_id)
    return JsonResponse(
        {
            "submission": _serialize_submission(
                submission,
                include_documents=True,
                include_events=True,
            )
        },
        status=200,
    )


@require_http_methods(["POST"])
@api_roles_required("admin", "super_admin")
def admin_verification_submission_assign_view(request, submission_id: int):
    submission = _get_admin_submission(submission_id)

    try:
        payload = _parse_json_body(request)
    except ValueError as exc:
        return _json_error(str(exc), status=400)

    assignee_id = payload.get("assignee_id")
    assignee = request.api_user

    if assignee_id:
        User = get_user_model()
        assignee = User.objects.filter(
            id=assignee_id, role__in=["admin", "super_admin"]
        ).first()
        if not assignee:
            return _json_error("assignee_id inválido.", status=400)

    try:
        assign_verification_submission(
            submission=submission,
            actor=request.api_user,
            assignee=assignee,
        )
    except ValidationError as exc:
        return _json_error(
            "No se pudo asignar la solicitud.",
            status=400,
            extra={"errors": exc.messages},
        )

    submission.refresh_from_db()
    submission = _get_admin_submission(submission.id)
    return JsonResponse({"submission": _serialize_submission(submission)}, status=200)


@require_http_methods(["POST"])
@api_roles_required("admin", "super_admin")
def admin_verification_submission_start_review_view(request, submission_id: int):
    submission = _get_admin_submission(submission_id)

    try:
        start_verification_review(
            submission=submission,
            actor=request.api_user,
        )
    except ValidationError as exc:
        return _json_error(
            "No se pudo iniciar la revisión.",
            status=400,
            extra={"errors": exc.messages},
        )

    submission.refresh_from_db()
    submission = _get_admin_submission(submission.id)
    return JsonResponse(
        {
            "submission": _serialize_submission(
                submission, include_documents=True, include_events=True
            )
        },
        status=200,
    )


@require_http_methods(["POST"])
@api_roles_required("admin", "super_admin")
def admin_verification_document_review_view(
    request, submission_id: int, document_id: int
):
    submission = _get_admin_submission(submission_id)
    document = get_object_or_404(
        ProfessionalDocument,
        pk=document_id,
        professional=submission.professional,
    )

    try:
        payload = _parse_json_body(request)
    except ValueError as exc:
        return _json_error(str(exc), status=400)

    decision = (payload.get("decision") or "").strip()
    notes = (payload.get("notes") or "").strip()

    try:
        review_professional_document(
            submission=submission,
            document=document,
            actor=request.api_user,
            decision=decision,
            notes=notes,
        )
    except ValidationError as exc:
        return _json_error(
            "No se pudo revisar el documento.",
            status=400,
            extra={"errors": exc.messages},
        )

    document.refresh_from_db()
    submission = _get_admin_submission(submission.id)

    return JsonResponse(
        {
            "document": _serialize_document(document),
            "submission": _serialize_submission(
                submission, include_documents=True, include_events=True
            ),
        },
        status=200,
    )


@require_http_methods(["POST"])
@api_roles_required("admin", "super_admin")
def admin_verification_submission_approve_view(request, submission_id: int):
    submission = _get_admin_submission(submission_id)

    try:
        payload = _parse_json_body(request)
    except ValueError as exc:
        return _json_error(str(exc), status=400)

    notes = (payload.get("notes") or "").strip()

    try:
        approve_verification_submission(
            submission=submission,
            actor=request.api_user,
            notes=notes,
        )
    except ValidationError as exc:
        return _json_error(
            "No se pudo aprobar la solicitud.",
            status=400,
            extra={"errors": exc.messages},
        )

    submission.refresh_from_db()
    submission = _get_admin_submission(submission.id)

    return JsonResponse(
        {
            "submission": _serialize_submission(
                submission, include_documents=True, include_events=True
            )
        },
        status=200,
    )


@require_http_methods(["POST"])
@api_roles_required("admin", "super_admin")
def admin_verification_submission_reject_view(request, submission_id: int):
    submission = _get_admin_submission(submission_id)

    try:
        payload = _parse_json_body(request)
    except ValueError as exc:
        return _json_error(str(exc), status=400)

    notes = (payload.get("notes") or "").strip()

    try:
        reject_verification_submission(
            submission=submission,
            actor=request.api_user,
            notes=notes,
        )
    except ValidationError as exc:
        return _json_error(
            "No se pudo rechazar la solicitud.",
            status=400,
            extra={"errors": exc.messages},
        )

    submission.refresh_from_db()
    submission = _get_admin_submission(submission.id)

    return JsonResponse(
        {
            "submission": _serialize_submission(
                submission, include_documents=True, include_events=True
            )
        },
        status=200,
    )


@require_http_methods(["POST"])
@api_roles_required("admin", "super_admin")
def admin_verification_submission_request_correction_view(request, submission_id: int):
    submission = _get_admin_submission(submission_id)

    try:
        payload = _parse_json_body(request)
    except ValueError as exc:
        return _json_error(str(exc), status=400)

    notes = (payload.get("notes") or "").strip()

    try:
        request_submission_correction(
            submission=submission,
            actor=request.api_user,
            notes=notes,
        )
    except ValidationError as exc:
        return _json_error(
            "No se pudo pedir corrección.", status=400, extra={"errors": exc.messages}
        )

    submission.refresh_from_db()
    submission = _get_admin_submission(submission.id)

    return JsonResponse(
        {
            "submission": _serialize_submission(
                submission, include_documents=True, include_events=True
            )
        },
        status=200,
    )
