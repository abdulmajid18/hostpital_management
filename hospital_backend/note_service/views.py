# views.py
import logging
from datetime import datetime

from django.contrib.auth import get_user_model
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from .dataclass import ChecklistItem, Priority, FrequencyType, PlanItem, ActionableStepsInput
from .encryption import EncryptionUtils
from .permissions import IsADoctor
from .rabbitmq_manager import RabbitMQManager
from .serializers import DoctorNoteSerializer
from .mongo_manager import MongoDBManager, ActionableStepsProcessor  #
from task_processing_service.schedular import StateScheduler

from task_processing_service.llm_generator import LLMProcessor, NoteInput

User = get_user_model()
mongo = MongoDBManager()
rabbitmq = RabbitMQManager()


@swagger_auto_schema(
    method="post",
    operation_summary="Create a Doctor Note",
    operation_description="""
    This endpoint allows doctors to create a medical note for a patient. 
    The note is stored in MongoDB.
    """,
    request_body=DoctorNoteSerializer,
    tags=["Note"],
    responses={
        201: openapi.Response(
            "Note Created Successfully", openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    "note_id": openapi.Schema(type=openapi.TYPE_STRING, description="The ID of the created note"),
                }
            )
        ),
        400: openapi.Response("Validation Error"),
        500: openapi.Response("Internal Server Error"),
    }
)
@api_view(["POST"])
@permission_classes([IsADoctor])  # No authentication required for now
def create_doctor_note(request):
    """
    Create a new doctor note.

    - Accepts `patient_id` (UUID) and `content` (text).
    - Stores the note in MongoDB.
    - Returns the note ID on success.
    """
    serializer = DoctorNoteSerializer(data=request.data, context={"request": request})
    if serializer.is_valid():
        doctor_note = serializer.save()
        try:
            note_id = mongo.create_note(doctor_note)
            message = doctor_note.to_dict()
            return Response({"note_id": note_id, "note": message.get("content")}, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


logger = logging.getLogger(__name__)
db_manager = MongoDBManager()
scheduler = StateScheduler(db_manager, logger)
processor = ActionableStepsProcessor(db_manager, scheduler, logger)
llm_processor = LLMProcessor()


@api_view(["GET"])
@permission_classes([AllowAny])
def generate_actionable_steps(request, patient_id):
    """
    API endpoint to create actionable steps based on the provided checklist and plan.
    """
    try:
        note = mongo.get_note_by_patient(patient_id)
        if not note:
            return Response({"message": "No note found for this patient"}, status=status.HTTP_404_NOT_FOUND)
        patient = User.objects.get(id=patient_id)
        decrypted_note = EncryptionUtils.decrypt_note(note.get("content"), patient.private_key)
        note = NoteInput(note_content=decrypted_note, note_id=note.get("note_id"), patient_id=note.get("patient_id"))
        rabbitmq.publish_note_for_training("notes", note.to_dict())
        return Response({"message": "Actionable steps Generating! Hit the generated action endpoint to check if ready",
                         "steps": "steps"},
                        status=status.HTTP_201_CREATED)
    except Exception as e:
        logger.error(f"Error creating actionable steps: {str(e)}")
        return Response({"error": "Internal Server Error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["GET"])
@permission_classes([AllowAny])
def get_due_notifications(request, patient_id):
    """Fetch due notifications."""
    try:
        note = mongo.get_note_by_patient(patient_id)
        if not note:
            return Response({"message": "No note found for this patient"}, status=status.HTTP_404_NOT_FOUND)
        note_id = note.get("note_id")
        notifications = scheduler.get_due_notifications(note_id=note_id, patient_id=patient_id)
        response_data = [
            {
                "note_id": notification["note_id"],
                "patient_id": notification["patient_id"],
                "description": notification["description"]
            }
            for notification in notifications
        ]

        return Response({"notifications": response_data}, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Error fetching due notifications: {e}")
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["PATCH"])
@permission_classes([AllowAny])
def check_in_notification(request, patient_id):
    """Mark a notification as completed (Check-in)."""
    try:

        note = mongo.get_note_by_patient(patient_id)
        if not note:
            return Response({"message": "No note found for this patient"}, status=status.HTTP_404_NOT_FOUND)
        note_id = note.get("note_id")

        if not note_id or not patient_id:
            return Response({"error": "Both note_id and patient_id are required."}, status=status.HTTP_400_BAD_REQUEST)

        scheduler.mark_completed(note_id, patient_id)
        logger.info(f"Checked in notification for patient {patient_id} on note {note_id}")

        return Response({"message": "Notification checked in successfully."}, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Error checking in notification: {e}")
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["GET"])
@permission_classes([IsADoctor])
def get_note_by_patient(request, patient_id: str):
    """Fetch the single note for a specific patient"""
    try:
        note = mongo.get_note_by_patient(patient_id)
        if not note:
            return Response({"message": "No note found for this patient"}, status=status.HTTP_404_NOT_FOUND)
        patient = User.objects.get(id=patient_id)
        decrypted_note = EncryptionUtils.decrypt_note(note.get("content"), patient.private_key)
        return Response({"note": decrypted_note}, status=status.HTTP_200_OK)

    except User.DoesNotExist:
        return Response({"error": "Patient not found"}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["GET"])
@permission_classes([AllowAny])
def get_actionable_steps(request, patient_id):
    """API to fetch actionable steps using a patient_id"""
    try:
        note = mongo.get_note_by_patient(patient_id)
        if not note:
            return Response({"message": "No note found for this patient"}, status=status.HTTP_404_NOT_FOUND)

        note_id = note.get("note_id")
        steps = processor.get_actionable_steps_by_note_id(note_id)

        if not steps:
            return Response({"status": "Generating... check back in 2 or 3 minutes"}, status=status.HTTP_202_ACCEPTED)

        return Response({"actionable_steps": steps}, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
