from django.urls import path

from .api_views import (
    # Public
    professionals_public_collection_view,
    professionals_public_detail_view,
    professionals_public_available_slots_view,
    # Patient
    patient_appointments_collection_view,
    patient_appointment_cancel_view,
    # Professional
    professional_appointments_collection_view,
    professional_availability_collection_view,
    professional_availability_detail_view,
)

urlpatterns = [
    # --- Public ---
    path(
        "professionals/public",
        professionals_public_collection_view,
        name="professionals-public-collection",
    ),
    path(
        "professionals/public/<int:professional_id>",
        professionals_public_detail_view,
        name="professionals-public-detail",
    ),
    path(
        "professionals/public/<int:professional_id>/available-slots",
        professionals_public_available_slots_view,
        name="professionals-public-available-slots",
    ),
    # --- Patient ---
    path(
        "patient/appointments",
        patient_appointments_collection_view,
        name="patient-appointments-collection",
    ),
    path(
        "patient/appointments/<int:appointment_id>/cancel",
        patient_appointment_cancel_view,
        name="patient-appointment-cancel",
    ),
    # --- Professional ---
    path(
        "professional/appointments",
        professional_appointments_collection_view,
        name="professional-appointments-collection",
    ),
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
