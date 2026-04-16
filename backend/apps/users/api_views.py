import json

from django.contrib.auth import authenticate
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from .api_auth import api_auth_required
from .token_service import create_access_token


def _parse_json_body(request):
    if not request.body:
        return {}
    try:
        return json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        raise ValueError("JSON inválido.")


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
    if user.role in {"super_admin", "admin"}:
        return "admin"
    if user.role == "professional":
        return "professional"
    if user.role == "patient":
        return "patient"
    return "unknown"


def _serialize_current_user(user):
    role_codes = _role_codes_for_user(user)
    return {
        "id": str(user.pk),
        "email": user.email,
        "status": "active" if user.is_active else "inactive",
        "is_email_verified": getattr(user, "is_email_verified", False),
        "role_codes": role_codes,
        "primary_role": _primary_role_for_user(user),
        "actor_type": _actor_type_for_user(user),
        "roles": [{"code": code} for code in role_codes],
        "first_name": user.first_name,
        "last_name": user.last_name,
        "phone": getattr(user, "phone", ""),
    }


@require_http_methods(["POST"])
def auth_login_view(request):
    try:
        payload = _parse_json_body(request)
    except ValueError as exc:
        return JsonResponse({"detail": str(exc)}, status=400)

    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""

    if not email or not password:
        return JsonResponse(
            {"detail": "Email y contraseña son obligatorios."},
            status=400,
        )

    user = authenticate(request, username=email, password=password)
    if not user or not user.is_active:
        return JsonResponse({"detail": "Credenciales inválidas."}, status=401)

    access_token = create_access_token(user)

    response = JsonResponse(
        {
            "access_token": access_token,
            "token_type": "bearer",
            "user": _serialize_current_user(user),
        }
    )
    response.set_cookie(
        "access_token",
        access_token,
        max_age=43200,
        httponly=False,
        secure=False,
        samesite="Lax",
        path="/",
    )
    return response


@require_http_methods(["POST"])
def auth_logout_view(request):
    response = JsonResponse({"detail": "Sesión cerrada."})
    response.delete_cookie("access_token", path="/")
    return response


@require_http_methods(["GET"])
@api_auth_required
def auth_me_view(request):
    return JsonResponse(_serialize_current_user(request.api_user))


@require_http_methods(["GET"])
@api_auth_required
def users_me_view(request):
    return JsonResponse(_serialize_current_user(request.api_user))
