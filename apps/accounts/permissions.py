from rest_framework import permissions

from .models import User


class _RolePermission(permissions.BasePermission):
    required_role = None

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and (user.is_superuser or user.role == self.required_role)
        )


class IsCitizen(_RolePermission):
    required_role = User.Role.CITIZEN


class IsWorker(_RolePermission):
    required_role = User.Role.WORKER


class IsAuthority(_RolePermission):
    required_role = User.Role.AUTHORITY
