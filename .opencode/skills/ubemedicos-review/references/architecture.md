# Ubemedicos Architecture

## Project Structure

```
ubemedicos/
├── backend/
│   ├── manage.py
│   ├── config/
│   │   ├── settings/
│   │   │   ├── base.py      # Base settings (DB, apps, AUTH_USER_MODEL)
│   │   │   ├── dev.py       # Dev settings (imports base, DEBUG=True)
│   │   │   └── prod.py      # Prod settings (imports base, DEBUG=False)
│   │   ├── urls.py
│   │   ├── wsgi.py
│   │   └── asgi.py
│   └── apps/
│       ├── users/            # Custom User model (AbstractUser, email auth)
│       ├── catalogs/        # Specialty model + seed command
│       ├── patients/        # PatientProfile
│       ├── professionals/   # ProfessionalProfile, Document, VerificationSubmission, VerificationEvent
│       ├── appointments/    # Appointment, AvailabilitySlot, AvailabilityBlock
│       ├── payments/        # Payment
│       └── audits/          # AuditEvent
├── infra/
│   └── docker-compose.yml   # PostgreSQL 16 Alpine (minimal config)
├── .env                     # Local env vars (DB credentials)
├── .env.example
├── requirements.txt
└── req/                     # Requirements documentation
```

## Docker PostgreSQL Config

Minimal configuration for development:
- Image: `postgres:16-alpine`
- Memory: 256MB limit
- CPU: 0.5
- Shared buffers: 64MB
- Max connections: 10
- WAL: minimal (no replication)

## AUTH_USER_MODEL

`users.User` using AbstractUser (not AbstractBaseUser + PermissionsMixin)

Key fields:
- `username = None` (removed)
- `email` (unique, USERNAME_FIELD)
- `role` (TextChoices)
- `is_email_verified` (BooleanField default=False)
- `created_at`, `updated_at` (auto_now_add/auto_now)

## Professional Verification Flow

```
[DRAFT] → can_submit_for_verification()
    ↓ (if blockers empty)
[SUBMITTED] → admin reviews
    ↓
[UNDER_REVIEW] → assigned to admin
    ↓
[APPROVED/REJECTED/NEEDS_CORRECTION/SUSPENDED]
```

Blockers checked:
- specialty required
- license_number required
- city, province required
- user first_name, last_name required
- Documents: ID, TITLE, LICENSE or SENESCYT required
- No rejected required documents
- No open submission exists

## Appointment Constraint

Unique constraint only for active appointments:
```python
UniqueConstraint(
    condition=Q(status__in=["pending_confirmation", "confirmed"]),
    fields=["professional", "scheduled_at"],
    name="uq_professional_slot_active_only"
)
```

Cancelled appointments don't block scheduling.
