from django.urls import path

from .api_views import specialties_collection_view

urlpatterns = [
    path(
        "catalogs/specialties",
        specialties_collection_view,
        name="catalogs-specialties-collection",
    ),
]
