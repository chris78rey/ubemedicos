# Key Decisions from Requirements

## req/01.md - Base Infrastructure

**Decisions:**
- Django 5.1+ with PostgreSQL 16
- Django runs local (not in Docker) for development
- PostgreSQL in Docker with named volume for persistence
- Environment variables in `.env`
- Separate settings: base.py, dev.py, prod.py
- App structure: backend/apps/{name}

**PostgreSQL Minimal Config:**
- Alpine image (smaller)
- 256MB memory limit
- 0.5 CPU
- shared_buffers=64MB
- max_connections=10
- synchronous_commit=off (dev only)

## req/02.md - Initial Models

**Decisions:**
- User model created before migrations
- AUTH_USER_MODEL = "users.User" set before migrate
- Separate apps per domain
- Custom UserManager for email-based auth
- Unique constraint on Appointment only for active statuses

**Apps Created:**
1. users - Custom User model
2. catalogs - Specialty
3. patients - PatientProfile
4. professionals - ProfessionalProfile, ProfessionalDocument
5. appointments - Appointment, AvailabilitySlot, AvailabilityBlock
6. payments - Payment
7. audits - AuditEvent

## req/03.md - Model Refinements

**Decisions:**
- AbstractUser instead of AbstractBaseUser+PermissionsMixin
- Added `is_email_verified` to User
- Added `get_submission_blockers()` and `can_submit_for_verification()` to ProfessionalProfile
- Created ProfessionalVerificationSubmission with unique constraint for open submissions
- Created ProfessionalVerificationEvent for audit trail
- Seed command with `--reset-demo` option
- Specialty model unchanged

**Seed Command Idempotency:**
- Uses `update_or_create` for users and profiles
- Uses `get_or_create` for specialties
- Never deletes specialties (shared catalog)
- Deletes only demo-specific data on reset

## Future Considerations

Per req/03.md notes:
- Frontend/API endpoints not yet built
- Professional submission rule enforced in service layer
- Admin is minimal (for testing only)
- Next logical step: REST API or admin polishing
