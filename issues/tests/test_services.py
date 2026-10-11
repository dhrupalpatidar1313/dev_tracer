from django.test import TestCase
from unittest.mock import patch
from rest_framework.exceptions import ValidationError
from django.utils import timezone
from ..models import Reporter, Issue, StatusHistory
from ..services import (
    create_reporter, update_reporter, delete_reporter,
    create_issue, update_issue, change_status, assign_issue,
    add_label, remove_label, add_comment, update_comment, delete_comment
)
from .helpers import make_reporter, make_issue, make_user
from ..exceptions import Conflict

class ServiceTests(TestCase):
    def test_create_and_update_reporter(self):
        r = Reporter(name="Test", email="test@x.com", team="test")
        create_reporter(r)
        self.assertIsNotNone(r.id)

        update_reporter(r, {"name": "Updated Name"})
        r.refresh_from_db()
        self.assertEqual(r.name, "Updated Name")

    def test_delete_reporter_with_issues_raises_conflict(self):
        r = make_reporter()
        make_issue(reporter=r)
        with self.assertRaises(Conflict):
            delete_reporter(r)

    def test_create_issue_writes_history(self):
        r = make_reporter()
        user = make_user()
        i = Issue(title="Bug", status="open", priority="medium", reporter=r)
        create_issue(i, actor=user)
        
        self.assertIsNotNone(i.id)
        history = StatusHistory.objects.filter(issue=i)
        self.assertEqual(history.count(), 1)
        self.assertIsNone(history.first().from_status)
        self.assertEqual(history.first().to_status, "open")
        self.assertEqual(history.first().changed_by, user)

    def test_change_status_sets_and_clears_resolved_at(self):
        r = make_reporter()
        user = make_user()
        issue = make_issue(reporter=r, status='open')

        # open -> in_progress
        change_status(issue, 'in_progress', actor=user)
        issue.refresh_from_db()
        self.assertEqual(issue.status, 'in_progress')
        self.assertIsNone(issue.resolved_at)

        # in_progress -> resolved (sets resolved_at)
        change_status(issue, 'resolved', actor=user)
        issue.refresh_from_db()
        self.assertEqual(issue.status, 'resolved')
        self.assertIsNotNone(issue.resolved_at)

        # resolved -> open (clears resolved_at)
        change_status(issue, 'open', actor=user)
        issue.refresh_from_db()
        self.assertEqual(issue.status, 'open')
        self.assertIsNone(issue.resolved_at)

    def test_change_status_invalid_transition(self):
        r = make_reporter()
        issue = make_issue(reporter=r, status='open')
        with self.assertRaises(ValidationError):
            change_status(issue, 'resolved')  # open -> resolved is invalid

    def test_assign_issue_role_check(self):
        r = make_reporter()
        issue = make_issue(reporter=r)
        dev = make_user(role='developer')
        viewer = make_user(role='viewer')

        # dev allowed
        assign_issue(issue, dev)
        issue.refresh_from_db()
        self.assertEqual(issue.assignee, dev)

        # viewer rejected
        with self.assertRaises(ValidationError):
            assign_issue(issue, viewer)

        # null allowed
        assign_issue(issue, None)
        issue.refresh_from_db()
        self.assertIsNone(issue.assignee)

    @patch('issues.models.StatusHistory.objects.create')
    def test_transactional_rollback(self, mock_create):
        mock_create.side_effect = Exception("DB Error")
        r = make_reporter()
        i = Issue(title="Rollback Bug", status="open", priority="medium", reporter=r)
        
        with self.assertRaisesMessage(Exception, "DB Error"):
            create_issue(i)
            
        self.assertFalse(Issue.objects.filter(title="Rollback Bug").exists())
