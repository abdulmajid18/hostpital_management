from rest_framework.permissions import BasePermission


class IsADoctor(BasePermission):
    """
    Custom permission to only allow Doctor to access certain views.
    """

    def has_permission(self, request, view):
        return (
                request.user
                and request.user.is_authenticated
                and request.user.groups.filter(name="Doctor").exists()
        )


class IsAPatient(BasePermission):
    """
    Custom permission to only allow Patient to access certain views.
    """

    def has_permission(self, request, view):
        return (
                request.user
                and request.user.is_authenticated
                and request.user.groups.filter(name="Patient").exists()
        )
