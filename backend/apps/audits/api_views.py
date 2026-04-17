import csv
import json
from datetime import datetime, time

from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from django.views.decorators.http import require_http_methods

from apps.users.api_auth import api_auth_required, api_roles_required
from .models import AuditEvent


MAX_PAGE_SIZE = 200
MAX_EXPORT_ROWS = 5000


def _json_error(message, status=400, extra=None):
    payload = {"detail": message}
    if extra:
        payload.update(extra)
    return JsonResponse(payload, status=status)


def _serialize_actor(actor):
    if actor is None:
        return None

    return {
        "id": actor.id,
        "email": actor.email,
        "role": actor.role,
        "first_name": actor.first_name,
        "last_name": actor.last_name,
    }


def _serialize_event(event: AuditEvent):
    return {
        "id": event.id,
        "actor": _serialize_actor(event.actor),
        "event_type": event.event_type,
        "entity_type": event.entity_type,
        "entity_id": event.entity_id,
        "metadata": event.metadata or {},
        "created_at": event.created_at.isoformat() if event.created_at else None,
    }


def _parse_positive_int(raw_value, *, default, field_name, min_value=1, max_value=None):
    if raw_value in (None, ""):
        return default

    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} debe ser numérico.")

    if value < min_value:
        raise ValueError(f"{field_name} debe ser mayor o igual a {min_value}.")

    if max_value is not None and value > max_value:
        raise ValueError(f"{field_name} no puede ser mayor a {max_value}.")

    return value


def _coerce_datetime(value, *, field_name, end_of_day=False):
    if not value:
        return None

    parsed_dt = parse_datetime(value)
    if parsed_dt is not None:
        if timezone.is_naive(parsed_dt):
            parsed_dt = timezone.make_aware(
                parsed_dt,
                timezone.get_current_timezone(),
            )
        return parsed_dt

    parsed_date = parse_date(value)
    if parsed_date is not None:
        selected_time = (
            time(23, 59, 59, 999999) if end_of_day else time(0, 0, 0)
        )
        combined = datetime.combine(parsed_date, selected_time)
        return timezone.make_aware(
            combined,
            timezone.get_current_timezone(),
        )

    raise ValueError(
        f"{field_name} debe venir en formato ISO datetime o YYYY-MM-DD."
    )


def _build_filtered_queryset(request):
    qs = AuditEvent.objects.select_related("actor").all().order_by("-created_at", "-id")

    actor_id = request.GET.get("actor_id")
    actor_email = (request.GET.get("actor_email") or "").strip()
    event_type = (request.GET.get("event_type") or "").strip()
    entity_type = (request.GET.get("entity_type") or "").strip()
    entity_id = (request.GET.get("entity_id") or "").strip()
    created_from = (request.GET.get("created_from") or "").strip()
    created_to = (request.GET.get("created_to") or "").strip()

    if actor_id:
        try:
            actor_id = int(actor_id)
        except (TypeError, ValueError):
            raise ValueError("actor_id debe ser numérico.")
        qs = qs.filter(actor_id=actor_id)

    if actor_email:
        qs = qs.filter(actor__email__icontains=actor_email)

    if event_type:
        qs = qs.filter(event_type=event_type)

    if entity_type:
        qs = qs.filter(entity_type=entity_type)

    if entity_id:
        qs = qs.filter(entity_id=entity_id)

    if created_from:
        qs = qs.filter(
            created_at__gte=_coerce_datetime(
                created_from,
                field_name="created_from",
                end_of_day=False,
            )
        )

    if created_to:
        qs = qs.filter(
            created_at__lte=_coerce_datetime(
                created_to,
                field_name="created_to",
                end_of_day=True,
            )
        )

    return qs


@require_http_methods(["GET"])
@api_roles_required("admin", "super_admin", "privacy_auditor")
def admin_audit_logs_collection_view(request):
    try:
        qs = _build_filtered_queryset(request)
        page = _parse_positive_int(
            request.GET.get("page"),
            default=1,
            field_name="page",
            min_value=1,
        )
        page_size = _parse_positive_int(
            request.GET.get("page_size"),
            default=50,
            field_name="page_size",
            min_value=1,
            max_value=MAX_PAGE_SIZE,
        )
    except ValueError as exc:
        return _json_error(str(exc), status=400)

    total = qs.count()
    offset = (page - 1) * page_size
    items = list(qs[offset : offset + page_size])

    return JsonResponse(
        {
            "items": [_serialize_event(event) for event in items],
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "has_next": offset + page_size < total,
            },
            "filters": {
                "actor_id": request.GET.get("actor_id"),
                "actor_email": request.GET.get("actor_email"),
                "event_type": request.GET.get("event_type"),
                "entity_type": request.GET.get("entity_type"),
                "entity_id": request.GET.get("entity_id"),
                "created_from": request.GET.get("created_from"),
                "created_to": request.GET.get("created_to"),
            },
        },
        status=200,
    )


@require_http_methods(["GET"])
@api_roles_required("admin", "super_admin", "privacy_auditor")
def admin_audit_log_detail_view(request, event_id: int):
    event = AuditEvent.objects.select_related("actor").filter(id=event_id).first()
    if not event:
        return _json_error("Evento de auditoría no encontrado.", status=404)

    return JsonResponse(_serialize_event(event), status=200)


@require_http_methods(["GET"])
@api_roles_required("admin", "super_admin", "privacy_auditor")
def admin_audit_logs_export_view(request):
    try:
        qs = _build_filtered_queryset(request)
        limit = _parse_positive_int(
            request.GET.get("limit"),
            default=MAX_EXPORT_ROWS,
            field_name="limit",
            min_value=1,
            max_value=MAX_EXPORT_ROWS,
        )
    except ValueError as exc:
        return _json_error(str(exc), status=400)

    rows = list(qs[:limit])

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="audit_logs.csv"'

    writer = csv.writer(response)
    writer.writerow(
        [
            "id",
            "created_at",
            "actor_id",
            "actor_email",
            "actor_role",
            "event_type",
            "entity_type",
            "entity_id",
            "metadata_json",
        ]
    )

    for event in rows:
        writer.writerow(
            [
                event.id,
                event.created_at.isoformat() if event.created_at else "",
                event.actor_id or "",
                event.actor.email if event.actor else "",
                event.actor.role if event.actor else "",
                event.event_type,
                event.entity_type,
                event.entity_id,
                json.dumps(event.metadata or {}, ensure_ascii=False),
            ]
        )

    response["X-Export-Row-Limit"] = str(limit)
    response["X-Export-Returned-Rows"] = str(len(rows))
    return response


@require_http_methods(["GET"])
@api_auth_required
def my_audit_events_view(request):
    try:
        page = _parse_positive_int(
            request.GET.get("page"),
            default=1,
            field_name="page",
            min_value=1,
        )
        page_size = _parse_positive_int(
            request.GET.get("page_size"),
            default=20,
            field_name="page_size",
            min_value=1,
            max_value=MAX_PAGE_SIZE,
        )
    except ValueError as exc:
        return _json_error(str(exc), status=400)

    qs = AuditEvent.objects.select_related("actor").filter(actor=request.api_user)

    event_type = (request.GET.get("event_type") or "").strip()
    entity_type = (request.GET.get("entity_type") or "").strip()

    if event_type:
        qs = qs.filter(event_type=event_type)

    if entity_type:
        qs = qs.filter(entity_type=entity_type)

    qs = qs.order_by("-created_at", "-id")

    total = qs.count()
    offset = (page - 1) * page_size
    items = list(qs[offset : offset + page_size])

    return JsonResponse(
        {
            "items": [_serialize_event(event) for event in items],
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "has_next": offset + page_size < total,
            },
        },
        status=200,
    )
