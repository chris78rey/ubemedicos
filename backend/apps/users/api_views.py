import json

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from apps.catalogs.models import Specialty
from apps.patients.models import PatientProfile
from apps.professionals.models import ProfessionalProfile
from .api_auth import api_auth_required
from .token_service import create_access_token


def _json_error(message, status=400, extra=None):
    payload = {"detail": message}
    if extra:
        payload.update(extra)
    return JsonResponse(payload, status=status)


def _parse_json_body(request):
    if not request.body:
        return {}
    try:
        return json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        raise ValueError("JSON inválido.")


def _set_access_cookie(response, access_token: str):
    response.set_cookie(
        getattr(settings, "AUTH_COOKIE_NAME", "access_token"),
        access_token,
        max_age=getattr(settings, "AUTH_TOKEN_MAX_AGE_SECONDS", 43200),
        httponly=False,
        secure=False,
        samesite="Lax",
        path="/",
    )


def _delete_access_cookie(response):
    response.delete_cookie(
        getattr(settings, "AUTH_COOKIE_NAME", "access_token"),
        path="/",
    )


def _role_codes_for_user(user) -> list[str]:
    if user.role == "super_admin":
        return [
            "super_admin",
            "admin_validation",
            "admin_support",
            "admin_moderation",
            "admin_privacy",
        ]
    if user.role == "admin":
        return ["admin_validation"]
    if user.role == "privacy_auditor":
        return ["privacy_auditor"]
    if user.role == "professional":
        return ["professional"]
    if user.role == "patient":
        return ["patient"]
    return []


def _primary_role_for_user(user) -> str | None:
    role_codes = _role_codes_for_user(user)
    return role_codes[0] if role_codes else None


def _actor_type_for_user(user) -> str:
    role_codes = _role_codes_for_user(user)
    if any(
        code in role_codes
        for code in [
            "super_admin",
            "admin_validation",
            "admin_support",
            "admin_moderation",
            "admin_privacy",
        ]
    ):
        return "admin"
    if "patient" in role_codes:
        return "patient"
    if "professional" in role_codes:
        return "professional"
    return "unknown"


def _serialize_current_user(user):
    role_codes = _role_codes_for_user(user)
    return {
        "id": str(user.pk),
        "email": user.email,
        "status": "active" if user.is_active else "inactive",
        "is_email_verified": bool(getattr(user, "is_email_verified", False)),
        "role_codes": role_codes,
        "primary_role": _primary_role_for_user(user),
        "actor_type": _actor_type_for_user(user),
        "roles": [{"code": code} for code in role_codes],
        "first_name": user.first_name,
        "last_name": user.last_name,
        "phone": getattr(user, "phone", ""),
    }


def _build_auth_response(user, status_code=200):
    access_token = create_access_token(user)
    response = JsonResponse(
        {
            "access_token": access_token,
            "token_type": "bearer",
            "user": _serialize_current_user(user),
        },
        status=status_code,
    )
    _set_access_cookie(response, access_token)
    return response


@csrf_exempt
@require_http_methods(["POST"])
def auth_login_view(request):
    try:
        payload = _parse_json_body(request)
    except ValueError as exc:
        return _json_error(str(exc), status=400)

    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""

    if not email or not password:
        return _json_error("Email y contraseña son obligatorios.", status=400)

    user = authenticate(request, username=email, password=password)
    if not user or not user.is_active:
        return _json_error("Credenciales inválidas.", status=401)

    return _build_auth_response(user, status_code=200)


@csrf_exempt
@require_http_methods(["POST"])
def auth_logout_view(request):
    response = JsonResponse({"detail": "Sesión cerrada."}, status=200)
    _delete_access_cookie(response)
    return response


@require_http_methods(["GET"])
@api_auth_required
def auth_me_view(request):
    return JsonResponse(_serialize_current_user(request.api_user), status=200)


@require_http_methods(["GET"])
@api_auth_required
def users_me_view(request):
    return JsonResponse(_serialize_current_user(request.api_user), status=200)


def _validate_common_registration_payload(payload):
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""
    first_name = (payload.get("first_name") or "").strip()
    last_name = (payload.get("last_name") or "").strip()
    phone = (payload.get("phone") or "").strip()

    if not email:
        raise ValueError("Email es obligatorio.")
    if not password:
        raise ValueError("Password es obligatorio.")
    if len(password) < 8:
        raise ValueError("Password debe tener al menos 8 caracteres.")
    if not first_name:
        raise ValueError("first_name es obligatorio.")
    if not last_name:
        raise ValueError("last_name es obligatorio.")

    return {
        "email": email,
        "password": password,
        "first_name": first_name,
        "last_name": last_name,
        "phone": phone,
        "national_id": (payload.get("national_id") or "").strip(),
    }


@csrf_exempt
@require_http_methods(["POST"])
def register_patient_view(request):
    User = get_user_model()

    try:
        payload = _parse_json_body(request)
        data = _validate_common_registration_payload(payload)
    except ValueError as exc:
        return _json_error(str(exc), status=400)

    if User.objects.filter(email=data["email"]).exists():
        return _json_error("Ya existe un usuario con ese email.", status=409)

    user = User.objects.create_user(
        email=data["email"],
        password=data["password"],
        first_name=data["first_name"],
        last_name=data["last_name"],
        phone=data["phone"],
        role="patient",
        is_email_verified=False,
    )

    PatientProfile.objects.create(
        user=user,
        national_id=data["national_id"],
    )

    return _build_auth_response(user, status_code=200)


@csrf_exempt
@require_http_methods(["POST"])
def register_professional_view(request):
    User = get_user_model()

    try:
        payload = _parse_json_body(request)
        data = _validate_common_registration_payload(payload)
    except ValueError as exc:
        return _json_error(str(exc), status=400)

    if User.objects.filter(email=data["email"]).exists():
        return _json_error("Ya existe un usuario con ese email.", status=409)

    specialty, _ = Specialty.objects.get_or_create(
        name="Medicina General",
        defaults={"is_active": True},
    )

    user = User.objects.create_user(
        email=data["email"],
        password=data["password"],
        first_name=data["first_name"],
        last_name=data["last_name"],
        phone=data["phone"],
        role="professional",
        is_email_verified=False,
    )

    ProfessionalProfile.objects.create(
        user=user,
        specialty=specialty,
        license_number=f"TEMP-LIC-{user.id}",
        city="",
        province="",
        bio="",
        public_profile_enabled=False,
        verification_status=ProfessionalProfile.VerificationStatus.DRAFT,
        consultation_fee=0,
        teleconsultation_fee=0,
        is_accepting_patients=False,
    )

    return _build_auth_response(user, status_code=200)
