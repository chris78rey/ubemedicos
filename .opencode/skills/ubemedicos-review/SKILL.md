---
name: ubemedicos-review
description: Review Ubemedicos Django project status. Use when user asks "revisar proyecto", "estado del proyecto", "que se ha hecho", "como está la base", "checkpoint", "resumen del proyecto", or any query about checking the current state of the Ubemedicos medical appointments system.
---

# Ubemedicos Review

## Quick Status Check

```bash
# Docker
docker ps --format "table {{.Names}}\t{{.Status}}" | grep ubemedicos

# DB tables count
docker exec ubemedicos_postgres psql -U appuser -d appdb -c "SELECT COUNT(*) FROM pg_tables WHERE schemaname = 'public';"

# Django
cd backend && python manage.py check && python manage.py showmigrations | grep "\[ \]"
```

## Data Review

```bash
cd backend && python manage.py shell -c "
from django.contrib.auth import get_user_model
from apps.catalogs.models import Specialty
from apps.patients.models import PatientProfile
from apps.professionals.models import ProfessionalProfile
from apps.appointments.models import Appointment
from apps.payments.models import Payment
U = get_user_model()
print('=== Data Counts ===')
print('Users:', U.objects.count())
print('Specialties:', Specialty.objects.count())
print('Patients:', PatientProfile.objects.count())
print('Professionals:', ProfessionalProfile.objects.count())
print('Appointments:', Appointment.objects.count())
print('Payments:', Payment.objects.count())
print()
print('=== Demo Users ===')
for u in U.objects.filter(email__contains='demo.local').values('email', 'role'):
    print(f\"  {u['email']} ({u['role']})\")
"
```

## Architecture Summary

| Component | Technology |
|-----------|------------|
| Backend | Django 5.1+ |
| Database | PostgreSQL 16 (Docker Alpine) |
| Auth | Custom User (email-based) |
| Apps | users, catalogs, patients, professionals, appointments, payments, audits |

## Database Schema (21 tables)

- **users**: `users_user`
- **catalogs**: `catalogs_specialty`
- **patients**: `patients_profile`
- **professionals**: `professionals_profile`, `professionals_document`, `professionals_verification_submission`, `professionals_verification_event`
- **appointments**: `appointments_appointment`, `appointments_availability_slot`, `appointments_availability_block`
- **payments**: `payments_payment`
- **audits**: `audits_event`
- + Django system tables (auth, admin, sessions, contenttypes)

## Key Models

### User (users.User)
- Email-based auth (`USERNAME_FIELD = email`)
- Roles: super_admin, admin, privacy_auditor, professional, patient
- `is_email_verified` field added

### ProfessionalProfile
- `specialty` (FK to Specialty, required)
- `license_number` (unique, required)
- `verification_status`: draft → submitted → under_review → approved/rejected/needs_correction/suspended
- `get_submission_blockers()` method for validation workflow

### Appointment
- FK to PatientProfile and ProfessionalProfile
- `status`: pending_confirmation, confirmed, cancelled_by_patient/professional, completed, no_show
- Unique constraint on (professional, scheduled_at) only for active statuses

## Important Commands

```bash
# Start services
docker compose -f infra/docker-compose.yml up -d

# Django
python manage.py migrate
python manage.py createsuperuser
python manage.py seed_initial_data        # Load demo data
python manage.py seed_initial_data --reset-demo  # Reset demo data

# Check
python manage.py check
python manage.py showmigrations
```

## Demo Credentials

| Role | Email | Password |
|------|-------|----------|
| Super Admin | superadmin@demo.local | Admin123! |
| Admin | admin@demo.local | Admin123! |
| Privacy Auditor | privacy@demo.local | Privacy123! |
| Patient | paciente@demo.local | Paciente123! |
| Professional | profesional@demo.local | Profesional123! |

## Detailed Reference

See `references/architecture.md` for full architecture details.

See `references/decisions.md` for key decisions from req/01-03.md.
