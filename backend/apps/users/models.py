from django.db import models
from django.contrib.auth.models import AbstractUser
from .managers import UserManager


class User(AbstractUser):
    class Role(models.TextChoices):
        SUPER_ADMIN = "super_admin", "Super Admin"
        ADMIN = "admin", "Admin"
        PRIVACY_AUDITOR = "privacy_auditor", "Privacy Auditor"
        PROFESSIONAL = "professional", "Professional"
        PATIENT = "patient", "Patient"

    username = None
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=30, choices=Role.choices)
    phone = models.CharField(max_length=30, blank=True)
    is_email_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name", "role"]

    objects = UserManager()

    class Meta:
        db_table = "users_user"
        indexes = [
            models.Index(fields=["email"], name="idx_users_email"),
            models.Index(fields=["role"], name="idx_users_role"),
            models.Index(fields=["is_active"], name="idx_users_active"),
        ]

    def __str__(self):
        return self.email
