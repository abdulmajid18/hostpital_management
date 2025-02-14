from django.conf import settings
from django.contrib.auth import get_user_model, authenticate
from django.utils import timezone
from django.contrib.auth.models import Group
from rest_framework import serializers
from rest_framework.fields import EmailField, ChoiceField, ListField, SerializerMethodField
from rest_framework.serializers import ModelSerializer, CharField, ValidationError, Serializer
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from .models import UserRole
from .utils.custom_exception import CustomException
from .models import PatientDoctorAssignment
from note_service.encryption import EncryptionUtils

User = get_user_model()


class UserSerializer(ModelSerializer):
    password = CharField(max_length=65, min_length=8, write_only=True)
    email = (EmailField(max_length=255, min_length=4),)
    name = CharField(max_length=255, min_length=2)
    role = ChoiceField(choices=UserRole.choices())

    class Meta:
        model = User
        fields = ["name", "email", "password", "role"]

    def validate(self, attrs):
        email = attrs.get("email", "")
        if User.objects.filter(email=email).exists():
            raise CustomException("email is already in use")
        return super().validate(attrs)

    def validate_role(self, value):
        """Ensure role is either 'Patient' or 'Doctor'"""
        if not Group.objects.filter(name=value).exists():
            raise CustomException("Invalid role. Choose either 'Patient' or 'Doctor'.")
        return value

    def create(self, validated_data):
        role_name = validated_data.pop("role")
        private_key, public_key = EncryptionUtils.generate_key_pair()
        user = User.objects.create_user(**validated_data)
        group = Group.objects.get(name=role_name)
        user.groups.add(group)
        user.public_key = public_key
        user.private_key = private_key
        user.save()
        return user


class TokenResponseSerializer(Serializer):
    role = ListField(child=CharField())
    refresh = CharField()
    access = CharField()
    access_token_expiry = CharField()


class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    email = EmailField()
    password = CharField(write_only=True)

    def validate(self, attrs):
        email = attrs.get("email")
        password = attrs.get("password")

        if not email or not password:
            raise ValidationError({"error": "email and password are required."})

        user = authenticate(
            request=self.context.get("request"), email=email, password=password
        )

        if not user:
            raise ValidationError({"error": "Invalid credentials."})

        if not user.is_verified:
            raise ValidationError({"error": "Account not verified."})

        if not user.is_active:
            raise ValidationError({"error": "Account disabled, contact Admin."})

        refresh = self.get_token(user)
        user_groups = user.groups.all()
        group_names = [group.name for group in user_groups]
        access_token_lifetime = settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"]
        access_expiry = timezone.now() + access_token_lifetime
        return {
            "private_key": user.private_key,
            "role": group_names,
            "refresh": str(refresh),
            "access": str(refresh.access_token),
            "access_token_expiry": access_expiry.isoformat()
                                   + "Z",  # Append 'Z' to indicate UTC time,
        }

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        return token


class RefreshTokenSerializer(Serializer):
    refresh = CharField()

    def validate(self, attrs):
        self.token = attrs["refresh"]
        return attrs

    def save(self, **kwargs):
        try:
            RefreshToken(self.token).blacklist()
        except TokenError:
            raise CustomException("Token is invalid or expired")


class ResendAccountActivationEmailSerializer(Serializer):
    email = EmailField(allow_null=False, required=True)


class UserDetailsSerializer(ModelSerializer):
    role = SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "name",
            "email",
            "role",
        ]

    def get_role(self, obj):
        """Retrieve the first group name assigned to the user as the role"""
        group = obj.groups.first()
        return group.name if group else None


class PatientDoctorAssignmentSerializer(ModelSerializer):
    doctor_id = serializers.UUIDField(write_only=True)

    class Meta:
        model = PatientDoctorAssignment
        fields = ["patient", "doctor", "created_at", "doctor_id"]
        read_only_fields = ["created_at", "patient", "doctor"]

    def validate(self, data):
        doctor_id = data.pop("doctor_id", None)
        try:
            doctor = User.objects.get(id=doctor_id)
        except User.DoesNotExist:
            raise ValidationError("Doctor not found.")

        patient = self.context["request"].user
        if not doctor.groups.filter(name="Doctor").exists():
            raise ValidationError("Selected user is not a doctor.")
        if PatientDoctorAssignment.objects.filter(patient=patient).exists():
            raise CustomException("You are already assigned to a doctor.")
        data["doctor"] = doctor
        return data

    def create(self, validated_data):
        patient = self.context["request"].user
        doctor = validated_data["doctor"]
        # Remove existing assignment if present
        PatientDoctorAssignment.objects.filter(patient=patient).delete()
        # Assign the new doctor
        return PatientDoctorAssignment.objects.create(patient=patient, doctor=doctor)


class DoctorSerializer(ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "name", "email"]
