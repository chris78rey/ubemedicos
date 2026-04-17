from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

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
