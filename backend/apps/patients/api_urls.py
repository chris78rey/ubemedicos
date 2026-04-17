from django.urls import path

from .api_views import patient_profile_view

urlpatterns = [
    path(
        "patient/profile",
        patient_profile_view,
        name="patient-profile",
    ),
]
