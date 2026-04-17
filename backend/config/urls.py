from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("apps.users.api_urls")),
    path("api/v1/", include("apps.appointments.api_urls")),
    path("api/v1/", include("apps.professionals.api_urls")),
]
