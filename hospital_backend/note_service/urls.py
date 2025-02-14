from django.urls import path
from .views import create_doctor_note

app_name = "note"

urlpatterns = [
    path("create/", create_doctor_note, name="create_doctor_note"),
]
