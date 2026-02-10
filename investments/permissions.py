from rest_framework.permissions import BasePermission

class IsProfileCompleted(BasePermission):
    """
    Allow access only to users with completed profiles.
    """
    def has_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and 
            getattr(request.user, 'profile_completed', False)
        )

class CanInvest(BasePermission):
    """
    Allow access only to users who can make investments.
    Requires: email verified + phone verified + profile completed.
    """
    def has_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and 
            getattr(request.user, 'email_verified', False) and
            getattr(request.user, 'is_verified', False) and
            getattr(request.user, 'profile_completed', False)
        )

class IsOwnerOrAdmin(BasePermission):
    """
    Allow access to object owner or admin.
    """
    def has_object_permission(self, request, view, obj):
        # Admin can access any object
        if request.user.role == 'ADMIN':
            return True
        
        # Users can only access their own objects
        if hasattr(obj, 'user'):
            return obj.user == request.user
        
        return False

class AdminOnly(BasePermission):
    """
    Allow access only to admin users.
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == 'ADMIN')

class CanManagePlans(BasePermission):
    """
    Allow access to manage investment plans (admin only).
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Admin can manage plans
        if request.user.role == 'ADMIN':
            return True
        
        # Check for specific permissions if using Django's permission system
        return request.user.has_perm('investments.manage_investment_plan')