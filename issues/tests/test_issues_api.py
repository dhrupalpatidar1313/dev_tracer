from django.test import TestCase
from rest_framework import status
from .helpers import make_user, auth_client, make_reporter, make_issue
from ..models import Label, Issue

class IssuesAPITests(TestCase):
    def setUp(self):
        self.admin = make_user(role='admin', username='admin_u')
        self.dev = make_user(role='developer', username='dev_u')
        self.dev2 = make_user(role='developer', username='dev2_u')
        self.viewer = make_user(role='viewer', username='viewer_u')

        self.admin_client = auth_client(self.admin)
        self.dev_client = auth_client(self.dev)
        self.dev2_client = auth_client(self.dev2)
        self.viewer_client = auth_client(self.viewer)
        self.reporter = make_reporter()

    def test_create_issue_permissions(self):
        payload = {
            "title": "New Bug",
            "description": "Bug detail",
            "status": "open",
            "priority": "high",
            "reporter": self.reporter.id
        }

        # Viewer cannot create issue
        r_view = self.viewer_client.post('/api/v1/issues/', payload, format='json')
        self.assertEqual(r_view.status_code, status.HTTP_403_FORBIDDEN)

        # Dev can create
        r_dev = self.dev_client.post('/api/v1/issues/', payload, format='json')
        self.assertEqual(r_dev.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r_dev.json()['title'], "New Bug")
        self.assertEqual(r_dev.json()['created_by']['username'], self.dev.username)

    def test_update_issue_editor_permission(self):
        # Issue created by dev
        issue = make_issue(reporter=self.reporter, created_by=self.dev, title="Dev Issue")

        # dev2 (not creator or assignee) cannot edit -> 403
        r_dev2 = self.dev2_client.patch(f'/api/v1/issues/{issue.id}/', {"title": "Hacked"}, format='json')
        self.assertEqual(r_dev2.status_code, status.HTTP_403_FORBIDDEN)

        # dev (creator) can edit -> 200
        r_dev = self.dev_client.patch(f'/api/v1/issues/{issue.id}/', {"title": "Updated Title"}, format='json')
        self.assertEqual(r_dev.status_code, status.HTTP_200_OK)
        self.assertEqual(r_dev.json()['title'], "Updated Title")

        # admin can edit -> 200
        r_admin = self.admin_client.patch(f'/api/v1/issues/{issue.id}/', {"title": "Admin Override"}, format='json')
        self.assertEqual(r_admin.status_code, status.HTTP_200_OK)

    def test_transition_endpoint(self):
        issue = make_issue(reporter=self.reporter, created_by=self.dev, status='open')

        # Invalid transition (open -> resolved)
        r_bad = self.dev_client.post(f'/api/v1/issues/{issue.id}/transition/', {"status": "resolved"}, format='json')
        self.assertEqual(r_bad.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Invalid status transition", r_bad.json()['error'])

        # Valid transition (open -> in_progress)
        r_good = self.dev_client.post(f'/api/v1/issues/{issue.id}/transition/', {"status": "in_progress", "note": "working on it"}, format='json')
        self.assertEqual(r_good.status_code, status.HTTP_200_OK)
        self.assertEqual(r_good.json()['status'], 'in_progress')

    def test_assign_endpoint(self):
        issue = make_issue(reporter=self.reporter, created_by=self.dev)

        # Assign to viewer -> 400
        r_view = self.dev_client.post(f'/api/v1/issues/{issue.id}/assign/', {"assignee": self.viewer.id}, format='json')
        self.assertEqual(r_view.status_code, status.HTTP_400_BAD_REQUEST)

        # Assign to dev2 -> 200
        r_dev = self.dev_client.post(f'/api/v1/issues/{issue.id}/assign/', {"assignee": self.dev2.id}, format='json')
        self.assertEqual(r_dev.status_code, status.HTTP_200_OK)
        self.assertEqual(r_dev.json()['assignee']['id'], self.dev2.id)

        # Now dev2 is assignee, so dev2 CAN edit the issue
        r_dev2_edit = self.dev2_client.patch(f'/api/v1/issues/{issue.id}/', {"description": "dev2 edit"}, format='json')
        self.assertEqual(r_dev2_edit.status_code, status.HTTP_200_OK)

    def test_filters_and_ordering(self):
        lbl = Label.objects.create(name="frontend", color="#123456")
        i1 = make_issue(reporter=self.reporter, title="I1", status="open", priority="low", assignee=self.dev)
        i1.labels.add(lbl)
        i2 = make_issue(reporter=self.reporter, title="I2", status="in_progress", priority="critical", assignee=None)
        i3 = make_issue(reporter=self.reporter, title="I3", status="closed", priority="medium", assignee=self.dev2)

        # filter assignee=me
        r_me = self.dev_client.get('/api/v1/issues/?assignee=me')
        self.assertEqual(r_me.json()['count'], 1)
        self.assertEqual(r_me.json()['results'][0]['id'], i1.id)

        # filter unassigned=true
        r_unassigned = self.dev_client.get('/api/v1/issues/?unassigned=true')
        self.assertEqual(r_unassigned.json()['count'], 1)
        self.assertEqual(r_unassigned.json()['results'][0]['id'], i2.id)

        # filter active=true
        r_active = self.dev_client.get('/api/v1/issues/?active=true')
        self.assertEqual(r_active.json()['count'], 2)

        # filter label
        r_label = self.dev_client.get('/api/v1/issues/?label=frontend')
        self.assertEqual(r_label.json()['count'], 1)

        # ordering by priority (rank-based) ascending
        r_ord = self.dev_client.get('/api/v1/issues/?ordering=priority')
        self.assertEqual(r_ord.status_code, status.HTTP_200_OK)
        results = r_ord.json()['results']
        priorities = [x['priority'] for x in results]
        # low < medium < critical
        self.assertEqual(priorities, ['low', 'medium', 'critical'])

        # invalid ordering -> 400
        r_bad_ord = self.dev_client.get('/api/v1/issues/?ordering=unknown_field')
        self.assertEqual(r_bad_ord.status_code, status.HTTP_400_BAD_REQUEST)

    def test_query_count_constant(self):
        # Create 10 issues
        for idx in range(10):
            make_issue(reporter=self.reporter, title=f"Issue {idx}")

        # The issue list must execute <= 5 queries
        with self.assertNumQueries(4):
            resp = self.dev_client.get('/api/v1/issues/')
            self.assertEqual(resp.status_code, status.HTTP_200_OK)
            self.assertEqual(resp.json()['count'], 10)
