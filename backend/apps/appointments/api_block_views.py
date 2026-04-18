from datetime import datetime

from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from apps.audits.models import AuditEvent
from apps.users.api_auth import api_roles_required
from .api_views import _json_error, _parse_json_body, _get_professional_profile
from .models import AvailabilityBlock, Appointment


ACTIVE_APPOINTMENT_STATUSES = [
    Appointment.Status.PENDING_CONFIRMATION,
    Appointment.Status.CONFIRMED,
]


def _parse_datetime(value, field_name: str):
    if not value:
        raise ValueError(f"{field_name} es obligatorio.")

    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        raise ValueError(f"{field_name} debe venir en formato ISO 8601.")

    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed)

    return parsed


def _serialize_block(block: AvailabilityBlock):
    return {
        "id": block.id,
        "start_at": block.start_at.isoformat(),
        "end_at": block.end_at.isoformat(),
        "reason": block.reason,
        "created_at": block.created_at.isoformat() if block.created_at else None,
    }


def _validate_block_window(professional, start_at, end_at, exclude_id=None):
    if start_at >= end_at:
        return "end_at debe ser mayor a start_at."

    if end_at <= timezone.now():
        return "El bloqueo debe terminar en el futuro."

    overlapping_blocks = professional.availability_blocks.filter(
        start_at__lt=end_at,
        end_at__gt=start_at,
    )
    if exclude_id:
        overlapping_blocks = overlapping_blocks.exclude(id=exclude_id)

    if overlapping_blocks.exists():
        return "Ya existe un bloqueo superpuesto en ese rango."

    active_appointments = professional.appointments.filter(
        status__in=ACTIVE_APPOINTMENT_STATUSES,
        scheduled_at__lt=end_at,
        ends_at__gt=start_at,
    )
    if active_appointments.exists():
        return (
            "No se puede crear o actualizar el bloqueo porque se cruza con citas activas."
        )

    return None


@csrf_exempt
@require_http_methods(["GET", "POST"])
@api_roles_required("professional")
def professional_availability_blocks_collection_view(request):
    professional = _get_professional_profile(request.api_user)
    if not professional:
        return _json_error("El usuario no tiene perfil profesional.", status=404)

    if request.method == "GET":
        blocks = professional.availability_blocks.order_by("start_at", "id")
        return JsonResponse(
            {"items": [_serialize_block(block) for block in blocks]},
            status=200,
        )

    try:
        payload = _parse_json_body(request)
        start_at = _parse_datetime(payload.get("start_at"), "start_at")
        end_at = _parse_datetime(payload.get("end_at"), "end_at")
    except ValueError as exc:
        return _json_error(str(exc), status=400)

    reason = (payload.get("reason") or "").strip()

    validation_error = _validate_block_window(professional, start_at, end_at)
    if validation_error:
        return _json_error(validation_error, status=409)

    with transaction.atomic():
        block = AvailabilityBlock.objects.create(
            professional=professional,
            start_at=start_at,
            end_at=end_at,
            reason=reason,
        )

        AuditEvent.objects.create(
            actor=request.api_user,
            event_type="availability_block_created",
            entity_type="AvailabilityBlock",
            entity_id=str(block.id),
            metadata=_serialize_block(block),
        )

    return JsonResponse(_serialize_block(block), status=201)


@csrf_exempt
@require_http_methods(["PATCH", "DELETE"])
@api_roles_required("professional")
def professional_availability_block_detail_view(request, block_id: int):
    professional = _get_professional_profile(request.api_user)
    if not professional:
        return _json_error("El usuario no tiene perfil profesional.", status=404)

    try:
        block = AvailabilityBlock.objects.get(id=block_id, professional=professional)
    except AvailabilityBlock.DoesNotExist:
        return _json_error("Bloqueo no encontrado.", status=404)

    if request.method == "DELETE":
        before = _serialize_block(block)

        with transaction.atomic():
            AuditEvent.objects.create(
                actor=request.api_user,
                event_type="availability_block_deleted",
                entity_type="AvailabilityBlock",
                entity_id=str(block.id),
                metadata={"before": before},
            )
            block.delete()

        return JsonResponse({"detail": "Bloqueo eliminado correctamente."}, status=200)

    try:
        payload = _parse_json_body(request)
    except ValueError as exc:
        return _json_error(str(exc), status=400)

    merged_start_at = payload.get("start_at", block.start_at.isoformat())
    merged_end_at = payload.get("end_at", block.end_at.isoformat())
    merged_reason = (payload.get("reason", block.reason) or "").strip()

    try:
        start_at = _parse_datetime(merged_start_at, "start_at")
        end_at = _parse_datetime(merged_end_at, "end_at")
    except ValueError as exc:
        return _json_error(str(exc), status=400)

    validation_error = _validate_block_window(
        professional,
        start_at,
        end_at,
        exclude_id=block.id,
    )
    if validation_error:
        return _json_error(validation_error, status=409)

    before = _serialize_block(block)

    with transaction.atomic():
        block.start_at = start_at
        block.end_at = end_at
        block.reason = merged_reason
        block.save(update_fields=["start_at", "end_at", "reason"])

        AuditEvent.objects.create(
            actor=request.api_user,
            event_type="availability_block_updated",
            entity_type="AvailabilityBlock",
            entity_id=str(block.id),
            metadata={
                "before": before,
                "after": _serialize_block(block),
            },
        )

    return JsonResponse(_serialize_block(block), status=200)
