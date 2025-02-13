from django.urls import path

from .views import (
    register, confirm_account, get_token_pair,
    token_refresh, resend_account_activation, logout, user_details,
)

app_name = "user_management"

urlpatterns = [
    path("register/", register, name="register"),
    path(
        "confirm-account/<str:uid>/<str:token>/",
        confirm_account,
        name="confirm_account",
    ),
    path("login/", get_token_pair, name="token_obtain_pair"),
    path("token/refresh/", token_refresh, name="token_refresh"),
    path(
            "resend-account-activation/",
            resend_account_activation,
            name="resend_account_activation",
        ),
    path("logout/", logout, name="logout"),
    path("user/", user_details, name="user_details"),
]
