from django.test import TestCase
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from ..permissions import get_role, IsAdminRole, IsDeveloperOrAdmin, IsAuthenticatedReadOnlyOrDeveloper, IsIssueEditor, IsAuthorOrAdmin
from ..models import Reporter, Issue
from unittest.mock import Mock

User = get_user_model()

class MockRequest:
    def __init__(self, user, method='GET'):
        self.user = user
        self.method = method

class PermissionsTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username='admin', password='1')
        self.developer = User.objects.create_user(username='dev', password='1')
        self.viewer = User.objects.create_user(username='viewer', password='1')
        
        self.admin.groups.clear()
        self.admin.groups.add(Group.objects.get(name='admin'))
        
        self.developer.groups.clear()
        self.developer.groups.add(Group.objects.get(name='developer'))

    def test_get_role(self):
        self.assertEqual(get_role(self.admin), 'admin')
        self.assertEqual(get_role(self.developer), 'developer')
        self.assertEqual(get_role(self.viewer), 'viewer')
        
        superuser = User.objects.create_superuser(username='super', password='1')
        self.assertEqual(get_role(superuser), 'admin')

    def test_is_admin_role(self):
        perm = IsAdminRole()
        self.assertTrue(perm.has_permission(MockRequest(self.admin), None))
        self.assertFalse(perm.has_permission(MockRequest(self.developer), None))
        self.assertFalse(perm.has_permission(MockRequest(self.viewer), None))

    def test_is_developer_or_admin(self):
        perm = IsDeveloperOrAdmin()
        self.assertTrue(perm.has_permission(MockRequest(self.admin), None))
        self.assertTrue(perm.has_permission(MockRequest(self.developer), None))
        self.assertFalse(perm.has_permission(MockRequest(self.viewer), None))

    def test_is_auth_read_only_or_dev(self):
        perm = IsAuthenticatedReadOnlyOrDeveloper()
        
        # GET (SAFE)
        self.assertTrue(perm.has_permission(MockRequest(self.viewer, 'GET'), None))
        self.assertTrue(perm.has_permission(MockRequest(self.developer, 'GET'), None))
        
        # POST
        self.assertFalse(perm.has_permission(MockRequest(self.viewer, 'POST'), None))
        self.assertTrue(perm.has_permission(MockRequest(self.developer, 'POST'), None))
        self.assertTrue(perm.has_permission(MockRequest(self.admin, 'POST'), None))

    def test_is_issue_editor(self):
        perm = IsIssueEditor()
        r = Reporter.objects.create(name='r', team='t')
        issue = Issue(title='test', status='open', priority='low', reporter=r)
        
        # Admin is always true
        self.assertTrue(perm.has_object_permission(MockRequest(self.admin, 'PATCH'), None, issue))
        
        # Viewer is false for write
        self.assertFalse(perm.has_object_permission(MockRequest(self.viewer, 'PATCH'), None, issue))
        
        # Dev not author/assignee is false
        self.assertFalse(perm.has_object_permission(MockRequest(self.developer, 'PATCH'), None, issue))
        
        # Dev author is true
        issue.created_by = self.developer
        self.assertTrue(perm.has_object_permission(MockRequest(self.developer, 'PATCH'), None, issue))
        
        # Dev assignee is true
        issue.created_by = None
        issue.assignee = self.developer
        self.assertTrue(perm.has_object_permission(MockRequest(self.developer, 'PATCH'), None, issue))
