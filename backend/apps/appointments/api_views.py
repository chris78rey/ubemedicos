import json
from datetime import time

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.db.models import Q

from apps.audits.models import AuditEvent
from apps.professionals.models import ProfessionalProfile
from apps.users.api_auth import api_roles_required
from .models import AvailabilitySlot


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


def _serialize_slot(slot: AvailabilitySlot):
    return {
        "id": slot.id,
        "weekday": slot.weekday,
        "start_time": slot.start_time.strftime("%H:%M:%S"),
        "end_time": slot.end_time.strftime("%H:%M:%S"),
        "modality": slot.modality,
        "is_active": slot.is_active,
    }


def _get_professional_profile(user):
    try:
        return user.professional_profile
    except ProfessionalProfile.DoesNotExist:
        return None


def _parse_time(value, field_name):
    if not value:
        raise ValueError(f"{field_name} es obligatorio.")
    parts = str(value).split(":")
    if len(parts) < 2:
        raise ValueError(f"{field_name} debe tener formato HH:MM o HH:MM:SS.")
    try:
        hh = int(parts[0])
        mm = int(parts[1])
        ss = int(parts[2]) if len(parts) > 2 else 0
        return time(hh, mm, ss)
    except ValueError:
        raise ValueError(f"{field_name} inválido.")


def _validate_slot_payload(payload):
    errors = {}

    weekday = payload.get("weekday")
    if weekday is None or str(weekday).strip() == "":
        errors["weekday"] = "weekday es obligatorio."
    else:
        try:
            weekday = int(weekday)
            if weekday < 0 or weekday > 6:
                errors["weekday"] = "weekday debe estar entre 0 y 6."
        except (TypeError, ValueError):
            errors["weekday"] = "weekday debe ser numérico."

    try:
        start_time = _parse_time(payload.get("start_time"), "start_time")
    except ValueError as exc:
        errors["start_time"] = str(exc)
        start_time = None

    try:
        end_time = _parse_time(payload.get("end_time"), "end_time")
    except ValueError as exc:
        errors["end_time"] = str(exc)
        end_time = None

    modality = payload.get("modality")
    allowed_modalities = {choice[0] for choice in AvailabilitySlot.Modality.choices}
    if modality not in allowed_modalities:
        errors["modality"] = f"modality debe ser uno de: {', '.join(sorted(allowed_modalities))}."

    is_active = payload.get("is_active", True)
    if isinstance(is_active, str):
        is_active = is_active.lower() in {"1", "true", "yes", "si"}

    if start_time and end_time and start_time >= end_time:
        errors["time_range"] = "end_time debe ser mayor a start_time."

    return errors, weekday if "weekday" not in errors else None, start_time, end_time, modality, is_active


def _has_overlap(professional, weekday, start_time, end_time, modality, exclude_id=None):
    qs = AvailabilitySlot.objects.filter(
        professional=professional,
        weekday=weekday,
        modality=modality,
        is_active=True,
        start_time__lt=end_time,
        end_time__gt=start_time,
    )
    if exclude_id:
        qs = qs.exclude(id=exclude_id)
    return qs.exists()


def _create_audit(actor, event_type, entity_id, metadata):
    AuditEvent.objects.create(
        actor=actor,
        event_type=event_type,
        entity_type="AvailabilitySlot",
        entity_id=str(entity_id),
        metadata=metadata or {},
    )


@require_http_methods(["GET", "POST"])
@api_roles_required("professional")
def professional_availability_collection_view(request):
    professional = _get_professional_profile(request.api_user)
    if not professional:
        return _json_error("El usuario no tiene perfil profesional.", status=404)

    if request.method == "GET":
        slots = professional.availability_slots.order_by(
            "weekday", "start_time", "end_time", "id"
        )
        return JsonResponse(
            {
                "items": [_serialize_slot(slot) for slot in slots],
            },
            status=200,
        )

    try:
        payload = _parse_json_body(request)
    except ValueError as exc:
        return _json_error(str(exc), status=400)

    errors, weekday, start_time, end_time, modality, is_active = _validate_slot_payload(payload)
    if errors:
        return JsonResponse({"detail": "Datos inválidos.", "errors": errors}, status=400)

    if _has_overlap(
        professional=professional,
        weekday=weekday,
        start_time=start_time,
        end_time=end_time,
        modality=modality,
    ):
        return _json_error(
            "Ya existe un horario activo superpuesto para ese día y modalidad.",
            status=409,
        )

    slot = AvailabilitySlot.objects.create(
        professional=professional,
        weekday=weekday,
        start_time=start_time,
        end_time=end_time,
        modality=modality,
        is_active=is_active,
    )

    _create_audit(
        actor=request.api_user,
        event_type="availability_slot_created",
        entity_id=slot.id,
        metadata=_serialize_slot(slot),
    )

    return JsonResponse(_serialize_slot(slot), status=201)


@require_http_methods(["PATCH", "DELETE"])
@api_roles_required("professional")
def professional_availability_detail_view(request, slot_id: int):
    professional = _get_professional_profile(request.api_user)
    if not professional:
        return _json_error("El usuario no tiene perfil profesional.", status=404)

    try:
        slot = AvailabilitySlot.objects.get(id=slot_id, professional=professional)
    except AvailabilitySlot.DoesNotExist:
        return _json_error("Horario no encontrado.", status=404)

    if request.method == "DELETE":
        previous = _serialize_slot(slot)
        slot.is_active = False
        slot.save(update_fields=["is_active"])

        _create_audit(
            actor=request.api_user,
            event_type="availability_slot_deactivated",
            entity_id=slot.id,
            metadata={"before": previous, "after": _serialize_slot(slot)},
        )

        return JsonResponse({"detail": "Horario desactivado correctamente."}, status=200)

    try:
        payload = _parse_json_body(request)
    except ValueError as exc:
        return _json_error(str(exc), status=400)

    merged_payload = {
        "weekday": payload.get("weekday", slot.weekday),
        "start_time": payload.get("start_time", slot.start_time.strftime("%H:%M:%S")),
        "end_time": payload.get("end_time", slot.end_time.strftime("%H:%M:%S")),
        "modality": payload.get("modality", slot.modality),
        "is_active": payload.get("is_active", slot.is_active),
    }

    errors, weekday, start_time, end_time, modality, is_active = _validate_slot_payload(merged_payload)
    if errors:
        return JsonResponse({"detail": "Datos inválidos.", "errors": errors}, status=400)

    if is_active and _has_overlap(
        professional=professional,
        weekday=weekday,
        start_time=start_time,
        end_time=end_time,
        modality=modality,
        exclude_id=slot.id,
    ):
        return _json_error(
            "Ya existe un horario activo superpuesto para ese día y modalidad.",
            status=409,
        )

    before = _serialize_slot(slot)

    slot.weekday = weekday
    slot.start_time = start_time
    slot.end_time = end_time
    slot.modality = modality
    slot.is_active = is_active
    slot.save(update_fields=["weekday", "start_time", "end_time", "modality", "is_active"])

    _create_audit(
        actor=request.api_user,
        event_type="availability_slot_updated",
        entity_id=slot.id,
        metadata={"before": before, "after": _serialize_slot(slot)},
    )

    return JsonResponse(_serialize_slot(slot), status=200)
