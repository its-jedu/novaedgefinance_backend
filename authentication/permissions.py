from rest_framework import permissions
from rest_framework.permissions import BasePermission

class IsAdminUser(BasePermission):
    """
    Allows access only to admin users.
    """
    def has_permission(self, request, view):
        return bool(request.user and 
                   request.user.is_authenticated and 
                   request.user.role == 'ADMIN')

class IsOwnerOrAdmin(BasePermission):
    """
    Allows access to object owner or admin.
    """
    def has_object_permission(self, request, view, obj):
        # Admin can access any object
        if request.user.role == 'ADMIN':
            return True
        
        # Users can only access their own objects
        # Check if obj has user attribute (like InvestmentProfile)
        if hasattr(obj, 'user'):
            return obj.user == request.user
        # Or if obj is the user itself
        return obj == request.user

class IsActive(BasePermission):
    """
    Allows access only to active users.
    """
    def has_permission(self, request, view):
        return bool(request.user and 
                   request.user.is_authenticated and 
                   request.user.is_active)

class IsEmailVerified(BasePermission):
    """
    Allows access only to email verified users.
    This is the main verification permission now.
    """
    def has_permission(self, request, view):
        return bool(request.user and 
                   request.user.is_authenticated and 
                   request.user.email_verified)

class CanMakeDeposits(BasePermission):
    """
    Allows access only to users who can make deposits.
    Now only requires: email verified and active account.
    """
    def has_permission(self, request, view):
        return bool(request.user and 
                   request.user.is_authenticated and 
                   request.user.email_verified and 
                   request.user.is_active)

class HasInvestmentProfile(BasePermission):
    """
    Allows access only to users who have an investment profile.
    Optional permission for profile-related operations.
    """
    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        
        try:
            return hasattr(request.user, 'investment_profile')
        except:
            return False

class IsProfileCompleted(BasePermission):
    """
    Allows access only to users with completed investment profiles.
    This is optional - can be used for features that require full profile.
    """
    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        
        try:
            return (request.user.investment_profile and 
                   request.user.investment_profile.is_completed)
        except:
            return False

