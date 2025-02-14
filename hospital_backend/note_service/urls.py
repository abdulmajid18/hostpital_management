from django.urls import path
from .views import create_doctor_note, create_actionable_steps, get_due_notifications, check_in_notification, \
    get_note_by_patient, get_actionable_steps

app_name = "note"

urlpatterns = [
    path("create/", create_doctor_note, name="create_doctor_note"),
    path("generate-action/", create_actionable_steps, name="test"),
    path("notifications/due/", get_due_notifications, name="get_due_notifications"),
    path("notifications/check-in/", check_in_notification, name="check_in_notification"),
    path("patient-note/", get_note_by_patient, name="get_note_by_patient"),
    path("patient-note-actionable-steps/", get_actionable_steps, name="get_actionable_steps"),
]
