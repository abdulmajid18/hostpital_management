import uuid
from datetime import datetime

from rest_framework import serializers
from .dataclass import DoctorNote


class DoctorNoteSerializer(serializers.Serializer):
    patient_id = serializers.CharField()
    content = serializers.CharField()

    def validate_patient_id(self, value):
        """Validate that patient_id is a valid UUID string."""
        try:
            uuid.UUID(value, version=4)
        except ValueError:
            raise serializers.ValidationError("Invalid patient_id. Must be a valid UUID string.")
        return value

    def create(self, validated_data):
        """Create a DoctorNote instance. doctor_id is set from request.user."""
        doctor_id = self.context["request"].user.id
        return DoctorNote(
            doctor_id=doctor_id,
            **validated_data
        )
