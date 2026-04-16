from django.core.exceptions import ValidationError
from django.test import TestCase
from django.contrib.auth import get_user_model

from apps.catalogs.models import Specialty
from apps.audits.models import AuditEvent
from .models import (
    ProfessionalProfile,
    ProfessionalDocument,
    ProfessionalVerificationSubmission,
    ProfessionalVerificationEvent,
)
from .services import (
    submit_professional_for_verification,
    assign_verification_submission,
    start_verification_review,
    review_professional_document,
    request_submission_correction,
    approve_verification_submission,
    reject_verification_submission,
)


class ProfessionalVerificationDecisionTests(TestCase):
    def setUp(self):
        self.User = get_user_model()

        self.admin_user = self.User.objects.create_user(
            email="admin@test.local",
            password="Admin123!",
            first_name="Admin",
            last_name="Test",
            role="admin",
            is_staff=True,
        )

        self.prof_user = self.User.objects.create_user(
            email="pro@test.local",
            password="Pro123456!",
            first_name="Ana",
            last_name="Ruiz",
            role="professional",
        )

        self.specialty = Specialty.objects.create(name="Medicina General")

        self.profile = ProfessionalProfile.objects.create(
            user=self.prof_user,
            specialty=self.specialty,
            license_number="LIC-123",
            city="Quito",
            province="Pichincha",
        )

    def _create_required_documents(self):
        self.doc_id = ProfessionalDocument.objects.create(
            professional=self.profile,
            document_type=ProfessionalDocument.DocumentType.ID,
            file_path="/tmp/id.pdf",
            original_name="id.pdf",
        )
        self.doc_title = ProfessionalDocument.objects.create(
            professional=self.profile,
            document_type=ProfessionalDocument.DocumentType.TITLE,
            file_path="/tmp/title.pdf",
            original_name="title.pdf",
        )
        self.doc_license = ProfessionalDocument.objects.create(
            professional=self.profile,
            document_type=ProfessionalDocument.DocumentType.LICENSE,
            file_path="/tmp/license.pdf",
            original_name="license.pdf",
        )

    def test_full_approval_flow(self):
        self._create_required_documents()

        submission = submit_professional_for_verification(
            professional=self.profile,
            actor=self.prof_user,
        )

        assign_verification_submission(
            submission=submission,
            actor=self.admin_user,
            assignee=self.admin_user,
        )

        start_verification_review(
            submission=submission,
            actor=self.admin_user,
        )

        review_professional_document(
            submission=submission,
            document=self.doc_id,
            actor=self.admin_user,
            decision=ProfessionalDocument.ReviewStatus.APPROVED,
            notes="Documento válido.",
        )
        review_professional_document(
            submission=submission,
            document=self.doc_title,
            actor=self.admin_user,
            decision=ProfessionalDocument.ReviewStatus.APPROVED,
            notes="Título válido.",
        )
        review_professional_document(
            submission=submission,
            document=self.doc_license,
            actor=self.admin_user,
            decision=ProfessionalDocument.ReviewStatus.APPROVED,
            notes="Licencia válida.",
        )

        approve_verification_submission(
            submission=submission,
            actor=self.admin_user,
            notes="Expediente aprobado.",
        )

        submission.refresh_from_db()
        self.profile.refresh_from_db()

        self.assertEqual(
            submission.status,
            ProfessionalVerificationSubmission.Status.APPROVED,
        )
        self.assertEqual(
            self.profile.verification_status,
            ProfessionalProfile.VerificationStatus.APPROVED,
        )
        self.assertEqual(
            AuditEvent.objects.filter(
                event_type="professional_verification_approved"
            ).count(),
            1,
        )

    def test_cannot_approve_when_required_document_is_pending(self):
        self._create_required_documents()

        submission = submit_professional_for_verification(
            professional=self.profile,
            actor=self.prof_user,
        )

        start_verification_review(
            submission=submission,
            actor=self.admin_user,
        )

        review_professional_document(
            submission=submission,
            document=self.doc_id,
            actor=self.admin_user,
            decision=ProfessionalDocument.ReviewStatus.APPROVED,
            notes="OK",
        )
        review_professional_document(
            submission=submission,
            document=self.doc_title,
            actor=self.admin_user,
            decision=ProfessionalDocument.ReviewStatus.APPROVED,
            notes="OK",
        )

        with self.assertRaises(ValidationError):
            approve_verification_submission(
                submission=submission,
                actor=self.admin_user,
                notes="No debería aprobar.",
            )

    def test_request_correction_flow(self):
        self._create_required_documents()

        submission = submit_professional_for_verification(
            professional=self.profile,
            actor=self.prof_user,
        )

        start_verification_review(
            submission=submission,
            actor=self.admin_user,
        )

        review_professional_document(
            submission=submission,
            document=self.doc_license,
            actor=self.admin_user,
            decision=ProfessionalDocument.ReviewStatus.REJECTED,
            notes="Licencia ilegible.",
        )

        request_submission_correction(
            submission=submission,
            actor=self.admin_user,
            notes="Debe volver a cargar la licencia en mejor calidad.",
        )

        submission.refresh_from_db()
        self.profile.refresh_from_db()

        self.assertEqual(
            submission.status,
            ProfessionalVerificationSubmission.Status.NEEDS_CORRECTION,
        )
        self.assertEqual(
            self.profile.verification_status,
            ProfessionalProfile.VerificationStatus.NEEDS_CORRECTION,
        )

    def test_reject_submission_requires_notes(self):
        self._create_required_documents()

        submission = submit_professional_for_verification(
            professional=self.profile,
            actor=self.prof_user,
        )

        start_verification_review(
            submission=submission,
            actor=self.admin_user,
        )

        with self.assertRaises(ValidationError):
            reject_verification_submission(
                submission=submission,
                actor=self.admin_user,
                notes="",
            )

    def test_reject_submission_changes_profile_status(self):
        self._create_required_documents()

        submission = submit_professional_for_verification(
            professional=self.profile,
            actor=self.prof_user,
        )

        start_verification_review(
            submission=submission,
            actor=self.admin_user,
        )

        reject_verification_submission(
            submission=submission,
            actor=self.admin_user,
            notes="Información inconsistente.",
        )

        submission.refresh_from_db()
        self.profile.refresh_from_db()

        self.assertEqual(
            submission.status,
            ProfessionalVerificationSubmission.Status.REJECTED,
        )
        self.assertEqual(
            self.profile.verification_status,
            ProfessionalProfile.VerificationStatus.REJECTED,
        )
        self.assertFalse(self.profile.public_profile_enabled)
        self.assertGreater(ProfessionalVerificationEvent.objects.count(), 0)
