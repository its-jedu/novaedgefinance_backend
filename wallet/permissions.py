from rest_framework.permissions import BasePermission
from rest_framework import permissions

class IsProfileCompleted(BasePermission):
    """
    Allow access only to users with completed profiles.
    Requires the authentication app's profile_completed field.
    """
    def has_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and 
            getattr(request.user, 'profile_completed', False)
        )

class CanMakeDeposits(BasePermission):
    """
    Allow access only to users who can make deposits.
    Requires: email verified + phone verified + profile completed.
    """
    def has_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and 
            getattr(request.user, 'email_verified', False) and
            getattr(request.user, 'is_verified', False) and  # Phone verified
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
        elif hasattr(obj, 'wallet'):
            return obj.wallet.user == request.user
        
        return False

class IsWalletOwnerOrAdmin(BasePermission):
    """
    Special permission for wallet-related objects.
    """
    def has_object_permission(self, request, view, obj):
        # Admin can access any object
        if request.user.role == 'ADMIN':
            return True
        
        # Check if object has wallet attribute
        if hasattr(obj, 'wallet'):
            return obj.wallet.user == request.user
        # Check if object is a wallet
        elif isinstance(obj, Wallet):
            return obj.user == request.user
        # Check if object has user attribute
        elif hasattr(obj, 'user'):
            return obj.user == request.user
        
        return False

class AdminOnly(BasePermission):
    """
    Allow access only to admin users.
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == 'ADMIN')

