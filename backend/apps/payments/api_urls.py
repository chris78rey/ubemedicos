from django.urls import path

from .api_views import (
    patient_payments_collection_view,
    patient_appointment_payment_intent_view,
    admin_payments_collection_view,
    admin_payment_mark_succeeded_view,
    admin_payment_mark_failed_view,
)

urlpatterns = [
    # --- Patient ---
    path(
        "patient/payments",
        patient_payments_collection_view,
        name="patient-payments-collection",
    ),
    path(
        "patient/appointments/<int:appointment_id>/payment-intent",
        patient_appointment_payment_intent_view,
        name="patient-appointment-payment-intent",
    ),
    # --- Admin ---
    path(
        "admin/payments",
        admin_payments_collection_view,
        name="admin-payments-collection",
    ),
    path(
        "admin/payments/<int:payment_id>/mark-succeeded",
        admin_payment_mark_succeeded_view,
        name="admin-payment-mark-succeeded",
    ),
    path(
        "admin/payments/<int:payment_id>/mark-failed",
        admin_payment_mark_failed_view,
        name="admin-payment-mark-failed",
    ),
]
