from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import User


class CustomUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("email", "first_name", "last_name", "role", "phone")


class CustomUserChangeForm(UserChangeForm):
    class Meta:
        model = User
        fields = "__all__"
