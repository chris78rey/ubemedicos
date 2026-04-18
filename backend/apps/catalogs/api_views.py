import io
import openpyxl
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from apps.audits.models import AuditEvent
from apps.users.api_auth import api_roles_required
from .models import Specialty


def _serialize_specialty(specialty: Specialty):
    return {
        "id": specialty.id,
        "name": specialty.name,
    }


@require_http_methods(["GET"])
def specialties_collection_view(request):
    items = Specialty.objects.filter(is_active=True).order_by("name")
    return JsonResponse(
        {"items": [_serialize_specialty(item) for item in items]},
        status=200,
    )


@csrf_exempt
@require_http_methods(["POST"])
@api_roles_required("super_admin")
def admin_upload_specialties_view(request):
    """
    Carga masiva de especialidades desde un archivo Excel.
    """
    uploaded_file = request.FILES.get("file")
    if not uploaded_file:
        return JsonResponse({"detail": "No se proporcionó ningún archivo."}, status=400)

    if not uploaded_file.name.endswith(".xlsx"):
        return JsonResponse(
            {"detail": "Formato de archivo inválido. Debe ser .xlsx"}, status=400
        )

    try:
        # Usamos BytesIO para leer el archivo subido en memoria
        wb = openpyxl.load_workbook(uploaded_file, data_only=True)
        sheet = wb.active
        if not sheet:
            return JsonResponse({"detail": "El archivo está vacío."}, status=400)

        rows = list(sheet.rows)
        if len(rows) < 2:
            return JsonResponse(
                {"detail": "El archivo no contiene filas de datos."}, status=400
            )

        summary = {
            "total_rows": len(rows) - 1,
            "created": 0,
            "reactivated": 0,
            "existing": 0,
            "blank_skipped": 0,
            "errors": [],
        }

        # Ignorar encabezado (fila 1)
        for i, row in enumerate(rows[1:], start=2):
            cell_value = row[0].value
            if cell_value is None:
                summary["blank_skipped"] += 1
                continue

            normalized_name = str(cell_value).strip()
            if not normalized_name:
                summary["blank_skipped"] += 1
                continue

            specialty = Specialty.objects.filter(name__iexact=normalized_name).first()

            if specialty:
                if not specialty.is_active:
                    specialty.is_active = True
                    specialty.save(update_fields=["is_active"])
                    summary["reactivated"] += 1
                else:
                    summary["existing"] += 1
            else:
                Specialty.objects.create(name=normalized_name, is_active=True)
                summary["created"] += 1

        # Registro en Auditoría
        AuditEvent.objects.create(
            actor=request.api_user,
            event_type="admin_bulk_upload_specialties",
            entity_type="Specialty",
            metadata={
                "filename": uploaded_file.name,
                "summary": summary,
            },
        )

        return JsonResponse(
            {"detail": "Carga procesada correctamente.", "summary": summary}, status=200
        )

    except Exception as exc:
        return JsonResponse(
            {"detail": f"Error procesando el archivo: {str(exc)}"}, status=400
        )
