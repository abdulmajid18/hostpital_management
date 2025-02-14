# from rest_framework.decorators import api_view, permission_classes
# from rest_framework.permissions import AllowAny
#
# from hospital_backend.task_processing_service.llm_generator import LLMProcessor
#
# llm_processor = LLMProcessor()
#
#
# @api_view(["GET"])
# @permission_classes([AllowAny])
# def get_actionable_steps(request):
#     """API to fetch actionable steps using a note ID."""
#     try:
#         note_id = "note789"
#         steps = processor.get_actionable_steps_by_note_id(note_id)
#         return Response({"actionable_steps": steps}, status=status.HTTP_200_OK)
#     except Exception as e:
#         return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
