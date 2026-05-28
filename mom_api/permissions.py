from rest_framework import permissions

class IsAdminUserRole(permissions.BasePermission):
    """
    Allows access only to users who have the 'Admin' role in their UserProfile
    or are Django superusers.
    """
    def has_permission(self, request, view):
        # Must be authenticated
        if not (request.user and request.user.is_authenticated):
            return False
            
        # Superusers are automatically admins
        if request.user.is_superuser:
            return True
            
        # Otherwise, check their profile role
        return hasattr(request.user, 'profile') and request.user.profile.role == 'Admin'
