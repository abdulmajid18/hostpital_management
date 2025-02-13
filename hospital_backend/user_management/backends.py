from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from rest_framework import exceptions
from rest_framework_simplejwt.authentication import (
    JWTAuthentication as BaseJWTAuthentication,
)

User = get_user_model()


class EmailBackend(ModelBackend):
    def authenticate(self, request, email=None, password=None, **kwargs):
        UserModel = get_user_model()
        if not email or not password:
            return None
        try:
            email = email.lower().strip()
            user = UserModel.objects.get(email=email)
        except UserModel.DoesNotExist:
            return None
        if user.check_password(password):
            return user
        return None


class JWTAuthentication(BaseJWTAuthentication):
    def authenticate(self, request):
        raw_token = self.get_raw_token(request)
        if raw_token is None:
            return None

        validated_token = self.get_validated_token(raw_token)
        if validated_token is None:
            raise exceptions.AuthenticationFailed("Invalid token")

        return self.get_user(validated_token), validated_token

    def get_user(self, validated_token):
        user_id = validated_token[settings.SIMPLE_JWT["USER_ID_CLAIM"]]
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            raise exceptions.AuthenticationFailed("User not found")

    def get_raw_token(self, request):
        auth_header = self.get_header(request)
        if not auth_header:
            return None
        if not auth_header.startswith(settings.SIMPLE_JWT["AUTH_HEADER_TYPES"]):
            auth_header = f"Bearer {auth_header}"
        return auth_header.split()[1]

    def get_header(self, request):
        auth = request.headers.get("Authorization", None)
        return auth
