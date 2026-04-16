from functools import wraps

from django.http import JsonResponse

from .token_service import resolve_access_token


def _extract_bearer_token(request) -> str | None:
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        return header.removeprefix("Bearer ").strip()

    cookie_token = request.COOKIES.get("access_token")
    if cookie_token:
        return cookie_token.strip()

    return None


def get_api_user(request):
    token = _extract_bearer_token(request)
    if not token:
        return None
    return resolve_access_token(token)


def api_auth_required(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        user = get_api_user(request)
        if not user:
            return JsonResponse({"detail": "Authentication required."}, status=401)

        request.api_user = user
        return view_func(request, *args, **kwargs)

    return wrapped


def api_roles_required(*allowed_roles):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            user = get_api_user(request)
            if not user:
                return JsonResponse({"detail": "Authentication required."}, status=401)

            if user.role not in allowed_roles:
                return JsonResponse({"detail": "Forbidden."}, status=403)

            request.api_user = user
            return view_func(request, *args, **kwargs)

        return wrapped

    return decorator
