import io
import openpyxl
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile

from .models import Specialty

User = get_user_model()


class CatalogsApiTests(TestCase):
    def setUp(self):
        self.super_admin = User.objects.create_user(
            email="super@ubemedicos.com",
            password="password123",
            role="super_admin"
        )
        self.patient = User.objects.create_user(
            email="patient@ubemedicos.com",
            password="password123",
            role="patient"
        )

    def _get_token(self, user):
        from apps.users.token_service import create_access_token
        return create_access_token(user)

    def test_only_active_specialties_are_listed(self):
        Specialty.objects.create(name="Cardiología", is_active=True)
        Specialty.objects.create(name="Neurología", is_active=True)
        Specialty.objects.create(name="Temporal", is_active=False)

        response = self.client.get("/api/v1/catalogs/specialties")
        self.assertEqual(response.status_code, 200)

        names = [item["name"] for item in response.json()["items"]]
        self.assertIn("Cardiología", names)
        self.assertIn("Neurología", names)
        self.assertNotIn("Temporal", names)

    def test_upload_unauthorized(self):
        response = self.client.post("/api/v1/admin/catalogs/specialties/upload")
        self.assertEqual(response.status_code, 401)

    def test_upload_wrong_role(self):
        token = self._get_token(self.patient)
        response = self.client.post(
            "/api/v1/admin/catalogs/specialties/upload",
            HTTP_AUTHORIZATION=f"Bearer {token}"
        )
        self.assertEqual(response.status_code, 403)

    def test_upload_success_and_idempotency(self):
        # Setup existing and inactive
        Specialty.objects.create(name="Existente", is_active=True)
        Specialty.objects.create(name="Inactiva", is_active=False)
        
        # Create Excel in memory
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["Nombre de Especialidad"]) # Header
        ws.append(["Nueva Especialidad"])      # New
        ws.append(["Existente"])               # Existing
        ws.append(["Inactiva"])                # To Reactivate
        ws.append(["  con espacios  "])        # Trim check
        ws.append([""])                        # Blank row check
        
        excel_file = io.BytesIO()
        wb.save(excel_file)
        excel_file.seek(0)
        
        uploaded_file = SimpleUploadedFile(
            "test.xlsx",
            excel_file.read(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        token = self._get_token(self.super_admin)
        response = self.client.post(
            "/api/v1/admin/catalogs/specialties/upload",
            {"file": uploaded_file},
            HTTP_AUTHORIZATION=f"Bearer {token}"
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        summary = data["summary"]
        
        self.assertEqual(summary["created"], 2) # "Nueva Especialidad" and "con espacios"
        self.assertEqual(summary["existing"], 1)
        self.assertEqual(summary["reactivated"], 1)
        self.assertEqual(summary["blank_skipped"], 1)
        
        # Verify DB
        self.assertTrue(Specialty.objects.filter(name="Nueva Especialidad", is_active=True).exists())
        self.assertTrue(Specialty.objects.filter(name="Inactiva", is_active=True).exists())
        self.assertTrue(Specialty.objects.filter(name="con espacios", is_active=True).exists())
