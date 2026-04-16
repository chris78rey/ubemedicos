import json
import shutil
import tempfile

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from apps.catalogs.models import Specialty
from apps.professionals.models import (
    ProfessionalProfile,
    ProfessionalDocument,
    ProfessionalVerificationSubmission,
)


class ProfessionalVerificationApiTests(TestCase):
    def setUp(self):
        User = get_user_model()

        self.temp_media_dir = tempfile.mkdtemp(prefix="test_media_prof_")
        self.original_media_root = getattr(settings, "MEDIA_ROOT", None)
        settings.MEDIA_ROOT = self.temp_media_dir
        self.addCleanup(self._cleanup_media)

        self.specialty = Specialty.objects.create(name="Medicina General")

        self.admin_user = User.objects.create_user(
            email="admin.api@test.local",
            password="Admin12345!",
            first_name="Admin",
            last_name="API",
            role="admin",
            is_staff=True,
            is_email_verified=True,
        )

        self.prof_user = User.objects.create_user(
            email="pro.api@test.local",
            password="Pro123456!",
            first_name="Ana",
            last_name="Ruiz",
            role="professional",
            phone="0999999999",
            is_email_verified=True,
        )

        self.profile = ProfessionalProfile.objects.create(
            user=self.prof_user,
            specialty=self.specialty,
            license_number="LIC-API-001",
            bio="Perfil de prueba",
            city="Quito",
            province="Pichincha",
            public_profile_enabled=False,
            verification_status=ProfessionalProfile.VerificationStatus.DRAFT,
            consultation_fee=20,
            teleconsultation_fee=15,
            is_accepting_patients=True,
        )

        self.prof_token = self._login("pro.api@test.local", "Pro123456!")
        self.admin_token = self._login("admin.api@test.local", "Admin12345!")

    def _cleanup_media(self):
        if self.original_media_root is not None:
            settings.MEDIA_ROOT = self.original_media_root
        shutil.rmtree(self.temp_media_dir, ignore_errors=True)

    def _login(self, email, password):
        response = self.client.post(
            "/api/v1/auth/login",
            data=json.dumps({"email": email, "password": password}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        return response.json()["access_token"]

    def _pdf_file(self, name):
        return SimpleUploadedFile(
            name,
            b"%PDF-1.4 prueba api\n%%EOF",
            content_type="application/pdf",
        )

    def _upload_required_documents(self):
        payloads = [
            ("id", "id.pdf"),
            ("title", "title.pdf"),
            ("license", "license.pdf"),
        ]

        for document_type, filename in payloads:
            response = self.client.post(
                "/api/v1/professionals/me/documents",
                data={
                    "document_type": document_type,
                    "file": self._pdf_file(filename),
                },
                HTTP_AUTHORIZATION=f"Bearer {self.prof_token}",
            )
            self.assertEqual(response.status_code, 201)

    def test_professional_profile_endpoint_returns_blockers(self):
        response = self.client.get(
            "/api/v1/professionals/me/profile",
            HTTP_AUTHORIZATION=f"Bearer {self.prof_token}",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()["profile"]
        self.assertEqual(payload["verification_status"], "draft")
        self.assertIn(
            "Debe subir documento de identidad.", payload["submission_blockers"]
        )

    def test_professional_can_upload_documents_and_submit(self):
        self._upload_required_documents()

        response = self.client.post(
            "/api/v1/professionals/me/submit-verification",
            HTTP_AUTHORIZATION=f"Bearer {self.prof_token}",
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload["submission"]["status"], "submitted")
        self.assertEqual(payload["profile"]["verification_status"], "submitted")

        self.profile.refresh_from_db()
        self.assertEqual(
            self.profile.verification_status,
            ProfessionalProfile.VerificationStatus.SUBMITTED,
        )

    def test_admin_can_review_and_approve_submission(self):
        self._upload_required_documents()

        submit_response = self.client.post(
            "/api/v1/professionals/me/submit-verification",
            HTTP_AUTHORIZATION=f"Bearer {self.prof_token}",
        )
        self.assertEqual(submit_response.status_code, 201)
        submission_id = submit_response.json()["submission"]["id"]

        assign_response = self.client.post(
            f"/api/v1/admin/verification/submissions/{submission_id}/assign",
            data=json.dumps({}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.admin_token}",
        )
        self.assertEqual(assign_response.status_code, 200)

        start_response = self.client.post(
            f"/api/v1/admin/verification/submissions/{submission_id}/start-review",
            HTTP_AUTHORIZATION=f"Bearer {self.admin_token}",
        )
        self.assertEqual(start_response.status_code, 200)

        docs = ProfessionalDocument.objects.filter(professional=self.profile).order_by(
            "id"
        )
        self.assertEqual(docs.count(), 3)

        for doc in docs:
            review_response = self.client.post(
                f"/api/v1/admin/verification/submissions/{submission_id}/documents/{doc.id}/review",
                data=json.dumps(
                    {
                        "decision": "approved",
                        "notes": f"Documento {doc.document_type} aprobado.",
                    }
                ),
                content_type="application/json",
                HTTP_AUTHORIZATION=f"Bearer {self.admin_token}",
            )
            self.assertEqual(review_response.status_code, 200)

        approve_response = self.client.post(
            f"/api/v1/admin/verification/submissions/{submission_id}/approve",
            data=json.dumps({"notes": "Expediente aprobado por API."}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.admin_token}",
        )
        self.assertEqual(approve_response.status_code, 200)
        self.assertEqual(approve_response.json()["submission"]["status"], "approved")

        self.profile.refresh_from_db()
        self.assertEqual(
            self.profile.verification_status,
            ProfessionalProfile.VerificationStatus.APPROVED,
        )

        submission = ProfessionalVerificationSubmission.objects.get(id=submission_id)
        self.assertEqual(
            submission.status, ProfessionalVerificationSubmission.Status.APPROVED
        )
