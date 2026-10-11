from django.test import TestCase
from django.db.models import ProtectedError
from django.db import IntegrityError
from ..models import Reporter, Issue, CriticalIssue, LowPriorityIssue, Label, Comment, StatusHistory
from .helpers import make_reporter, make_issue, make_user

class ModelTests(TestCase):
    def test_reporter_validation(self):
        r = Reporter(name="", email="test@x.com", team="backend")
        with self.assertRaisesMessage(ValueError, "Name cannot be empty"):
            r.validate()
            
        r.name = "Asha"
        r.email = "bad"
        with self.assertRaisesMessage(ValueError, "Invalid email"):
            r.validate()

        r.email = "asha@x.com"
        r.team = ""
        with self.assertRaisesMessage(ValueError, "Team cannot be empty"):
            r.validate()

        r.team = "backend"
        r.validate()  # Passes

    def test_reporter_to_dict(self):
        r = make_reporter(name="Asha", email="asha@x.com", team="backend")
        d = r.to_dict()
        self.assertEqual(list(d.keys()), ['id', 'name', 'email', 'team'])
        self.assertEqual(d['name'], "Asha")

    def test_issue_validation(self):
        r = make_reporter()
        i = Issue(title="", status="open", priority="medium", reporter=r)
        with self.assertRaisesMessage(ValueError, "Title cannot be empty"):
            i.validate()

        i.title = "Valid title"
        i.status = "banana"
        with self.assertRaisesMessage(ValueError, "Invalid status. Must be one of: open, in_progress, resolved, closed"):
            i.validate()

        i.status = "open"
        i.priority = "urgent"
        with self.assertRaisesMessage(ValueError, "Invalid priority. Must be one of: low, medium, high, critical"):
            i.validate()

        i.priority = "high"
        i.validate()  # Passes

    def test_issue_describe(self):
        i = Issue(title="Normal", priority="medium")
        self.assertEqual(i.describe(), "Normal [medium]")

        c = CriticalIssue(title="Bug", priority="critical")
        self.assertEqual(c.describe(), "[URGENT] Bug — needs immediate attention")
        
        l = LowPriorityIssue(title="Typo", priority="low")
        self.assertEqual(l.describe(), "Typo — low priority, handle when free")

    def test_issue_transitions(self):
        i = Issue(status='open')
        self.assertTrue(i.can_transition_to('in_progress'))
        self.assertTrue(i.can_transition_to('closed'))
        self.assertFalse(i.can_transition_to('resolved'))

        i.status = 'in_progress'
        self.assertTrue(i.can_transition_to('open'))
        self.assertTrue(i.can_transition_to('resolved'))
        self.assertFalse(i.can_transition_to('closed'))

        i.status = 'resolved'
        self.assertTrue(i.can_transition_to('closed'))
        self.assertTrue(i.can_transition_to('open'))
        self.assertFalse(i.can_transition_to('in_progress'))

        i.status = 'closed'
        self.assertFalse(i.can_transition_to('open'))
        self.assertFalse(i.can_transition_to('in_progress'))
        self.assertFalse(i.can_transition_to('resolved'))

    def test_issue_to_dict(self):
        r = make_reporter()
        i = make_issue(reporter=r, title="My Issue")
        d = i.to_dict()
        expected_keys = ['id', 'title', 'description', 'status', 'priority', 'reporter_id', 'created_at']
        self.assertEqual(list(d.keys()), expected_keys)
        self.assertNotIn('reporter', d)

    def test_label_validation_and_uniqueness(self):
        l = Label(name="", color="#123456")
        with self.assertRaisesMessage(ValueError, "Label name cannot be empty"):
            l.validate()

        l.name = "Bug"
        l.color = "blue"
        with self.assertRaisesMessage(ValueError, "Label color must be a hex value like #RRGGBB"):
            l.validate()

        l.color = "#123456"
        l.validate()
        l.save()

        # Case-insensitive uniqueness
        l2 = Label(name="bug", color="#654321")
        with self.assertRaises(IntegrityError):
            l2.save()

    def test_comment_validation(self):
        r = make_reporter()
        i = make_issue(reporter=r)
        c = Comment(issue=i, body="")
        with self.assertRaisesMessage(ValueError, "Comment body cannot be empty"):
            c.validate()

    def test_issue_queryset_methods(self):
        r = make_reporter()
        u = make_user()
        i1 = make_issue(reporter=r, title="Searchable Title", status="open", priority="low", assignee=u)
        i2 = make_issue(reporter=r, title="Other", status="closed", priority="critical")
        Comment.objects.create(issue=i1, author=u, body="test comment")

        qs = Issue.objects.with_related().with_counts().with_priority_rank()
        first = qs.get(pk=i1.pk)
        self.assertEqual(first.comment_count, 1)
        self.assertEqual(first.priority_rank, 0)

        second = qs.get(pk=i2.pk)
        self.assertEqual(second.priority_rank, 3)

        # active()
        active_ids = list(Issue.objects.active().values_list('id', flat=True))
        self.assertIn(i1.id, active_ids)
        self.assertNotIn(i2.id, active_ids)

        # search()
        search_results = Issue.objects.search("Searchable")
        self.assertEqual(search_results.count(), 1)
        self.assertEqual(search_results.first().id, i1.id)

    def test_reporter_protect_on_delete(self):
        r = make_reporter()
        make_issue(reporter=r)
        with self.assertRaises(ProtectedError):
            r.delete()
