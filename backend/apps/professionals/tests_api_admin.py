import json
from pathlib import Path
from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.audits.models import AuditEvent
from apps.catalogs.models import Specialty
from .api_views import PROFESSIONAL_UPLOADS_DIR
from .models import (
    ProfessionalProfile,
    ProfessionalDocument,
    ProfessionalVerificationSubmission,
)


class ProfessionalVerificationAdminApiTests(TestCase):
    def setUp(self):
        User = get_user_model()

        self.admin_user = User.objects.create_user(
            email="admin.review@test.local",
            password="Admin123!",
            first_name="Admin",
            last_name="Reviewer",
            role="admin",
            is_staff=True,
        )

        self.prof_user = User.objects.create_user(
            email="prof.for.review@test.local",
            password="Pro123456!",
            first_name="Juan",
            last_name="Perez",
            role="professional",
            is_email_verified=True,
        )

        self.specialty = Specialty.objects.create(name="Cardiología")

        self.profile = ProfessionalProfile.objects.create(
            user=self.prof_user,
            specialty=self.specialty,
            license_number="CARDIO-001",
            city="Guayaquil",
            province="Guayas",
        )

        # Create docs
        self.doc_id = ProfessionalDocument.objects.create(
            professional=self.profile,
            document_type=ProfessionalDocument.DocumentType.ID,
            file_path="media/prof/id.pdf",
            original_name="id.pdf",
        )
        self.doc_title = ProfessionalDocument.objects.create(
            professional=self.profile,
            document_type=ProfessionalDocument.DocumentType.TITLE,
            file_path="media/prof/title.pdf",
            original_name="title.pdf",
        )
        self.doc_license = ProfessionalDocument.objects.create(
            professional=self.profile,
            document_type=ProfessionalDocument.DocumentType.LICENSE,
            file_path="media/prof/license.pdf",
            original_name="license.pdf",
        )

        self.real_doc_dir = PROFESSIONAL_UPLOADS_DIR / str(self.profile.id)
        self.real_doc_dir.mkdir(parents=True, exist_ok=True)

        self.real_doc_path = self.real_doc_dir / "id_admin_test.pdf"
        self.real_doc_path.write_bytes(b"%PDF-1.4 admin review test")

        self.doc_id.file_path = str(self.real_doc_path)
        self.doc_id.original_name = "id_admin_test.pdf"
        self.doc_id.save(update_fields=["file_path", "original_name"])

        # Submit
        login_prof = self.client.post(
            "/api/v1/auth/login",
            data='{"email":"prof.for.review@test.local","password":"Pro123456!"}',
            content_type="application/json",
        )
        token_prof = login_prof.json()["access_token"]

        self.client.post(
            "/api/v1/professional/verification/submit",
            **{"HTTP_AUTHORIZATION": f"Bearer {token_prof}"},
        )
        self.submission = ProfessionalVerificationSubmission.objects.get(
            professional=self.profile
        )

        # Auth as admin
        login_admin = self.client.post(
            "/api/v1/auth/login",
            data='{"email":"admin.review@test.local","password":"Admin123!"}',
            content_type="application/json",
        )
        self.admin_token = login_admin.json()["access_token"]

    def _auth_headers(self):
        return {"HTTP_AUTHORIZATION": f"Bearer {self.admin_token}"}

    def test_list_submissions(self):
        response = self.client.get(
            "/api/v1/admin/professional-verifications",
            **self._auth_headers(),
        )
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(len(response.json()["items"]), 1)

    def test_get_submission_detail(self):
        response = self.client.get(
            f"/api/v1/admin/professional-verifications/{self.submission.id}",
            **self._auth_headers(),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["submission"]["id"], self.submission.id)
        self.assertIn("documents", response.json())

    def test_assign_submission(self):
        response = self.client.post(
            f"/api/v1/admin/professional-verifications/{self.submission.id}/assign",
            data=json.dumps({}),  # Assigns to self
            content_type="application/json",
            **self._auth_headers(),
        )
        self.assertEqual(response.status_code, 200)
        self.submission.refresh_from_db()
        self.assertEqual(self.submission.assigned_admin, self.admin_user)

    def test_start_review(self):
        response = self.client.post(
            f"/api/v1/admin/professional-verifications/{self.submission.id}/start-review",
            **self._auth_headers(),
        )
        self.assertEqual(response.status_code, 200)
        self.submission.refresh_from_db()
        self.assertEqual(
            self.submission.status, ProfessionalVerificationSubmission.Status.UNDER_REVIEW
        )

    def test_review_document(self):
        response = self.client.post(
            f"/api/v1/admin/professional-verifications/{self.submission.id}/documents/{self.doc_id.id}/review",
            data=json.dumps({"decision": "approved", "notes": "Todo bien"}),
            content_type="application/json",
            **self._auth_headers(),
        )
        self.assertEqual(response.status_code, 200)
        self.doc_id.refresh_from_db()
        self.assertEqual(self.doc_id.review_status, ProfessionalDocument.ReviewStatus.APPROVED)

    def test_request_correction_requires_notes(self):
        response = self.client.post(
            f"/api/v1/admin/professional-verifications/{self.submission.id}/request-correction",
            data=json.dumps({"notes": ""}),
            content_type="application/json",
            **self._auth_headers(),
        )
        self.assertEqual(response.status_code, 400)

    def test_approve_final_success(self):
        # Approve all docs first
        self.doc_id.review_status = ProfessionalDocument.ReviewStatus.APPROVED
        self.doc_id.save()
        self.doc_title.review_status = ProfessionalDocument.ReviewStatus.APPROVED
        self.doc_title.save()
        self.doc_license.review_status = ProfessionalDocument.ReviewStatus.APPROVED
        self.doc_license.save()

        response = self.client.post(
            f"/api/v1/admin/professional-verifications/{self.submission.id}/approve",
            data=json.dumps({"notes": "Excelente"}),
            content_type="application/json",
            **self._auth_headers(),
        )
        self.assertEqual(response.status_code, 200)
        self.submission.refresh_from_db()
        self.profile.refresh_from_db()
        self.assertEqual(
            self.submission.status, ProfessionalVerificationSubmission.Status.APPROVED
        )
        self.assertEqual(
            self.profile.verification_status, ProfessionalProfile.VerificationStatus.APPROVED
        )

    def test_forbidden_for_professional(self):
        login_prof = self.client.post(
            "/api/v1/auth/login",
            data='{"email":"prof.for.review@test.local","password":"Pro123456!"}',
            content_type="application/json",
        )
        token_prof = login_prof.json()["access_token"]
        
        response = self.client.get(
            "/api/v1/admin/professional-verifications",
            **{"HTTP_AUTHORIZATION": f"Bearer {token_prof}"},
        )
        self.assertEqual(response.status_code, 403)

    def test_admin_can_download_document_from_submission(self):
        response = self.client.get(
            f"/api/v1/admin/professional-verifications/{self.submission.id}/documents/{self.doc_id.id}/download",
            **self._auth_headers(),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(
            AuditEvent.objects.filter(
                event_type="admin_professional_document_downloaded",
                entity_type="ProfessionalDocument",
                entity_id=str(self.doc_id.id),
            ).exists()
        )
