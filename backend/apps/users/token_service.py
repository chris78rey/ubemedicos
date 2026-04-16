from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner

TOKEN_SALT = "ubemedicos-auth-api"
signer = TimestampSigner(salt=TOKEN_SALT)


def create_access_token(user) -> str:
    return signer.sign(str(user.pk))


def resolve_access_token(token: str):
    if not token:
        return None

    try:
        raw_user_id = signer.unsign(
            token,
            max_age=getattr(settings, "AUTH_TOKEN_MAX_AGE_SECONDS", 43200),
        )
    except (BadSignature, SignatureExpired):
        return None

    User = get_user_model()

    try:
        user = User.objects.get(pk=raw_user_id, is_active=True)
    except User.DoesNotExist:
        return None

    return user
