from django.urls import path

from .api_views import (
    specialties_collection_view,
    admin_upload_specialties_view,
    admin_download_specialties_template_view,
)

urlpatterns = [
    path(
        "catalogs/specialties",
        specialties_collection_view,
        name="catalogs-specialties-collection",
    ),
    path(
        "admin/catalogs/specialties/upload",
        admin_upload_specialties_view,
        name="admin-upload-specialties",
    ),
    path(
        "admin/catalogs/specialties/template",
        admin_download_specialties_template_view,
        name="admin-specialties-template",
    ),
]
