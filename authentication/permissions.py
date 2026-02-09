from rest_framework import permissions
from rest_framework.permissions import BasePermission

class IsAdminUser(BasePermission):
    """
    Allows access only to admin users.
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == 'ADMIN')

class IsOwnerOrAdmin(BasePermission):
    """
    Allows access to object owner or admin.
    """
    def has_object_permission(self, request, view, obj):
        # Admin can access any object
        if request.user.role == 'ADMIN':
            return True
        
        # Users can only access their own objects
        return obj == request.user

class IsVerified(permissions.BasePermission):
    """
    Allows access only to verified users.
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_verified)

class IsActive(permissions.BasePermission):
    """
    Allows access only to active users.
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_active)