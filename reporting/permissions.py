from rest_framework.permissions import BasePermission

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

class CanViewReports(BasePermission):
    """
    Allow access to view reports (admin or user with permission).
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Admin can view all reports
        if request.user.role == 'ADMIN':
            return True
        
        # Check for specific report viewing permission
        return request.user.has_perm('reporting.view_financialreport')

