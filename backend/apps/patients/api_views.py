import json

from django.db import transaction
from django.http import JsonResponse
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_http_methods

from apps.audits.models import AuditEvent
from apps.users.api_auth import api_roles_required
from .models import PatientProfile


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


def _parse_birth_date(value):
    if value in (None, ""):
        return None

    parsed = parse_date(str(value))
    if parsed is None:
        raise ValueError("birth_date debe venir en formato YYYY-MM-DD.")
    return parsed


def _serialize_profile(profile: PatientProfile):
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
            "birth_date": profile.birth_date.isoformat() if profile.birth_date else None,
            "gender": profile.gender,
            "national_id": profile.national_id,
            "emergency_contact_name": profile.emergency_contact_name,
            "emergency_contact_phone": profile.emergency_contact_phone,
            "created_at": profile.created_at.isoformat() if profile.created_at else None,
            "updated_at": profile.updated_at.isoformat() if profile.updated_at else None,
        },
    }


@require_http_methods(["GET", "PATCH"])
@api_roles_required("patient")
def patient_profile_view(request):
    profile = PatientProfile.objects.select_related("user").filter(user=request.api_user).first()
    if not profile:
        return _json_error("Perfil de paciente no encontrado.", status=404)

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

            if "birth_date" in payload:
                value = _parse_birth_date(payload.get("birth_date"))
                if profile.birth_date != value:
                    profile.birth_date = value
                    profile_changed_fields.append("birth_date")
                    audit_fields.append("birth_date")

            if "gender" in payload:
                value = (payload.get("gender") or "").strip()
                if profile.gender != value:
                    profile.gender = value
                    profile_changed_fields.append("gender")
                    audit_fields.append("gender")

            if "national_id" in payload:
                value = (payload.get("national_id") or "").strip()
                if profile.national_id != value:
                    profile.national_id = value
                    profile_changed_fields.append("national_id")
                    audit_fields.append("national_id")

            if "emergency_contact_name" in payload:
                value = (payload.get("emergency_contact_name") or "").strip()
                if profile.emergency_contact_name != value:
                    profile.emergency_contact_name = value
                    profile_changed_fields.append("emergency_contact_name")
                    audit_fields.append("emergency_contact_name")

            if "emergency_contact_phone" in payload:
                value = (payload.get("emergency_contact_phone") or "").strip()
                if profile.emergency_contact_phone != value:
                    profile.emergency_contact_phone = value
                    profile_changed_fields.append("emergency_contact_phone")
                    audit_fields.append("emergency_contact_phone")

            if user_changed_fields:
                user.save(update_fields=user_changed_fields + ["updated_at"])

            if profile_changed_fields:
                profile.save(update_fields=profile_changed_fields + ["updated_at"])

            if audit_fields:
                AuditEvent.objects.create(
                    actor=request.api_user,
                    event_type="patient_profile_updated",
                    entity_type="PatientProfile",
                    entity_id=str(profile.id),
                    metadata={"fields": audit_fields},
                )
    except ValueError as exc:
        return _json_error(str(exc), status=400)

    profile.refresh_from_db()
    profile = PatientProfile.objects.select_related("user").get(id=profile.id)
    return JsonResponse(_serialize_profile(profile), status=200)
