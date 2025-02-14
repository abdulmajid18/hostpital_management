from django.urls import path
from .views import create_doctor_note, get_due_notifications, check_in_notification, \
    get_note_by_patient, get_actionable_steps, generate_actionable_steps

app_name = "note"

urlpatterns = [
    path("create/", create_doctor_note, name="create_doctor_note"),
    path("view/<str:patient_id>/", get_note_by_patient, name="get_note_by_patient"),
    path("generate-action/<str:patient_id>/", generate_actionable_steps, name="generate_action"),
    path("notifications/due/<str:patient_id>/", get_due_notifications, name="get_due_notifications"),
    path("notifications/check-in/<str:patient_id>", check_in_notification, name="check_in_notification"),
    path("patient-note-actionable-steps/<str:patient_id>/", get_actionable_steps, name="get_actionable_steps"),
]
