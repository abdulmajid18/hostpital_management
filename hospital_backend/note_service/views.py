# views.py
import logging
from datetime import datetime

from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status

from .dataclass import ChecklistItem, Priority, FrequencyType, PlanItem, ActionableStepsInput
from .rabbitmq_manager import RabbitMQManager
from .serializers import DoctorNoteSerializer
from .mongo_manager import MongoDBManager, ActionableStepsProcessor  #
from task_processing_service.schedular import StateScheduler

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
@permission_classes([])  # No authentication required for now
def create_doctor_note(request):
    """
    Create a new doctor note.

    - Accepts `patient_id` (UUID) and `content` (text).
    - Stores the note in MongoDB.
    - Returns the note ID on success.
    """
    serializer = DoctorNoteSerializer(data=request.data)
    if serializer.is_valid():
        doctor_note = serializer.save()
        try:
            note_id = mongo.create_note(doctor_note)
            message = doctor_note.to_dict()
            rabbitmq.publish_note_for_training("notes", message)
            return Response({"note_id": str(note_id)}, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


logger = logging.getLogger(__name__)
db_manager = MongoDBManager()
scheduler = StateScheduler(db_manager, logger)
processor = ActionableStepsProcessor(db_manager, scheduler, logger)


@api_view(["GET"])
@permission_classes([AllowAny])
def create_actionable_steps(request):
    """
    API endpoint to create actionable steps based on the provided checklist and plan.
    """
    try:
        current_time = datetime.utcnow()
        patient_id = "patient123"
        note_id = "note789"
        checklist_items = [
            ChecklistItem(
                description="Check blood pressure",
                priority=Priority.HIGH
            ),
            ChecklistItem(
                description="Review medication list",
                priority=Priority.MEDIUM
            )
        ]
        plan_items = [
            # Morning and evening medication
            PlanItem(
                description="Take blood pressure medication",
                patient_id=patient_id,
                start_date=current_time,
                duration=7,  # 7 days
                frequency=FrequencyType.FIXED_TIME,
                specific_times=["09:00", "21:00"]
            ),
            # Every 4 hours
            PlanItem(
                description="Check temperature",
                patient_id=patient_id,
                start_date=current_time,
                duration=3,  # 3 days
                frequency=FrequencyType.INTERVAL_BASED,
                interval_hours=4
            ),
            # 3 times per day
            PlanItem(
                description="Do breathing exercises",
                patient_id=patient_id,
                start_date=current_time,
                duration=5,  # 5 days
                frequency=FrequencyType.FREQUENCY_BASED,
                times_per_day=3
            )]

        steps_input = ActionableStepsInput(
            note_id=note_id,
            checklist=checklist_items,
            plan=plan_items
        )

        step_ids = processor.create_actionable_steps(steps_input)
        logger.info("Creating actionable steps...")
        logger.info(f"Created {len(step_ids)} steps")

        return Response({"message": "Actionable steps created successfully", "step_ids": step_ids},
                        status=status.HTTP_201_CREATED)
    except Exception as e:
        logger.error(f"Error creating actionable steps: {str(e)}")
        return Response({"error": "Internal Server Error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["GET"])
@permission_classes([AllowAny])
def get_due_notifications(request):
    """Fetch due notifications."""
    try:
        patient_id = "patient123"
        note_id = "note789"
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


@api_view(["POST"])
@permission_classes([AllowAny])
def check_in_notification(request):
    """Mark a notification as completed (Check-in)."""
    try:
        note_id = "note789"
        patient_id = "patient123"

        if not note_id or not patient_id:
            return Response({"error": "Both note_id and patient_id are required."}, status=status.HTTP_400_BAD_REQUEST)

        scheduler.mark_completed(note_id, patient_id)
        logger.info(f"Checked in notification for patient {patient_id} on note {note_id}")

        return Response({"message": "Notification checked in successfully."}, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Error checking in notification: {e}")
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["GET"])
@permission_classes([AllowAny])
def get_note_by_patient(request):
    """Fetch the single note for a specific patient"""
    try:
        patient_id = "patient123"
        note = mongo.get_note_by_patient(patient_id)
        if note:
            return Response({"note": note}, status=status.HTTP_200_OK)
        else:
            return Response({"message": "No note found for this patient"}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["GET"])
@permission_classes([AllowAny])
def get_actionable_steps(request):
    """API to fetch actionable steps using a note ID."""
    try:
        note_id = "note789"
        steps = processor.get_actionable_steps_by_note_id(note_id)
        return Response({"actionable_steps": steps}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
