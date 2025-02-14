# views.py
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status

from .rabbitmq_manager import RabbitMQManager
from .serializers import DoctorNoteSerializer
from .mongo_manager import MongoDBManager  #

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
