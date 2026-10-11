from rest_framework import permissions

def get_role(user):
    if not user or not user.is_authenticated:
        return None
    if user.is_superuser:
        return 'admin'
    
    group_names = set(user.groups.values_list('name', flat=True))
    if 'admin' in group_names:
        return 'admin'
    elif 'developer' in group_names:
        return 'developer'
    elif 'viewer' in group_names:
        return 'viewer'
    return 'viewer'

class IsAdminRole(permissions.BasePermission):
    def has_permission(self, request, view):
        return get_role(request.user) == 'admin'

class IsDeveloperOrAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        role = get_role(request.user)
        return role in ['admin', 'developer']

class IsAuthenticatedReadOnlyOrDeveloper(permissions.BasePermission):
    def has_permission(self, request, view):
        role = get_role(request.user)
        if not role:
            return False
        if request.method in permissions.SAFE_METHODS:
            return True
        return role in ['admin', 'developer']

class IsIssueEditor(permissions.BasePermission):
    def has_permission(self, request, view):
        # We handle this per-object, but need to pass the base check too.
        # Developer or Admin can be editors, viewers can't write.
        if request.method in permissions.SAFE_METHODS:
            return bool(get_role(request.user))
        return get_role(request.user) in ['admin', 'developer']
        
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        role = get_role(request.user)
        if role == 'admin':
            return True
        if role == 'developer':
            return obj.created_by == request.user or obj.assignee == request.user
        return False

class IsAuthorOrAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return bool(get_role(request.user))
        return get_role(request.user) in ['admin', 'developer']

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        role = get_role(request.user)
        if role == 'admin':
            return True
        if hasattr(obj, 'author'):
            return obj.author == request.user
        if hasattr(obj, 'created_by'):
            return obj.created_by == request.user
        return False

