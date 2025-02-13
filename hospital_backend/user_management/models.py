import uuid
from enum import Enum

from django.conf import settings
from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser, Group
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken


def get_object_or_none(model, **kwargs):
    try:
        result = model.objects.get(**kwargs)
    except model.DoesNotExist:
        result = None
    return result


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("The Email field must be set")
        email = self.normalize_email(email)
        extra_fields.setdefault("username", email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email, password, **extra_fields)


import enum


class UserRole(enum.Enum):
    PATIENT = "Patient"
    DOCTOR = "Doctor"

    @classmethod
    def choices(cls):
        return [(role.value, role.value) for role in cls]


class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=150, blank=True)
    email = models.EmailField(verbose_name="email", max_length=255, unique=True)
    otp_email = models.CharField(max_length=10, null=True, blank=True)
    is_active = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    groups = models.ManyToManyField(
        Group, related_name="authentication_user_set", blank=True
    )
    user_permissions = models.ManyToManyField(
        "auth.Permission",
        related_name="authentication_user_set",
        blank=True,
        help_text="Specific permissions for this user.",
        verbose_name="user permissions",
    )

    objects = UserManager()

    REQUIRED_FIELDS = ["name", "role"]
    USERNAME_FIELD = "email"

    def tokens(self):
        refresh = RefreshToken.for_user(self)
        access = refresh.access_token
        access_token_lifetime = settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"]
        access_expiry = timezone.now() + access_token_lifetime
        return {
            "refresh": str(refresh),
            "access": str(access),
            "access_token_expiry": access_expiry.isoformat()
                                   + "Z",  # Append 'Z' to indicate UTC time
        }

    def get_role(self):
        """Retrieve the user's assigned role"""
        group = self.groups.first()
        return group.name if group else None

    @classmethod
    def is_otp_correct(cls, registrant_id, otp_code):
        user = get_object_or_none(User, id=registrant_id)
        if user and user.otp_email == otp_code:
            return True
        return False


from django.core.exceptions import ValidationError


class PatientDoctorAssignment(models.Model):
    patient = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='assigned_doctor',
        limit_choices_to={'groups__name': 'Patient'}  # Restrict choices based on groups
    )
    doctor = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='assigned_patients',
        limit_choices_to={'groups__name': 'Doctor'}  # Restrict choices based on groups
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.patient.name} -> {self.doctor.name}"

    def clean(self):
        """Ensure the patient and doctor belong to the correct groups"""
        if self.patient.get_role() != "Patient":
            raise ValidationError("The selected user must be a patient.")
        if self.doctor.get_role() != "Doctor":
            raise ValidationError("The selected user must be a doctor.")

        if PatientDoctorAssignment.objects.filter(patient=self.patient).exists():
            raise ValidationError("This patient is already assigned to a doctor.")

    def save(self, *args, **kwargs):
        self.clean()  # Run validation before saving
        super().save(*args, **kwargs)


class UserInvitationToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    sent_by = models.UUIDField()
    token = models.CharField(max_length=255, unique=True)
    used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        unique_together = ("user", "used")

    def is_expired(self):
        return timezone.now() > self.expires_at

    def mark_as_used(self):
        self.used = True
        self.save()

    @classmethod
    def validate_and_use_token(cls, token):
        try:
            activation_token = cls.objects.get(token=token)
        except cls.DoesNotExist:
            return False, "Invalid token, Contact Admin to resend"

        if activation_token.is_expired():
            return False, "Token has expired, Contact Admin to resend"
        if activation_token.used:
            return (
                False,
                "This token has already been used. Please contact admin if you need a new one.",
            )

        return True, activation_token
