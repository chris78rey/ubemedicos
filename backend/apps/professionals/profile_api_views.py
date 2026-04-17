import json
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from apps.audits.models import AuditEvent
from apps.catalogs.models import Specialty
from apps.users.api_auth import api_roles_required
from .models import ProfessionalProfile


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


def _parse_bool(value, field_name):
    if isinstance(value, bool):
        return value

    if isinstance(value, int):
        return bool(value)

    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "si", "sí"}:
            return True
        if normalized in {"0", "false", "no"}:
            return False

    raise ValueError(f"{field_name} debe ser booleano.")


def _parse_non_negative_decimal(value, field_name):
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"{field_name} debe ser numérico.")

    if parsed < 0:
        raise ValueError(f"{field_name} no puede ser negativo.")

    return parsed.quantize(Decimal("0.01"))


def _serialize_profile(profile: ProfessionalProfile):
    user = profile.user
    return {
        "user": {
            "id": user.id,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "phone": user.phone,
            "role": user.role,
            "is_email_verified": bool(user.is_email_verified),
        },
        "profile": {
            "id": profile.id,
            "specialty": {
                "id": profile.specialty_id,
                "name": profile.specialty.name if profile.specialty_id else None,
            },
            "license_number": profile.license_number,
            "bio": profile.bio,
            "city": profile.city,
            "province": profile.province,
            "public_profile_enabled": profile.public_profile_enabled,
            "verification_status": profile.verification_status,
            "consultation_fee": str(profile.consultation_fee),
            "teleconsultation_fee": str(profile.teleconsultation_fee),
            "is_accepting_patients": profile.is_accepting_patients,
            "created_at": profile.created_at.isoformat() if profile.created_at else None,
            "updated_at": profile.updated_at.isoformat() if profile.updated_at else None,
        },
        "submission_blockers": profile.get_submission_blockers(),
        "can_submit_for_verification": profile.can_submit_for_verification(),
    }


@require_http_methods(["GET", "PATCH"])
@api_roles_required("professional")
def professional_profile_view(request):
    profile = (
        ProfessionalProfile.objects.select_related("user", "specialty")
        .filter(user=request.api_user)
        .first()
    )
    if not profile:
        return _json_error("Perfil profesional no encontrado.", status=404)

    if request.method == "GET":
        return JsonResponse(_serialize_profile(profile), status=200)

    try:
        payload = _parse_json_body(request)
    except ValueError as exc:
        return _json_error(str(exc), status=400)

    user = profile.user
    user_changed_fields = []
    profile_changed_fields = []
    audit_fields = []

    try:
        with transaction.atomic():
            if "first_name" in payload:
                value = (payload.get("first_name") or "").strip()
                if not value:
                    return _json_error("first_name no puede quedar vacío.", status=400)
                if user.first_name != value:
                    user.first_name = value
                    user_changed_fields.append("first_name")
                    audit_fields.append("first_name")

            if "last_name" in payload:
                value = (payload.get("last_name") or "").strip()
                if not value:
                    return _json_error("last_name no puede quedar vacío.", status=400)
                if user.last_name != value:
                    user.last_name = value
                    user_changed_fields.append("last_name")
                    audit_fields.append("last_name")

            if "phone" in payload:
                value = (payload.get("phone") or "").strip()
                if user.phone != value:
                    user.phone = value
                    user_changed_fields.append("phone")
                    audit_fields.append("phone")

            if "specialty_id" in payload:
                raw_specialty_id = payload.get("specialty_id")
                if raw_specialty_id in (None, ""):
                    return _json_error("specialty_id es obligatorio.", status=400)

                specialty = Specialty.objects.filter(
                    id=raw_specialty_id,
                    is_active=True,
                ).first()
                if not specialty:
                    return _json_error("Especialidad no válida.", status=400)

                if profile.specialty_id != specialty.id:
                    profile.specialty = specialty
                    profile_changed_fields.append("specialty")
                    audit_fields.append("specialty_id")

            if "license_number" in payload:
                value = (payload.get("license_number") or "").strip()
                if not value:
                    return _json_error("license_number no puede quedar vacío.", status=400)

                exists = ProfessionalProfile.objects.exclude(id=profile.id).filter(
                    license_number__iexact=value
                ).exists()
                if exists:
                    return _json_error(
                        "Ya existe otro profesional con ese número de licencia.",
                        status=409,
                    )

                if profile.license_number != value:
                    profile.license_number = value
                    profile_changed_fields.append("license_number")
                    audit_fields.append("license_number")

            if "bio" in payload:
                value = (payload.get("bio") or "").strip()
                if profile.bio != value:
                    profile.bio = value
                    profile_changed_fields.append("bio")
                    audit_fields.append("bio")

            if "city" in payload:
                value = (payload.get("city") or "").strip()
                if profile.city != value:
                    profile.city = value
                    profile_changed_fields.append("city")
                    audit_fields.append("city")

            if "province" in payload:
                value = (payload.get("province") or "").strip()
                if profile.province != value:
                    profile.province = value
                    profile_changed_fields.append("province")
                    audit_fields.append("province")

            if "public_profile_enabled" in payload:
                value = _parse_bool(
                    payload.get("public_profile_enabled"),
                    "public_profile_enabled",
                )
                if profile.public_profile_enabled != value:
                    profile.public_profile_enabled = value
                    profile_changed_fields.append("public_profile_enabled")
                    audit_fields.append("public_profile_enabled")

            if "is_accepting_patients" in payload:
                value = _parse_bool(
                    payload.get("is_accepting_patients"),
                    "is_accepting_patients",
                )
                if profile.is_accepting_patients != value:
                    profile.is_accepting_patients = value
                    profile_changed_fields.append("is_accepting_patients")
                    audit_fields.append("is_accepting_patients")

            if "consultation_fee" in payload:
                value = _parse_non_negative_decimal(
                    payload.get("consultation_fee"),
                    "consultation_fee",
                )
                if profile.consultation_fee != value:
                    profile.consultation_fee = value
                    profile_changed_fields.append("consultation_fee")
                    audit_fields.append("consultation_fee")

            if "teleconsultation_fee" in payload:
                value = _parse_non_negative_decimal(
                    payload.get("teleconsultation_fee"),
                    "teleconsultation_fee",
                )
                if profile.teleconsultation_fee != value:
                    profile.teleconsultation_fee = value
                    profile_changed_fields.append("teleconsultation_fee")
                    audit_fields.append("teleconsultation_fee")

            if user_changed_fields:
                user.save(update_fields=user_changed_fields + ["updated_at"])

            if profile_changed_fields:
                profile.save(update_fields=profile_changed_fields + ["updated_at"])

            if audit_fields:
                AuditEvent.objects.create(
                    actor=request.api_user,
                    event_type="professional_profile_updated",
                    entity_type="ProfessionalProfile",
                    entity_id=str(profile.id),
                    metadata={"fields": audit_fields},
                )
    except ValueError as exc:
        return _json_error(str(exc), status=400)

    profile.refresh_from_db()
    profile = ProfessionalProfile.objects.select_related("user", "specialty").get(
        id=profile.id
    )
    return JsonResponse(_serialize_profile(profile), status=200)
