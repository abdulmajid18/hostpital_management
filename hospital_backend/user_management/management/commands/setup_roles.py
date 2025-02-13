from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType

User = get_user_model()


class Command(BaseCommand):
    help = "Create default roles Doctor and Patient"

    def handle(self, *args, **kwargs):
        self.create_roles()

    def create_roles(self):
        roles = ["Doctor", "Patient"]

        # Create groups
        for role in roles:
            group, created = Group.objects.get_or_create(name=role)
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created role: {role}"))
            else:
                self.stdout.write(self.style.WARNING(f"Role {role} already exists"))

        # Assign permissions (optional)
        content_type = ContentType.objects.get_for_model(User)
        role_permissions = {
            "Doctor": ["view_patient_records", "update_prescription"],
            "Patient": ["view_own_records", "request_appointment"],
        }

        for role, perms in role_permissions.items():
            group = Group.objects.get(name=role)
            for perm in perms:
                permission, _ = Permission.objects.get_or_create(
                    codename=perm,
                    name=f'Can {perm.replace("_", " ")}',
                    content_type=content_type,
                )
                group.permissions.add(permission)

        self.stdout.write(self.style.SUCCESS("Roles and permissions have been set up successfully"))
