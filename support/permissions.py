from rest_framework.permissions import BasePermission

class IsOwnerOrAdmin(BasePermission):
    """
    Allow access to ticket owner or admin.
    """
    def has_object_permission(self, request, view, obj):
        # Admin can access any ticket
        if request.user.role == 'ADMIN':
            return True
        
        # Users can only access their own tickets
        if hasattr(obj, 'user'):
            return obj.user == request.user
        elif hasattr(obj, 'ticket'):
            return obj.ticket.user == request.user
        
        return False

class IsTicketOwner(BasePermission):
    """
    Allow access only to ticket owner.
    """
    def has_object_permission(self, request, view, obj):
        return obj.user == request.user

class AdminOnly(BasePermission):
    """
    Allow access only to admin users.
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == 'ADMIN')

class CanRespondToTicket(BasePermission):
    """
    Allow access to respond to tickets (admin or ticket owner).
    """
    def has_object_permission(self, request, view, obj):
        # Admin can respond to any ticket
        if request.user.role == 'ADMIN':
            return True
        
        # Ticket owner can respond to their own tickets
        return obj.user == request.user

