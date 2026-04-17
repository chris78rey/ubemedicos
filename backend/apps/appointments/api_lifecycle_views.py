import json

from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from apps.audits.models import AuditEvent
from apps.users.api_auth import api_roles_required
from .api_views import _json_error, _serialize_appointment
from .models import Appointment


ACTIVE_PROFESSIONAL_ACTIONABLE_STATUSES = {
    Appointment.Status.PENDING_CONFIRMATION,
    Appointment.Status.CONFIRMED,
}


def _parse_json_body(request):
    if not request.body:
        return {}
    try:
        return json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        raise ValueError("JSON inválido.")


def _get_professional_appointment(user, appointment_id: int):
    try:
        professional = user.professional_profile
    except Exception:
        return None

    return (
        Appointment.objects.select_related(
            "patient__user",
            "professional__user",
            "professional__specialty",
        )
        .filter(
            id=appointment_id,
            professional=professional,
        )
        .first()
    )


def _create_audit(actor, event_type: str, appointment: Appointment, metadata: dict):
    AuditEvent.objects.create(
        actor=actor,
        event_type=event_type,
        entity_type="Appointment",
        entity_id=str(appointment.id),
        metadata=metadata or {},
    )


@require_http_methods(["POST"])
@api_roles_required("professional")
def professional_appointment_confirm_view(request, appointment_id: int):
    appointment = _get_professional_appointment(request.api_user, appointment_id)
    if not appointment:
        return _json_error("Cita no encontrada.", status=404)

    if appointment.status == Appointment.Status.CONFIRMED:
        return JsonResponse(_serialize_appointment(appointment), status=200)

    if appointment.status != Appointment.Status.PENDING_CONFIRMATION:
        return _json_error(
            "Solo se puede confirmar una cita pendiente de confirmación.",
            status=409,
        )

    try:
        payload = _parse_json_body(request)
    except ValueError as exc:
        return _json_error(str(exc), status=400)

    notes = (payload.get("notes") or "").strip()

    with transaction.atomic():
        appointment = Appointment.objects.select_for_update().get(id=appointment.id)
        before_status = appointment.status
        appointment.status = Appointment.Status.CONFIRMED
        appointment.save(update_fields=["status"])

        _create_audit(
            actor=request.api_user,
            event_type="appointment_confirmed_by_professional",
            appointment=appointment,
            metadata={
                "before_status": before_status,
                "after_status": appointment.status,
                "notes": notes,
            },
        )

    appointment.refresh_from_db()
    appointment = (
        Appointment.objects.select_related(
            "patient__user",
            "professional__user",
            "professional__specialty",
        )
        .get(id=appointment.id)
    )
    return JsonResponse(_serialize_appointment(appointment), status=200)


@require_http_methods(["POST"])
@api_roles_required("professional")
def professional_appointment_cancel_view(request, appointment_id: int):
    appointment = _get_professional_appointment(request.api_user, appointment_id)
    if not appointment:
        return _json_error("Cita no encontrada.", status=404)

    if appointment.status == Appointment.Status.CANCELLED_BY_PROFESSIONAL:
        return JsonResponse(_serialize_appointment(appointment), status=200)

    if appointment.status not in ACTIVE_PROFESSIONAL_ACTIONABLE_STATUSES:
        return _json_error("Solo se pueden cancelar citas activas.", status=409)

    if appointment.is_paid:
        return _json_error(
            "No se puede cancelar una cita pagada desde este flujo mínimo. "
            "Primero debe resolverse el reembolso o ajuste administrativo.",
            status=409,
        )

    try:
        payload = _parse_json_body(request)
    except ValueError as exc:
        return _json_error(str(exc), status=400)

    reason = (payload.get("reason") or "").strip()

    with transaction.atomic():
        appointment = Appointment.objects.select_for_update().get(id=appointment.id)
        before_status = appointment.status
        appointment.status = Appointment.Status.CANCELLED_BY_PROFESSIONAL
        appointment.save(update_fields=["status"])

        _create_audit(
            actor=request.api_user,
            event_type="appointment_cancelled_by_professional",
            appointment=appointment,
            metadata={
                "before_status": before_status,
                "after_status": appointment.status,
                "reason": reason,
            },
        )

    appointment.refresh_from_db()
    appointment = (
        Appointment.objects.select_related(
            "patient__user",
            "professional__user",
            "professional__specialty",
        )
        .get(id=appointment.id)
    )
    return JsonResponse(_serialize_appointment(appointment), status=200)


@require_http_methods(["POST"])
@api_roles_required("professional")
def professional_appointment_complete_view(request, appointment_id: int):
    appointment = _get_professional_appointment(request.api_user, appointment_id)
    if not appointment:
        return _json_error("Cita no encontrada.", status=404)

    if appointment.status == Appointment.Status.COMPLETED:
        return JsonResponse(_serialize_appointment(appointment), status=200)

    if appointment.status != Appointment.Status.CONFIRMED:
        return _json_error(
            "Solo se puede completar una cita confirmada.",
            status=409,
        )

    if appointment.scheduled_at > timezone.now():
        return _json_error(
            "No se puede completar una cita futura.",
            status=409,
        )

    try:
        payload = _parse_json_body(request)
    except ValueError as exc:
        return _json_error(str(exc), status=400)

    notes = (payload.get("notes") or "").strip()

    with transaction.atomic():
        appointment = Appointment.objects.select_for_update().get(id=appointment.id)
        before_status = appointment.status
        appointment.status = Appointment.Status.COMPLETED
        appointment.save(update_fields=["status"])

        _create_audit(
            actor=request.api_user,
            event_type="appointment_completed_by_professional",
            appointment=appointment,
            metadata={
                "before_status": before_status,
                "after_status": appointment.status,
                "notes": notes,
            },
        )

    appointment.refresh_from_db()
    appointment = (
        Appointment.objects.select_related(
            "patient__user",
            "professional__user",
            "professional__specialty",
        )
        .get(id=appointment.id)
    )
    return JsonResponse(_serialize_appointment(appointment), status=200)


@require_http_methods(["POST"])
@api_roles_required("professional")
def professional_appointment_mark_no_show_patient_view(request, appointment_id: int):
    appointment = _get_professional_appointment(request.api_user, appointment_id)
    if not appointment:
        return _json_error("Cita no encontrada.", status=404)

    if appointment.status == Appointment.Status.NO_SHOW_PATIENT:
        return JsonResponse(_serialize_appointment(appointment), status=200)

    if appointment.status != Appointment.Status.CONFIRMED:
        return _json_error(
            "Solo se puede marcar no asistencia sobre una cita confirmada.",
            status=409,
        )

    if appointment.scheduled_at > timezone.now():
        return _json_error(
            "No se puede marcar no asistencia en una cita futura.",
            status=409,
        )

    try:
        payload = _parse_json_body(request)
    except ValueError as exc:
        return _json_error(str(exc), status=400)

    reason = (payload.get("reason") or "").strip()

    with transaction.atomic():
        appointment = Appointment.objects.select_for_update().get(id=appointment.id)
        before_status = appointment.status
        appointment.status = Appointment.Status.NO_SHOW_PATIENT
        appointment.save(update_fields=["status"])

        _create_audit(
            actor=request.api_user,
            event_type="appointment_marked_no_show_patient",
            appointment=appointment,
            metadata={
                "before_status": before_status,
                "after_status": appointment.status,
                "reason": reason,
            },
        )

    appointment.refresh_from_db()
    appointment = (
        Appointment.objects.select_related(
            "patient__user",
            "professional__user",
            "professional__specialty",
        )
        .get(id=appointment.id)
    )
    return JsonResponse(_serialize_appointment(appointment), status=200)
