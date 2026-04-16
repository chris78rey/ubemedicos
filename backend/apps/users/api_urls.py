from django.urls import path

from .api_views import (
    auth_login_view,
    auth_logout_view,
    auth_me_view,
    users_me_view,
)

urlpatterns = [
    path("auth/login", auth_login_view, name="auth-login"),
    path("auth/logout", auth_logout_view, name="auth-logout"),
    path("auth/me", auth_me_view, name="auth-me"),
    path("users/me", users_me_view, name="users-me"),
]
