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

## Autenticación (Auth)

### Login
- **Endpoint**: `/api/v1/auth/login`
- **Method**: `POST`
- **Payload**: `email`, `password`.
- **Response**: Genera un `access_token` (JWT/Django Token) y lo devuelve junto con el objeto `user`. También establece una cookie `access_token`.

### Registro
- **Pacientes**: `/api/v1/auth/register/patient`
- **Profesionales**: `/api/v1/auth/register/professional`
- **Method**: `POST`
- **Payload**: `email`, `password`, `first_name`, `last_name`, `phone`.
- **Logic**: Cria un usuario con el rol correspondiente y su perfil inicial (en `DRAFT` para profesionales).

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

## Problemas Conocidos y Soluciones (Troubleshooting)

### 1. Carga de Archivos via PATCH (Django Restriction)
Por defecto, Django no parsea datos multiparte (`multipart/form-data`) en peticiones `PATCH` o `PUT`. Esto causa que `request.FILES` aparezca vacío en el backend.
- **Solución**: Se implementó el helper `_load_multipart_files_if_patch` en `apps.professionals.api_views` que invoca manualmente al `MultiPartParser` si detecta este escenario.
- **Afecta a**: Reemplazo de documentos profesionales (`/api/v1/professional/documents/<id>`).

### 2. Protección CSRF en APIs
Aunque se use autenticación por Token (Bearer), si el frontend envía cookies (como `access_token`), el middleware `CsrfViewMiddleware` de Django puede bloquear peticiones `POST/PATCH` si no se incluye un token CSRF.
- **Solución**: Se decoraron las vistas de perfil y documentos con `@csrf_exempt`. La seguridad reside en la validación del token de sesión/JWT en el encabezado `Authorization`.

### 3. Validación de Tarifas (Decimales)
El backend usa `_parse_non_negative_decimal` que invoca directamente al constructor `Decimal()`.
- **Pitfall**: Si el usuario ingresa símbolos de moneda (ej. `$50`) o formatos no numéricos desde el frontend, la API devolverá un Error 400.
- **Recomendación**: Sanitizar el input en el frontend para enviar solo números y puntos decimales.

### 4. Unicidad de Licencia Profesional
El campo `license_number` es único en la base de datos (`unique=True`).
- **Comportamiento**: Al intentar guardar un perfil, el backend excluye el propio ID del usuario para permitir ediciones, pero bloquea si el número ya existe en otro registro.
- **Seed/Registro**: Durante el registro inicial se usa el formato `TEMP-LIC-{user_id}` para evitar colisiones antes de que el profesional cargue su dato real.

### 5. Filtros en Bandeja de Validación Administrativa
El panel de Validación Profesional (`/admin/professional-verifications`) permite filtrar expedientes.
- **Filtro "Mías"**: Filtra solicitudes asignadas al administrador actual (`assigned_admin_id`). 
- **Comportamiento**: Las solicitudes nuevas entran como `submitted` sin administrador asignado. Para evitar que queden ocultas, el filtro "Mías" ahora está desactivado por defecto (valor `false`).
- **Integración con Dashboard**: El Dashboard administrativo permite saltar directamente a una solicitud o al panel completo pasando parámetros `mine=0` o `submission_id` en la query string, los cuales son procesados automáticamente al cargar la página.

### 6. Restricciones de Asignación de Expedientes
El sistema bloquea la asignación de expedientes a administradores si no se cumplen ciertas reglas de estado.
- **Estados Permitidos**: Solo se pueden asignar solicitudes que estén en estado `submitted` o `under_review`.
- **Validación**: Si el expediente está en un estado final (aprobado o rechazado) o devuelto para corrección, el backend lanzará una `ValidationError` que se traduce en un error 400 en el frontend.
- **Uso de CSRF**: Al igual que el resto de la API administrativa, los endpoints de asignación y decisión final están marcados como `@csrf_exempt` para facilitar la gestión via Bearer Token desde el cliente.

### 7. Validación de Agenda y Disponibilidad
El módulo de citas (`apps.appointments`) aplica validaciones estrictas de tiempo para garantizar la integridad de la agenda.
- **Inversión de Tiempo**: Tanto en `AvailabilitySlot` como en `TimeBlock`, la hora/fecha de fin (`end_time`/`end_at`) debe ser estrictamente posterior a la de inicio.
- **Solapamiento (Overlaps)**: El sistema impide crear horarios regulares (`AvailabilitySlot`) o bloqueos (`TimeBlock`) que se crucen con registros existentes del mismo tipo y modalidad para el mismo profesional.
- **Bloqueos vs Citas**: No se puede crear un `TimeBlock` (vacaciones/bloqueo) si ya existen citas confirmadas o pendientes en ese rango de tiempo.
- **CSRF**: Todos los endpoints de gestión de agenda y ciclo de vida de citas (confirmar, cancelar, completar) están marcados como `@csrf_exempt` para compatibilidad con el flujo de Bearer Tokens del frontend.

## Testing Strategy
- Cada módulo tiene su `tests_api.py`.
- Se usa `setUp` para crear usuarios con diferentes roles (admin, prof, patient).
- Se valida:
  - Control de acceso (Roles).
  - Integridad de datos (formatos, obligatorios).
  - Trazabilidad (se comprueba que `AuditEvent.objects.count()` aumente).
