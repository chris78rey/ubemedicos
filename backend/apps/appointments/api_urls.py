from django.urls import path

from .api_views import (
    professional_availability_collection_view,
    professional_availability_detail_view,
)

urlpatterns = [
    path(
        "professional/availability",
        professional_availability_collection_view,
        name="professional-availability-collection",
    ),
    path(
        "professional/availability/<int:slot_id>",
        professional_availability_detail_view,
        name="professional-availability-detail",
    ),
]
