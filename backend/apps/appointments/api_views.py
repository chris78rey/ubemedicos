import json
from datetime import datetime, date, time, timedelta

from django.http import JsonResponse
from django.core.exceptions import ObjectDoesNotExist
from django.views.decorators.http import require_http_methods
from django.db.models import Q
from django.utils import timezone
from django.db import transaction
from django.views.decorators.csrf import csrf_exempt

from apps.audits.models import AuditEvent
from apps.users.api_auth import api_roles_required
from apps.professionals.models import ProfessionalProfile
from .models import AvailabilitySlot, AvailabilityBlock, Appointment


# --- Helpers ---


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


def _serialize_slot(slot: AvailabilitySlot):
    return {
        "id": slot.id,
        "weekday": slot.weekday,
        "start_time": slot.start_time.strftime("%H:%M:%S"),
        "end_time": slot.end_time.strftime("%H:%M:%S"),
        "modality": slot.modality,
        "is_active": slot.is_active,
    }


def _serialize_professional_public(prof: ProfessionalProfile):
    return {
        "id": prof.id,
        "name": f"{prof.user.first_name} {prof.user.last_name}",
        "specialty": prof.specialty.name if prof.specialty else None,
        "city": prof.city,
        "province": prof.province,
        "office_address": prof.office_address,
        "bio": prof.bio,
        "consultation_fee": str(prof.consultation_fee),
        "teleconsultation_fee": str(prof.teleconsultation_fee),
    }


def _build_appointment_resolution_summary(app: Appointment):
    try:
        payment = app.payment
    except ObjectDoesNotExist:
        return None

    raw = payment.raw_response or {}
    decision = str(raw.get("decision") or "").strip()
    cancel_as = str(raw.get("cancel_as") or "").strip().lower() or None
    refunded_at = raw.get("refunded_at")
    appointment_status_after = raw.get("appointment_status_after") or app.status

    if payment.status != "refunded":
        return None

    if decision == "refund_and_cancel_appointment":
        if cancel_as == "professional":
            message = (
                "Administración resolvió esta cita con reembolso y la dejó "
                "cancelada como cancelación del profesional."
            )
        elif cancel_as == "patient":
            message = (
                "Administración resolvió esta cita con reembolso y la dejó "
                "cancelada como cancelación del paciente."
            )
        else:
            message = (
                "Administración resolvió esta cita con reembolso y la dejó cancelada."
            )

        return {
            "kind": "refunded_and_cancelled",
            "message": message,
            "cancelled_as": cancel_as,
            "appointment_status_after": appointment_status_after,
            "refunded_at": refunded_at,
        }

    if decision == "refunded":
        return {
            "kind": "refund_only",
            "message": "Administración reembolsó el pago de esta cita.",
            "cancelled_as": None,
            "appointment_status_after": appointment_status_after,
            "refunded_at": refunded_at,
        }

    return {
        "kind": "refunded",
        "message": "Esta cita figura con pago reembolsado.",
        "cancelled_as": None,
        "appointment_status_after": appointment_status_after,
        "refunded_at": refunded_at,
    }


def _serialize_appointment(app: Appointment):
    return {
        "id": app.id,
        "professional": {
            "id": app.professional_id,
            "name": f"{app.professional.user.first_name} {app.professional.user.last_name}",
            "specialty": app.professional.specialty.name
            if app.professional.specialty
            else None,
            "office_address": app.professional.office_address,
            "phone": app.professional.user.phone,
        },
        "patient": {
            "id": app.patient_id,
            "name": f"{app.patient.user.first_name} {app.patient.user.last_name}",
            "email": app.patient.user.email,
            "phone": app.patient.user.phone,
        },
        "scheduled_at": app.scheduled_at.isoformat(),
        "ends_at": app.ends_at.isoformat(),
        "modality": app.modality,
        "status": app.status,
        "notes": app.notes,
        "price": str(app.price),
        "is_paid": app.is_paid,
        "resolution_summary": _build_appointment_resolution_summary(app),
    }


# --- Public Views ---


@require_http_methods(["GET"])
def professionals_public_collection_view(request):
    """Listado público de profesionales aprobados y habilitados."""
    qs = ProfessionalProfile.objects.filter(
        verification_status=ProfessionalProfile.VerificationStatus.APPROVED,
        public_profile_enabled=True,
        is_accepting_patients=True,
    ).select_related("user", "specialty")

    city = request.GET.get("city")
    specialty_id = request.GET.get("specialty_id")

    if city:
        qs = qs.filter(city__icontains=city)
    if specialty_id:
        qs = qs.filter(specialty_id=specialty_id)

    return JsonResponse(
        {"items": [_serialize_professional_public(p) for p in qs]},
        status=200,
    )


@require_http_methods(["GET"])
def professionals_public_detail_view(request, professional_id: int):
    """Detalle público de un profesional."""
    try:
        prof = ProfessionalProfile.objects.select_related("user", "specialty").get(
            id=professional_id,
            verification_status=ProfessionalProfile.VerificationStatus.APPROVED,
            public_profile_enabled=True,
        )
    except ProfessionalProfile.DoesNotExist:
        return _json_error("Profesional no encontrado.", status=404)

    return JsonResponse(_serialize_professional_public(prof), status=200)


@require_http_methods(["GET"])
def professionals_public_available_slots_view(request, professional_id: int):
    """Cálculo de slots de 30 minutos disponibles para una fecha."""
    try:
        prof = ProfessionalProfile.objects.get(
            id=professional_id,
            verification_status=ProfessionalProfile.VerificationStatus.APPROVED,
            public_profile_enabled=True,
        )
    except ProfessionalProfile.DoesNotExist:
        return _json_error("Profesional no encontrado.", status=404)

    date_str = request.GET.get("date")
    modality = request.GET.get("modality")

    if not date_str:
        return _json_error("Parámetro 'date' (YYYY-MM-DD) es obligatorio.")

    try:
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return _json_error("Formato de fecha inválido. Use YYYY-MM-DD.")

    if target_date < timezone.now().date():
        return JsonResponse({"items": []}, status=200)

    # 1. Disponibilidad teórica (AvailabilitySlot)
    # weekday(): 0=Lunes, ..., 6=Domingo
    weekday = target_date.weekday()
    slots_qs = prof.availability_slots.filter(weekday=weekday, is_active=True)
    if modality:
        slots_qs = slots_qs.filter(modality=modality)

    # 2. Bloqueos puntuales (AvailabilityBlock)
    blocks = prof.availability_blocks.filter(
        start_at__date__lte=target_date,
        end_at__date__gte=target_date,
    )

    # 3. Citas ya tomadas (Appointment)
    apps = prof.appointments.filter(
        scheduled_at__date=target_date,
        status__in=[
            Appointment.Status.PENDING_CONFIRMATION,
            Appointment.Status.CONFIRMED,
        ],
    )

    # Generar slots de 30 min y filtrar
    available_times = []
    for slot in slots_qs:
        curr = datetime.combine(target_date, slot.start_time)
        end = datetime.combine(target_date, slot.end_time)
        
        while curr + timedelta(minutes=30) <= end:
            slot_start = timezone.make_aware(curr)
            slot_end = slot_start + timedelta(minutes=30)

            # Validar si está en el pasado (hoy mismo)
            if slot_start < timezone.now():
                curr += timedelta(minutes=30)
                continue

            # Validar bloqueos
            is_blocked = any(b.start_at < slot_end and b.end_at > slot_start for b in blocks)
            if is_blocked:
                curr += timedelta(minutes=30)
                continue

            # Validar citas
            is_taken = any(a.scheduled_at < slot_end and a.ends_at > slot_start for a in apps)
            if is_taken:
                curr += timedelta(minutes=30)
                continue

            available_times.append({
                "time": curr.time().strftime("%H:%M:%S"),
                "datetime": slot_start.isoformat(),
                "modality": slot.modality,
            })
            curr += timedelta(minutes=30)

    return JsonResponse({"items": available_times}, status=200)


# --- Patient Views ---


@csrf_exempt
@require_http_methods(["GET", "POST"])
@api_roles_required("patient")
def patient_appointments_collection_view(request):
    patient = request.api_user.patient_profile

    if request.method == "GET":
        qs = Appointment.objects.filter(patient=patient).select_related(
            "professional__user", "professional__specialty"
        ).order_by("-scheduled_at")
        return JsonResponse(
            {"items": [_serialize_appointment(a) for a in qs]},
            status=200,
        )

    # Crear cita
    try:
        body = _parse_json_body(request)
    except ValueError as exc:
        return _json_error(str(exc))

    prof_id = body.get("professional_id")
    scheduled_at_str = body.get("scheduled_at")
    modality = body.get("modality")
    notes = body.get("notes", "")

    if not all([prof_id, scheduled_at_str, modality]):
        return _json_error("Faltan campos obligatorios: professional_id, scheduled_at, modality.")

    try:
        prof = ProfessionalProfile.objects.get(
            id=prof_id,
            verification_status=ProfessionalProfile.VerificationStatus.APPROVED,
            public_profile_enabled=True,
        )
    except ProfessionalProfile.DoesNotExist:
        return _json_error("Profesional no disponible.", status=404)

    try:
        scheduled_at = datetime.fromisoformat(scheduled_at_str)
        if timezone.is_naive(scheduled_at):
            scheduled_at = timezone.make_aware(scheduled_at)
    except ValueError:
        return _json_error("Formato de scheduled_at inválido. Use ISO 8601.")

    if scheduled_at < timezone.now():
        return _json_error("No se puede agendar en el pasado.")

    ends_at = scheduled_at + timedelta(minutes=30)

    # Validar disponibilidad teórica
    weekday = scheduled_at.weekday()
    has_availability = prof.availability_slots.filter(
        weekday=weekday,
        modality=modality,
        is_active=True,
        start_time__lte=scheduled_at.time(),
        end_time__gte=ends_at.time(),
    ).exists()

    if not has_availability:
        return _json_error("El profesional no tiene disponibilidad configurada para este horario.")

    # Validar bloqueos
    if prof.availability_blocks.filter(start_at__lt=ends_at, end_at__gt=scheduled_at).exists():
        return _json_error("El horario seleccionado está bloqueado administrativamente.")

    # Validar cruce de citas
    if Appointment.objects.filter(
        professional=prof,
        status__in=[Appointment.Status.PENDING_CONFIRMATION, Appointment.Status.CONFIRMED],
        scheduled_at__lt=ends_at,
        ends_at__gt=scheduled_at,
    ).exists():
        return _json_error("El horario ya está reservado.", status=409)

    # Determinar precio
    price = prof.consultation_fee if modality == "in_person" else prof.teleconsultation_fee

    with transaction.atomic():
        appointment = Appointment.objects.create(
            patient=patient,
            professional=prof,
            scheduled_at=scheduled_at,
            ends_at=ends_at,
            modality=modality,
            status=Appointment.Status.PENDING_CONFIRMATION,
            notes=notes,
            price=price,
        )

        AuditEvent.objects.create(
            actor=request.api_user,
            event_type="appointment_created",
            entity_type="Appointment",
            entity_id=str(appointment.id),
            metadata=_serialize_appointment(appointment),
        )

    return JsonResponse(_serialize_appointment(appointment), status=201)


@csrf_exempt
@require_http_methods(["POST"])
@api_roles_required("patient")
def patient_appointment_cancel_view(request, appointment_id: int):
    patient = request.api_user.patient_profile
    try:
        app = (
            Appointment.objects.select_related(
                "patient__user",
                "professional__user",
                "professional__specialty",
            )
            .get(id=appointment_id, patient=patient)
        )
    except Appointment.DoesNotExist:
        return _json_error("Cita no encontrada.", status=404)

    if app.status == Appointment.Status.CANCELLED_BY_PATIENT:
        return JsonResponse(_serialize_appointment(app), status=200)

    if app.status not in [
        Appointment.Status.PENDING_CONFIRMATION,
        Appointment.Status.CONFIRMED,
    ]:
        return _json_error("Solo se pueden cancelar citas activas.", status=409)

    if app.is_paid:
        return _json_error(
            "No se puede cancelar una cita pagada desde este flujo mínimo. "
            "Primero debe resolverse el reembolso o ajuste administrativo.",
            status=409,
        )

    with transaction.atomic():
        app = Appointment.objects.select_for_update().get(id=app.id)
        before_status = app.status
        app.status = Appointment.Status.CANCELLED_BY_PATIENT
        app.save(update_fields=["status"])

        AuditEvent.objects.create(
            actor=request.api_user,
            event_type="appointment_cancelled_by_patient",
            entity_type="Appointment",
            entity_id=str(app.id),
            metadata={
                "before_status": before_status,
                "after_status": app.status,
                "is_paid": app.is_paid,
            },
        )

    app.refresh_from_db()
    app = (
        Appointment.objects.select_related(
            "patient__user",
            "professional__user",
            "professional__specialty",
        )
        .get(id=app.id)
    )
    return JsonResponse(_serialize_appointment(app), status=200)


# --- Professional Views ---


@require_http_methods(["GET"])
@api_roles_required("professional")
def professional_appointments_collection_view(request):
    professional = request.api_user.professional_profile
    qs = (
        Appointment.objects.filter(professional=professional)
        .select_related(
            "patient__user",
            "professional__user",
            "professional__specialty",
            "payment",
        )
        .order_by("-scheduled_at")
    )

    return JsonResponse(
        {"items": [_serialize_appointment(a) for a in qs]},
        status=200,
    )


# --- Availability CRUD (Preservado de la versión anterior) ---


@csrf_exempt
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
            {"items": [_serialize_slot(slot) for slot in slots]},
            status=200,
        )

    try:
        payload = _parse_json_body(request)
    except ValueError as exc:
        return _json_error(str(exc), status=400)

    errors, weekday, start_time, end_time, modality, is_active = _validate_slot_payload(payload)
    if errors:
        return JsonResponse({"detail": "Datos inválidos.", "errors": errors}, status=400)

    if _has_overlap(professional, weekday, start_time, end_time, modality):
        return _json_error("Ya existe un horario activo superpuesto.", status=409)

    slot = AvailabilitySlot.objects.create(
        professional=professional,
        weekday=weekday,
        start_time=start_time,
        end_time=end_time,
        modality=modality,
        is_active=is_active,
    )

    AuditEvent.objects.create(
        actor=request.api_user,
        event_type="availability_slot_created",
        entity_type="AvailabilitySlot",
        entity_id=str(slot.id),
        metadata=_serialize_slot(slot),
    )

    return JsonResponse(_serialize_slot(slot), status=201)


@csrf_exempt
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
        AuditEvent.objects.create(
            actor=request.api_user,
            event_type="availability_slot_deactivated",
            entity_type="AvailabilitySlot",
            entity_id=str(slot.id),
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

    if is_active and _has_overlap(professional, weekday, start_time, end_time, modality, exclude_id=slot.id):
        return _json_error("Ya existe un horario activo superpuesto.", status=409)

    before = _serialize_slot(slot)
    slot.weekday = weekday
    slot.start_time = start_time
    slot.end_time = end_time
    slot.modality = modality
    slot.is_active = is_active
    slot.save(update_fields=["weekday", "start_time", "end_time", "modality", "is_active"])

    AuditEvent.objects.create(
        actor=request.api_user,
        event_type="availability_slot_updated",
        entity_type="AvailabilitySlot",
        entity_id=str(slot.id),
        metadata={"before": before, "after": _serialize_slot(slot)},
    )

    return JsonResponse(_serialize_slot(slot), status=200)
