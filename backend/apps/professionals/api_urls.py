from django.urls import path

from .api_views import (
    professional_verification_status_view,
    professional_documents_collection_view,
    professional_document_replace_view,
    professional_verification_submit_view,
    professional_verification_events_view,
)

urlpatterns = [
    path(
        "professional/verification/status",
        professional_verification_status_view,
        name="professional-verification-status",
    ),
    path(
        "professional/documents",
        professional_documents_collection_view,
        name="professional-documents-collection",
    ),
    path(
        "professional/documents/<int:document_id>",
        professional_document_replace_view,
        name="professional-document-replace",
    ),
    path(
        "professional/verification/submit",
        professional_verification_submit_view,
        name="professional-verification-submit",
    ),
    path(
        "professional/verification/events",
        professional_verification_events_view,
        name="professional-verification-events",
    ),
]
