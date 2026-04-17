import json
from uuid import uuid4

from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from apps.appointments.models import Appointment
from apps.audits.models import AuditEvent
from apps.users.api_auth import api_roles_required
from .models import Payment


ACTIVE_APPOINTMENT_STATUSES = {
    Appointment.Status.PENDING_CONFIRMATION,
    Appointment.Status.CONFIRMED,
}

TERMINAL_APPOINTMENT_STATUSES = {
    Appointment.Status.CANCELLED_BY_PATIENT,
    Appointment.Status.CANCELLED_BY_PROFESSIONAL,
    Appointment.Status.COMPLETED,
    Appointment.Status.NO_SHOW_PATIENT,
    Appointment.Status.NO_SHOW_PROFESSIONAL,
}

ADMIN_CANCELLATION_TARGET_MAP = {
    "patient": Appointment.Status.CANCELLED_BY_PATIENT,
    "professional": Appointment.Status.CANCELLED_BY_PROFESSIONAL,
}


def _json_error(message, status=400):
    return JsonResponse({"detail": message}, status=status)


def _parse_json_body(request):
    if not request.body:
        return {}
    try:
        return json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        raise ValueError("JSON inválido.")


def _new_external_reference():
    return f"demo_pay_{uuid4().hex[:20]}"


def _serialize_payment(payment: Payment, include_raw=False):
    appointment = payment.appointment
    professional_user = appointment.professional.user
    patient_user = appointment.patient.user

    payload = {
        "id": payment.id,
        "external_reference": payment.external_reference,
        "amount": str(payment.amount),
        "currency": payment.currency,
        "status": payment.status,
        "paid_at": payment.paid_at.isoformat() if payment.paid_at else None,
        "created_at": payment.created_at.isoformat() if payment.created_at else None,
        "appointment": {
            "id": appointment.id,
            "status": appointment.status,
            "is_paid": appointment.is_paid,
            "scheduled_at": appointment.scheduled_at.isoformat(),
            "ends_at": appointment.ends_at.isoformat(),
            "modality": appointment.modality,
            "price": str(appointment.price),
            "professional": {
                "id": appointment.professional_id,
                "name": f"{professional_user.first_name} {professional_user.last_name}".strip() or professional_user.email,
                "specialty": appointment.professional.specialty.name if appointment.professional.specialty_id else None,
            },
            "patient": {
                "id": appointment.patient_id,
                "name": f"{patient_user.first_name} {patient_user.last_name}".strip() or patient_user.email,
            },
        },
    }

    if include_raw:
        payload["raw_response"] = payment.raw_response or {}

    return payload


def _get_payment_with_related(payment_id: int):
    return (
        Payment.objects.select_related(
            "appointment__professional__user",
            "appointment__professional__specialty",
            "appointment__patient__user",
        )
        .filter(id=payment_id)
        .first()
    )


# --- Patient Views ---


@require_http_methods(["GET"])
@api_roles_required("patient")
def patient_payments_collection_view(request):
    patient = request.api_user.patient_profile
    qs = Payment.objects.select_related(
        "appointment__professional__user",
        "appointment__professional__specialty",
        "appointment__patient__user",
    ).filter(appointment__patient=patient).order_by("-created_at")

    return JsonResponse(
        {"items": [_serialize_payment(payment) for payment in qs]},
        status=200,
    )


@require_http_methods(["POST"])
@api_roles_required("patient")
def patient_appointment_payment_intent_view(request, appointment_id: int):
    patient = request.api_user.patient_profile

    try:
        appointment = Appointment.objects.select_related(
            "professional__user",
            "professional__specialty",
            "patient__user",
        ).get(id=appointment_id, patient=patient)
    except Appointment.DoesNotExist:
        return _json_error("Cita no encontrada.", status=404)

    if appointment.status not in ACTIVE_APPOINTMENT_STATUSES:
        return _json_error(
            "Solo se puede generar pago para citas activas.",
            status=409,
        )

    with transaction.atomic():
        payment = (
            Payment.objects.select_for_update()
            .select_related(
                "appointment__professional__user",
                "appointment__professional__specialty",
                "appointment__patient__user",
            )
            .filter(appointment=appointment)
            .first()
        )

        if payment and payment.status == Payment.Status.SUCCEEDED:
            return JsonResponse(_serialize_payment(payment), status=200)

        if payment and payment.status == Payment.Status.PENDING:
            return JsonResponse(_serialize_payment(payment), status=200)

        if payment and payment.status in {Payment.Status.FAILED, Payment.Status.REFUNDED}:
            previous_status = payment.status
            payment.status = Payment.Status.PENDING
            payment.paid_at = None
            payment.external_reference = _new_external_reference()
            payment.raw_response = {
                **(payment.raw_response or {}),
                "provider": "demo_manual",
                "reopened_at": timezone.now().isoformat(),
                "reopened_by": request.api_user.email,
                "previous_status": previous_status,
            }
            payment.save(
                update_fields=[
                    "status",
                    "paid_at",
                    "external_reference",
                    "raw_response",
                ]
            )

            AuditEvent.objects.create(
                actor=request.api_user,
                event_type="payment_intent_reopened",
                entity_type="Payment",
                entity_id=str(payment.id),
                metadata={
                    "appointment_id": appointment.id,
                    "from_status": previous_status,
                    "to_status": payment.status,
                    "external_reference": payment.external_reference,
                },
            )

            return JsonResponse(_serialize_payment(payment), status=200)

        payment = Payment.objects.create(
            appointment=appointment,
            external_reference=_new_external_reference(),
            amount=appointment.price,
            currency="USD",
            status=Payment.Status.PENDING,
            raw_response={
                "provider": "demo_manual",
                "created_from": "patient_payment_intent",
                "created_at": timezone.now().isoformat(),
            },
        )

        AuditEvent.objects.create(
            actor=request.api_user,
            event_type="payment_intent_created",
            entity_type="Payment",
            entity_id=str(payment.id),
            metadata={
                "appointment_id": appointment.id,
                "status": payment.status,
                "amount": str(payment.amount),
                "currency": payment.currency,
                "external_reference": payment.external_reference,
            },
        )

    payment = _get_payment_with_related(payment.id)
    return JsonResponse(_serialize_payment(payment), status=201)


# --- Admin Views ---


@require_http_methods(["GET"])
@api_roles_required("admin", "super_admin")
def admin_payments_collection_view(request):
    qs = Payment.objects.select_related(
        "appointment__professional__user",
        "appointment__professional__specialty",
        "appointment__patient__user",
    ).order_by("-created_at")

    status_filter = request.GET.get("status")
    if status_filter:
        qs = qs.filter(status=status_filter)

    return JsonResponse(
        {"items": [_serialize_payment(payment, include_raw=True) for payment in qs]},
        status=200,
    )


@require_http_methods(["POST"])
@api_roles_required("admin", "super_admin")
def admin_payment_mark_succeeded_view(request, payment_id: int):
    try:
        body = _parse_json_body(request)
    except ValueError as exc:
        return _json_error(str(exc))

    payment = _get_payment_with_related(payment_id)
    if not payment:
        return _json_error("Pago no encontrado.", status=404)

    appointment = payment.appointment
    if appointment.status in TERMINAL_APPOINTMENT_STATUSES:
        return _json_error("No se puede aprobar un pago de una cita cerrada o cancelada.")

    if payment.status == Payment.Status.SUCCEEDED:
        return JsonResponse(_serialize_payment(payment, include_raw=True), status=200)

    if payment.status == Payment.Status.REFUNDED:
        return _json_error("No se puede aprobar un pago ya reembolsado.")

    admin_notes = (body.get("notes") or "").strip()

    with transaction.atomic():
        payment = Payment.objects.select_for_update().get(id=payment.id)
        appointment = Appointment.objects.select_for_update().get(id=payment.appointment_id)

        payment.status = Payment.Status.SUCCEEDED
        payment.paid_at = timezone.now()
        payment.raw_response = {
            **(payment.raw_response or {}),
            "provider": "demo_manual",
            "decision": "succeeded",
            "admin_notes": admin_notes,
            "updated_at": timezone.now().isoformat(),
            "updated_by": request.api_user.email,
        }
        payment.save(update_fields=["status", "paid_at", "raw_response"])

        appointment.is_paid = True
        if appointment.status == Appointment.Status.PENDING_CONFIRMATION:
            appointment.status = Appointment.Status.CONFIRMED
            appointment.save(update_fields=["is_paid", "status"])
        else:
            appointment.save(update_fields=["is_paid"])

        AuditEvent.objects.create(
            actor=request.api_user,
            event_type="payment_marked_succeeded",
            entity_type="Payment",
            entity_id=str(payment.id),
            metadata={
                "appointment_id": appointment.id,
                "payment_status": payment.status,
                "appointment_status": appointment.status,
                "is_paid": appointment.is_paid,
            },
        )

    payment = _get_payment_with_related(payment.id)
    return JsonResponse(_serialize_payment(payment, include_raw=True), status=200)


@require_http_methods(["POST"])
@api_roles_required("admin", "super_admin")
def admin_payment_mark_failed_view(request, payment_id: int):
    try:
        body = _parse_json_body(request)
    except ValueError as exc:
        return _json_error(str(exc))

    payment = _get_payment_with_related(payment_id)
    if not payment:
        return _json_error("Pago no encontrado.", status=404)

    if payment.status == Payment.Status.SUCCEEDED:
        return _json_error("Un pago exitoso no puede marcarse como fallido en este flujo mínimo.")

    admin_notes = (body.get("notes") or "").strip()

    with transaction.atomic():
        payment = Payment.objects.select_for_update().get(id=payment.id)
        appointment = Appointment.objects.select_for_update().get(id=payment.appointment_id)

        payment.status = Payment.Status.FAILED
        payment.paid_at = None
        payment.raw_response = {
            **(payment.raw_response or {}),
            "provider": "demo_manual",
            "decision": "failed",
            "admin_notes": admin_notes,
            "updated_at": timezone.now().isoformat(),
            "updated_by": request.api_user.email,
        }
        payment.save(update_fields=["status", "paid_at", "raw_response"])

        appointment.is_paid = False
        if appointment.status not in TERMINAL_APPOINTMENT_STATUSES:
            appointment.save(update_fields=["is_paid"])

        AuditEvent.objects.create(
            actor=request.api_user,
            event_type="payment_marked_failed",
            entity_type="Payment",
            entity_id=str(payment.id),
            metadata={
                "appointment_id": appointment.id,
                "payment_status": payment.status,
                "appointment_status": appointment.status,
                "is_paid": appointment.is_paid,
            },
        )

    payment = _get_payment_with_related(payment.id)
    return JsonResponse(_serialize_payment(payment, include_raw=True), status=200)


@require_http_methods(["POST"])
@api_roles_required("admin", "super_admin")
def admin_payment_mark_refunded_view(request, payment_id: int):
    try:
        body = _parse_json_body(request)
    except ValueError as exc:
        return _json_error(str(exc))

    payment = _get_payment_with_related(payment_id)
    if not payment:
        return _json_error("Pago no encontrado.", status=404)

    if payment.status == Payment.Status.REFUNDED:
        return JsonResponse(_serialize_payment(payment, include_raw=True), status=200)

    if payment.status != Payment.Status.SUCCEEDED:
        return _json_error(
            "Solo un pago exitoso puede marcarse como reembolsado.",
            status=409,
        )

    admin_notes = (body.get("notes") or "").strip()

    with transaction.atomic():
        payment = Payment.objects.select_for_update().get(id=payment.id)
        appointment = Appointment.objects.select_for_update().get(id=payment.appointment_id)

        payment.status = Payment.Status.REFUNDED
        payment.raw_response = {
            **(payment.raw_response or {}),
            "provider": "demo_manual",
            "decision": "refunded",
            "admin_notes": admin_notes,
            "refunded_at": timezone.now().isoformat(),
            "updated_at": timezone.now().isoformat(),
            "updated_by": request.api_user.email,
        }
        payment.save(update_fields=["status", "raw_response"])

        appointment.is_paid = False
        appointment.save(update_fields=["is_paid"])

        AuditEvent.objects.create(
            actor=request.api_user,
            event_type="payment_marked_refunded",
            entity_type="Payment",
            entity_id=str(payment.id),
            metadata={
                "appointment_id": appointment.id,
                "payment_status": payment.status,
                "appointment_status": appointment.status,
                "is_paid": appointment.is_paid,
            },
        )

    payment = _get_payment_with_related(payment.id)
    return JsonResponse(_serialize_payment(payment, include_raw=True), status=200)


@require_http_methods(["POST"])
@api_roles_required("admin", "super_admin")
def admin_payment_refund_and_cancel_appointment_view(request, payment_id: int):
    try:
        body = _parse_json_body(request)
    except ValueError as exc:
        return _json_error(str(exc))

    payment = _get_payment_with_related(payment_id)
    if not payment:
        return _json_error("Pago no encontrado.", status=404)

    cancel_as = (body.get("cancel_as") or "").strip().lower()
    if cancel_as not in ADMIN_CANCELLATION_TARGET_MAP:
        return _json_error(
            "cancel_as debe ser 'patient' o 'professional'.",
            status=400,
        )

    target_status = ADMIN_CANCELLATION_TARGET_MAP[cancel_as]
    admin_notes = (body.get("notes") or "").strip()
    appointment = payment.appointment

    if payment.status not in {Payment.Status.SUCCEEDED, Payment.Status.REFUNDED}:
        return _json_error(
            "Solo se puede resolver este flujo sobre pagos exitosos o ya reembolsados.",
            status=409,
        )

    if appointment.status in {
        Appointment.Status.COMPLETED,
        Appointment.Status.NO_SHOW_PATIENT,
        Appointment.Status.NO_SHOW_PROFESSIONAL,
    }:
        return _json_error(
            "No se puede cancelar una cita ya cerrada.",
            status=409,
        )

    if (
        payment.status == Payment.Status.REFUNDED
        and appointment.status == target_status
        and not appointment.is_paid
    ):
        return JsonResponse(_serialize_payment(payment, include_raw=True), status=200)

    if appointment.status in {
        Appointment.Status.CANCELLED_BY_PATIENT,
        Appointment.Status.CANCELLED_BY_PROFESSIONAL,
    } and appointment.status != target_status:
        return _json_error(
            "La cita ya fue cancelada con otro origen de cancelación.",
            status=409,
        )

    with transaction.atomic():
        payment = Payment.objects.select_for_update().get(id=payment.id)
        appointment = Appointment.objects.select_for_update().get(id=payment.appointment_id)

        before_payment_status = payment.status
        before_appointment_status = appointment.status

        payment.status = Payment.Status.REFUNDED
        payment.raw_response = {
            **(payment.raw_response or {}),
            "provider": "demo_manual",
            "decision": "refund_and_cancel_appointment",
            "cancel_as": cancel_as,
            "admin_notes": admin_notes,
            "refunded_at": timezone.now().isoformat(),
            "appointment_status_after": target_status,
            "updated_at": timezone.now().isoformat(),
            "updated_by": request.api_user.email,
        }
        payment.save(update_fields=["status", "raw_response"])

        appointment.status = target_status
        appointment.is_paid = False
        appointment.save(update_fields=["status", "is_paid"])

        AuditEvent.objects.create(
            actor=request.api_user,
            event_type="payment_refunded_and_appointment_cancelled",
            entity_type="Payment",
            entity_id=str(payment.id),
            metadata={
                "appointment_id": appointment.id,
                "before_payment_status": before_payment_status,
                "after_payment_status": payment.status,
                "before_appointment_status": before_appointment_status,
                "after_appointment_status": appointment.status,
                "cancel_as": cancel_as,
                "is_paid": appointment.is_paid,
            },
        )

        AuditEvent.objects.create(
            actor=request.api_user,
            event_type="appointment_cancelled_after_payment_refund",
            entity_type="Appointment",
            entity_id=str(appointment.id),
            metadata={
                "payment_id": payment.id,
                "before_status": before_appointment_status,
                "after_status": appointment.status,
                "cancel_as": cancel_as,
                "payment_status": payment.status,
                "is_paid": appointment.is_paid,
            },
        )

    payment = _get_payment_with_related(payment.id)
    return JsonResponse(_serialize_payment(payment, include_raw=True), status=200)
