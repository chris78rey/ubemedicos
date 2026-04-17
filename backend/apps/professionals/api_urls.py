from django.urls import path

from .api_views import (
    # Professional views
    professional_verification_status_view,
    professional_documents_collection_view,
    professional_document_replace_view,
    professional_verification_submit_view,
    professional_verification_events_view,
    # Admin views
    admin_professional_verifications_collection_view,
    admin_professional_verifications_detail_view,
    admin_professional_verifications_assign_view,
    admin_professional_verifications_start_review_view,
    admin_professional_document_review_view,
    admin_professional_verifications_request_correction_view,
    admin_professional_verifications_approve_view,
    admin_professional_verifications_reject_view,
)

urlpatterns = [
    # --- Professional ---
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
    # --- Admin Review ---
    path(
        "admin/professional-verifications",
        admin_professional_verifications_collection_view,
        name="admin-professional-verifications-collection",
    ),
    path(
        "admin/professional-verifications/<int:submission_id>",
        admin_professional_verifications_detail_view,
        name="admin-professional-verifications-detail",
    ),
    path(
        "admin/professional-verifications/<int:submission_id>/assign",
        admin_professional_verifications_assign_view,
        name="admin-professional-verifications-assign",
    ),
    path(
        "admin/professional-verifications/<int:submission_id>/start-review",
        admin_professional_verifications_start_review_view,
        name="admin-professional-verifications-start-review",
    ),
    path(
        "admin/professional-verifications/<int:submission_id>/documents/<int:document_id>/review",
        admin_professional_document_review_view,
        name="admin-professional-document-review",
    ),
    path(
        "admin/professional-verifications/<int:submission_id>/request-correction",
        admin_professional_verifications_request_correction_view,
        name="admin-professional-verifications-request-correction",
    ),
    path(
        "admin/professional-verifications/<int:submission_id>/approve",
        admin_professional_verifications_approve_view,
        name="admin-professional-verifications-approve",
    ),
    path(
        "admin/professional-verifications/<int:submission_id>/reject",
        admin_professional_verifications_reject_view,
        name="admin-professional-verifications-reject",
    ),
]
