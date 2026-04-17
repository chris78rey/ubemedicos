from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from apps.audits.models import AuditEvent
from apps.catalogs.models import Specialty
from .models import (
    ProfessionalProfile,
    ProfessionalDocument,
    ProfessionalVerificationSubmission,
)


class ProfessionalVerificationApiTests(TestCase):
    def setUp(self):
        User = get_user_model()

        self.prof_user = User.objects.create_user(
            email="proapi@test.local",
            password="Pro123456!",
            first_name="Ana",
            last_name="Ruiz",
            role="professional",
            is_email_verified=True,
        )

        self.admin_user = User.objects.create_user(
            email="adminapi@test.local",
            password="Admin123!",
            first_name="Admin",
            last_name="Test",
            role="admin",
            is_staff=True,
        )

        self.specialty = Specialty.objects.create(name="Medicina General")

        self.profile = ProfessionalProfile.objects.create(
            user=self.prof_user,
            specialty=self.specialty,
            license_number="LIC-API-001",
            city="Quito",
            province="Pichincha",
        )

        login = self.client.post(
            "/api/v1/auth/login",
            data='{"email":"proapi@test.local","password":"Pro123456!"}',
            content_type="application/json",
        )
        self.token = login.json()["access_token"]

    def _auth_headers(self):
        return {"HTTP_AUTHORIZATION": f"Bearer {self.token}"}

    def _pdf_file(self, name="doc.pdf", content=b"%PDF-1.4 test file"):
        return SimpleUploadedFile(name, content, content_type="application/pdf")

    def test_get_verification_status(self):
        response = self.client.get(
            "/api/v1/professional/verification/status",
            **self._auth_headers(),
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("profile", response.json())
        self.assertEqual(
            response.json()["profile"]["verification_status"],
            ProfessionalProfile.VerificationStatus.DRAFT,
        )

    def test_upload_document(self):
        response = self.client.post(
            "/api/v1/professional/documents",
            data={
                "document_type": ProfessionalDocument.DocumentType.ID,
                "file": self._pdf_file("id.pdf"),
            },
            **self._auth_headers(),
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            ProfessionalDocument.objects.filter(
                professional=self.profile,
                document_type=ProfessionalDocument.DocumentType.ID,
            ).exists()
        )

    def test_upload_same_required_document_reuses_record(self):
        first = self.client.post(
            "/api/v1/professional/documents",
            data={
                "document_type": ProfessionalDocument.DocumentType.TITLE,
                "file": self._pdf_file("title_v1.pdf"),
            },
            **self._auth_headers(),
        )
        self.assertEqual(first.status_code, 201)

        second = self.client.post(
            "/api/v1/professional/documents",
            data={
                "document_type": ProfessionalDocument.DocumentType.TITLE,
                "file": self._pdf_file("title_v2.pdf"),
            },
            **self._auth_headers(),
        )
        self.assertEqual(second.status_code, 201)

        self.assertEqual(
            ProfessionalDocument.objects.filter(
                professional=self.profile,
                document_type=ProfessionalDocument.DocumentType.TITLE,
            ).count(),
            1,
        )

    def test_submit_verification_success(self):
        self.client.post(
            "/api/v1/professional/documents",
            data={
                "document_type": ProfessionalDocument.DocumentType.ID,
                "file": self._pdf_file("id.pdf"),
            },
            **self._auth_headers(),
        )
        self.client.post(
            "/api/v1/professional/documents",
            data={
                "document_type": ProfessionalDocument.DocumentType.TITLE,
                "file": self._pdf_file("title.pdf"),
            },
            **self._auth_headers(),
        )
        self.client.post(
            "/api/v1/professional/documents",
            data={
                "document_type": ProfessionalDocument.DocumentType.LICENSE,
                "file": self._pdf_file("license.pdf"),
            },
            **self._auth_headers(),
        )

        response = self.client.post(
            "/api/v1/professional/verification/submit",
            **self._auth_headers(),
        )

        self.assertEqual(response.status_code, 201)
        self.profile.refresh_from_db()
        self.assertEqual(
            self.profile.verification_status,
            ProfessionalProfile.VerificationStatus.SUBMITTED,
        )
        self.assertEqual(
            ProfessionalVerificationSubmission.objects.filter(
                professional=self.profile,
                status=ProfessionalVerificationSubmission.Status.SUBMITTED,
            ).count(),
            1,
        )

    def test_submit_verification_returns_blockers(self):
        response = self.client.post(
            "/api/v1/professional/verification/submit",
            **self._auth_headers(),
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("submission_blockers", response.json())
        self.assertGreater(len(response.json()["submission_blockers"]), 0)

    def test_list_verification_events(self):
        self.client.post(
            "/api/v1/professional/documents",
            data={
                "document_type": ProfessionalDocument.DocumentType.ID,
                "file": self._pdf_file("id.pdf"),
            },
            **self._auth_headers(),
        )
        self.client.post(
            "/api/v1/professional/documents",
            data={
                "document_type": ProfessionalDocument.DocumentType.TITLE,
                "file": self._pdf_file("title.pdf"),
            },
            **self._auth_headers(),
        )
        self.client.post(
            "/api/v1/professional/documents",
            data={
                "document_type": ProfessionalDocument.DocumentType.LICENSE,
                "file": self._pdf_file("license.pdf"),
            },
            **self._auth_headers(),
        )
        self.client.post(
            "/api/v1/professional/verification/submit",
            **self._auth_headers(),
        )

        response = self.client.get(
            "/api/v1/professional/verification/events",
            **self._auth_headers(),
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("items", response.json())
        self.assertGreaterEqual(len(response.json()["items"]), 1)

    def test_professional_can_download_own_document(self):
        upload_response = self.client.post(
            "/api/v1/professional/documents",
            data={
                "document_type": ProfessionalDocument.DocumentType.ID,
                "file": self._pdf_file("id_download.pdf"),
            },
            **self._auth_headers(),
        )
        self.assertEqual(upload_response.status_code, 201)

        document_id = upload_response.json()["id"]

        response = self.client.get(
            f"/api/v1/professional/documents/{document_id}/download",
            **self._auth_headers(),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(
            AuditEvent.objects.filter(
                event_type="professional_document_downloaded",
                entity_type="ProfessionalDocument",
                entity_id=str(document_id),
            ).exists()
        )
