from django.test import TestCase
from rest_framework import status
from django.utils import timezone
from datetime import timedelta
from .helpers import make_user, auth_client, make_reporter, make_issue
from ..models import Label, StatusHistory

class DashboardAPITests(TestCase):
    def setUp(self):
        self.admin = make_user(role='admin')
        self.dev = make_user(role='developer')
        self.dev_client = auth_client(self.dev)
        self.reporter = make_reporter(team="backend")

    def test_dashboard_endpoint(self):
        # 1 issue assigned to dev
        make_issue(reporter=self.reporter, assignee=self.dev, status='open')
        # 1 issue created by dev
        make_issue(reporter=self.reporter, created_by=self.dev, status='in_progress')
        # 1 unassigned active issue
        make_issue(reporter=self.reporter, assignee=None, status='open')

        resp = self.dev_client.get('/api/v1/dashboard/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()

        self.assertIn('assigned_to_me', data)
        self.assertEqual(data['assigned_to_me']['open'], 1)
        self.assertEqual(data['assigned_to_me']['in_progress'], 0)
        self.assertIn('created_by_me', data)
        self.assertEqual(data['created_by_me'], 1)
        self.assertIn('unassigned_active', data)
        self.assertEqual(data['unassigned_active'], 2)  # open issue with assignee None + issue with created_by dev (if unassigned)
        self.assertIn('recent_activity', data)

    def test_statistics_endpoint(self):
        now = timezone.now()
        lbl = Label.objects.create(name="urgent", color="#123456")
        i = make_issue(reporter=self.reporter, status='resolved')
        i.labels.add(lbl)
        i.resolved_at = now
        i.created_at = now - timedelta(hours=4)
        i.save()

        resp = self.dev_client.get('/api/v1/statistics/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()

        self.assertIn('total', data)
        self.assertEqual(data['total'], 1)
        self.assertIn('by_status', data)
        self.assertEqual(data['by_status']['resolved'], 1)
        self.assertEqual(data['by_status']['open'], 0)
        self.assertIn('by_priority', data)
        self.assertEqual(data['by_priority']['critical'], 0)
        self.assertIn('by_team', data)
        self.assertEqual(data['by_team']['backend'], 1)
        self.assertIn('top_labels', data)
        self.assertIn('avg_resolution_hours', data)
        self.assertIn('created_last_30_days', data)
