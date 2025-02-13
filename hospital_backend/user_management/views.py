from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.db import transaction
from django.utils.http import urlsafe_base64_decode
from rest_framework import status
from rest_framework.decorators import permission_classes, api_view
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .models import get_object_or_none
from .serializers import UserSerializer, MyTokenObtainPairSerializer, TokenResponseSerializer, RefreshTokenSerializer, \
    ResendAccountActivationEmailSerializer, UserDetailsSerializer
from .utils.email import send_activation_email

from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema

User = get_user_model()


class RegisterView(GenericAPIView):
    """
    post:
    Register a new user it could be either a Doctor or Patient.

    - Request Body: UserSerializer
    - Response: RegistrationResponseSerializer
    """

    serializer_class = UserSerializer
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        request_body=UserSerializer,
        responses={
            201: openapi.Response(
                description="User registered successfully",
                examples={
                    "application/json": {
                        "message": "Registration successful! Please check your email for account activation "
                                   "instructions. Resend if not received"
                    }
                },
            ),
            400: openapi.Response(
                description="Bad Request",
                examples={
                    "application/json": {
                        "error": "Validation errors"
                    }
                },
            ),
            500: openapi.Response(
                description="Internal Server Error",
                examples={
                    "application/json": {
                        "error": "Internal Server Error"
                    }
                },
            ),
        },
        tags=["Authentication"],
    )
    @transaction.atomic
    def post(self, request):
        serializer = UserSerializer(data=request.data)
        if serializer.is_valid():
            try:
                user = serializer.save()
                sent = send_activation_email(request, user)
                if sent:
                    message = {
                        "message": "Registration successful! Please check your email for account activation "
                                   "instructions. Resend if not received"
                    }
                    return Response(message, status=status.HTTP_201_CREATED)
                else:
                    return Response(
                        {"message": "Email not sent, try again"},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    )
            except Exception:
                return Response(
                    {"error": "Internal Server Error"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@swagger_auto_schema(
    method="get",
    operation_description="Confirm account via email link",
    responses={302: "Redirect to activation URL", 400: "Invalid  , Request a new one"},
    tags=["Authentication"],
)
@api_view(["GET"])
@permission_classes([AllowAny])
def confirm_account(request, uid, token):
    """
    get:
    Confirm account activation via email link.

    - URL Parameters: uid, token
    - Response: Redirects to activation URL on success or returns a 400 error message
    """
    try:
        uid = urlsafe_base64_decode(uid).decode()
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user and default_token_generator.check_token(user, token):
        user.is_verified = True
        user.is_active = True
        user.save()
        return Response(
            {"message": "Account activated successfully"},
            status=status.HTTP_200_OK,
        )
    else:
        return Response(
            {"message": "Invalid token, Request a new one"},
            status=status.HTTP_400_BAD_REQUEST,
        )


class ObtainCustomizedTokenView(TokenObtainPairView):
    permission_classes = [AllowAny]
    serializer_class = MyTokenObtainPairSerializer

    @swagger_auto_schema(
        operation_description="Obtain a new JWT token pair (access and refresh tokens).",
        request_body=MyTokenObtainPairSerializer,
        responses={200: TokenResponseSerializer()},
        tags=["Authentication"],
    )
    def post(self, request, *args, **kwargs):
        """
        Obtain a new JWT token pair (access and refresh tokens).
        """
        return super().post(request, *args, **kwargs)


class CustomTokenRefreshView(TokenRefreshView):
    @swagger_auto_schema(
        operation_summary="Refresh JWT Token",
        operation_description="This endpoint allows you to refresh your JWT token by providing a valid refresh token. "
                              "The response will contain a new access token.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "refresh": openapi.Schema(
                    type=openapi.TYPE_STRING, description="Refresh token"
                ),
            },
            required=["refresh"],
        ),
        responses={
            200: openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    "access": openapi.Schema(
                        type=openapi.TYPE_STRING, description="New access token"
                    ),
                },
            ),
            401: "Unauthorized - Invalid or expired token",
        },
        tags=["Authentication"],
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

    """
    post:
    Log out the user by invalidating the refresh token.

    - Request Body: RefreshTokenSerializer
    - Response: 204 No Content
    """

    serializer_class = RefreshTokenSerializer
    permission_classes = (IsAuthenticated,)

    @swagger_auto_schema(
        operation_description="Log out the user by invalidating the refresh token.",
        request_body=RefreshTokenSerializer,
        responses={204: "No Content"},
        tags=["Authentication"],
    )
    def post(self, request, *args):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


@swagger_auto_schema(
    method="post",
    operation_summary="Resend activation email if expired",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            "email": openapi.Schema(type=openapi.TYPE_STRING),
        },
        required=["email"],
    ),
    responses={
        200: "Activation email resent successfully",
        400: "User is already active",
        500: "Couldn't send email",
    },
    tags=["Authentication"],
)
@api_view(["POST"])
@transaction.atomic
@permission_classes([AllowAny])
def resend_account_activation(request):
    """
    post:
    Request a new account activation email.

    - Request Body:
        "email": "string"
    - Response:
        200 OK - Activation email sent successfully
        400 Bad Request - Invalid request or user does not exist
    """
    data = request.data
    serializer = ResendAccountActivationEmailSerializer(data=data)
    email = data.get("email")

    if serializer.is_valid() and email:
        user = get_object_or_none(User, email=email)

        if user and user.is_verified:
            return Response(
                {"error": "User is already active"}, status=status.HTTP_400_BAD_REQUEST
            )
        elif user:
            sent = send_activation_email(request, user)
            if sent:
                return Response(
                    {"message": "Activation email resent successfully."},
                    status=status.HTTP_200_OK,
                )
            else:
                return Response(
                    {"error": "Couldn't send email"}, status=status.HTTP_400_BAD_REQUEST
                )

        return Response(
            {"error": "email not recognized"}, status=status.HTTP_400_BAD_REQUEST
        )

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LogoutView(GenericAPIView):
    """
    post:
    Log out the user by invalidating the refresh token.

    - Request Body: RefreshTokenSerializer
    - Response: 204 No Content
    """

    serializer_class = RefreshTokenSerializer
    permission_classes = (IsAuthenticated,)

    @swagger_auto_schema(
        operation_description="Log out the user by invalidating the refresh token.",
        request_body=RefreshTokenSerializer,
        responses={204: "No Content"},
        tags=["Authentication"],
    )
    def post(self, request, *args):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


@swagger_auto_schema(
    method="get",
    responses={200: UserDetailsSerializer()},
    security=[{"Bearer": []}],  # Specify Bearer token authentication
    operation_id="User Details",
    tags=["Authentication"],
    operation_description="""
    Retrieve details of the currently authenticated user.

    This endpoint returns details such as name, email, and role
    of the authenticated user. Once you include jwt as part of the request you should be authenticated

    - Response:
        200 OK - Details of the authenticated user
    """,
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def user_details(request):
    user = request.user
    serializer = UserDetailsSerializer(user)
    return Response(serializer.data)


register = RegisterView.as_view()
get_token_pair = ObtainCustomizedTokenView.as_view()
token_refresh = CustomTokenRefreshView().as_view()
logout = LogoutView.as_view()