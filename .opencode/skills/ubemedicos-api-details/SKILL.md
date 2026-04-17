---
name: ubemedicos-api-details
description: Details about the implemented API architecture in Ubemedicos. Use when user asks "cómo está la API", "detalle de perfiles", "catálogo de especialidades", "arquitectura de auditoría", or any query about how the API views and routes are structured for profiles and audits.
---

# Ubemedicos API Details

## Environment and Tools
The project uses a Python 3.12 virtual environment located at `.venv/` in the root.
- **Python Path**: `.venv/Scripts/python.exe`
- **Django Implementation**: Django 5.1 / 6.0 compatible API.
- **Activation**: `.venv\Scripts\activate` (Windows)

## Profile Management (Fases 1 & 2)

### Professionals API
- **Endpoint**: `/api/v1/professional/profile`
- **Controller**: `apps.professionals.profile_api_views.professional_profile_view`
- **Methods**: `GET`, `PATCH`
- **Fields (Updateable)**: `first_name`, `last_name`, `phone`, `specialty_id`, `license_number`, `bio`, `city`, `province`, `public_profile_enabled`, `is_accepting_patients`, `consultation_fee`, `teleconsultation_fee`.
- **Logic**: Atomic transaction updating both `User` and `ProfessionalProfile`. Generates `AuditEvent` on update.

### Patients API
- **Endpoint**: `/api/v1/patient/profile`
- **Controller**: `apps.patients.api_views.patient_profile_view`
- **Methods**: `GET`, `PATCH`
- **Fields (Updateable)**: `first_name`, `last_name`, `phone`, `birth_date` (YYYY-MM-DD), `gender`, `national_id`, `emergency_contact_name`, `emergency_contact_phone`.
- **Logic**: Atomic transaction updating both `User` and `PatientProfile`. Generates `AuditEvent` on update.

### Catalogs API
- **Endpoint**: `/api/v1/catalogs/specialties`
- **Controller**: `apps.catalogs.api_views.specialties_collection_view`
- **Method**: `GET` (Public)
- **Serialization**: `id`, `name`. Filters by `is_active=True`.

## Audit API (Block implementation)

### Endpoints
- `GET /api/v1/admin/audits/access-logs`: List logs (Admin/Auditor only).
- `GET /api/v1/admin/audits/access-logs/<id>`: Event details.
- `GET /api/v1/admin/audits/access-logs/export.csv`: Export up to 5000 rows.
- `GET /api/v1/users/me/audit-events`: My own traceability (Any authenticated user).

## Error Handling Pattern
Consistent JSON response format:
```json
{
  "detail": "Descriptive error message"
}
```

## Testing Strategy
- Cada módulo tiene su `tests_api.py`.
- Se usa `setUp` para crear usuarios con diferentes roles (admin, prof, patient).
- Se valida:
  - Control de acceso (Roles).
  - Integridad de datos (formatos, obligatorios).
  - Trazabilidad (se comprueba que `AuditEvent.objects.count()` aumente).
