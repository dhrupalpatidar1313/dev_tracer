from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.utils import timezone
from datetime import timedelta
import random

from issues.models import Reporter, Label, Issue, Comment, StatusHistory
from issues import services

User = get_user_model()

class Command(BaseCommand):
    help = "Seed demo data for DevTrack"

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Delete existing data before seeding',
        )

    def handle(self, *args, **options):
        if Issue.objects.exists() and not options['force']:
            self.stdout.write(self.style.WARNING(
                "Issues already exist in database. Use --force to clear and re-seed."
            ))
            return

        if options['force']:
            self.stdout.write("Clearing existing data...")
            Comment.objects.all().delete()
            StatusHistory.objects.all().delete()
            Issue.objects.all().delete()
            Label.objects.all().delete()
            Reporter.objects.all().delete()

        # 1. Ensure Groups
        admin_group, _ = Group.objects.get_or_create(name='admin')
        dev_group, _ = Group.objects.get_or_create(name='developer')
        viewer_group, _ = Group.objects.get_or_create(name='viewer')

        # 2. Demo Users
        def create_or_update_user(username, password, group, is_superuser=False):
            user, created = User.objects.get_or_create(username=username)
            user.set_password(password)
            user.is_superuser = is_superuser
            user.is_staff = is_superuser
            user.save()
            user.groups.clear()
            user.groups.add(group)
            return user

        admin_user = create_or_update_user('admin_demo', 'AdminPass123!', admin_group, is_superuser=True)
        dev_user = create_or_update_user('dev_demo', 'DevPass123!', dev_group)
        viewer_user = create_or_update_user('viewer_demo', 'ViewerPass123!', viewer_group)

        self.stdout.write(self.style.SUCCESS("Demo users ensured (admin_demo, dev_demo, viewer_demo)"))

        # 3. Reporters
        reporters_data = [
            {"name": "Asha Rao", "email": "asha.rao@example.com", "team": "backend", "user": dev_user},
            {"name": "Liam Chen", "email": "liam.chen@example.com", "team": "frontend", "user": None},
            {"name": "Maya Patel", "email": "maya.patel@example.com", "team": "mobile", "user": None},
            {"name": "Carlos Gomez", "email": "carlos.gomez@example.com", "team": "devops", "user": admin_user},
            {"name": "Sarah Connor", "email": "sarah.connor@example.com", "team": "qa", "user": viewer_user},
        ]
        reporters = []
        for r_data in reporters_data:
            rep = Reporter(name=r_data["name"], email=r_data["email"], team=r_data["team"], user=r_data["user"])
            rep.validate()
            rep.save()
            reporters.append(rep)

        self.stdout.write(self.style.SUCCESS(f"Created {len(reporters)} reporters"))

        # 4. Labels
        labels_data = [
            {"name": "bug", "color": "#e11d48"},
            {"name": "feature", "color": "#2563eb"},
            {"name": "security", "color": "#dc2626"},
            {"name": "performance", "color": "#d97706"},
            {"name": "ui/ux", "color": "#9333ea"},
            {"name": "documentation", "color": "#16a34a"},
        ]
        labels = []
        for l_data in labels_data:
            lbl, _ = Label.objects.get_or_create(name=l_data["name"], defaults={"color": l_data["color"]})
            labels.append(lbl)

        self.stdout.write(self.style.SUCCESS(f"Created {len(labels)} labels"))

        # 5. Issues (~25 issues)
        issue_templates = [
            ("Login button not clickable on iOS devices", "Button unresponsive under 375px width", "open", "critical"),
            ("Database connection pool exhaust under load", "High connection latency seen on /api/v1/issues/", "in_progress", "critical"),
            ("Add export to CSV for reporter issues list", "Requested by management for weekly reporting", "resolved", "high"),
            ("Typo in footer copyright year", "Displays 2023 instead of current year", "closed", "low"),
            ("Session timeout too aggressive on web client", "Users logged out after only 5 minutes of inactivity", "open", "medium"),
            ("API documentation missing error response schema", "Swagger schema has missing responses on set-role", "resolved", "medium"),
            ("Memory leak in background status aggregator", "Workers consume 2GB RSS over 24 hours", "in_progress", "high"),
            ("Add dark mode toggle to settings page", "Support system preference theme", "open", "low"),
            ("Password reset email links expire too quickly", "Token expires in 10 minutes instead of 24 hours", "resolved", "high"),
            ("Refactor permission classes for issue editing", "Ensure creator and assignee can edit their issues", "closed", "medium"),
            ("Search endpoint slow when querying full text", "Indexes missing on description field", "in_progress", "medium"),
            ("Fix duplicate key error when attaching labels", "Make attaching label idempotent", "closed", "low"),
            ("Null pointer when unassigning issue from UI", "Unassign payload sends null instead of omitting key", "resolved", "high"),
            ("Webhook failure retry backoff strategy", "Implement exponential backoff for failed deliveries", "open", "high"),
            ("Upgrade PostgreSQL driver to psycopg 3", "Test connection pooling compatibility", "open", "low"),
            ("Add rate limiting to authentication endpoints", "Prevent brute force attacks on /login/", "closed", "critical"),
            ("User avatar upload fails for PNG images", "Image processing service throws decompression error", "in_progress", "medium"),
            ("Broken link in onboarding welcome email", "Directs users to staging environment URL", "closed", "low"),
            ("Add filtering by active status in issues API", "Helper filter to return open and in_progress tickets", "resolved", "medium"),
            ("Improve test coverage across issues app", "Target > 85% test coverage", "in_progress", "high"),
            ("Sanitize user input in comment markdown parser", "Prevent potential XSS script injection", "open", "critical"),
            ("Optimize dashboard aggregate query counts", "Use single annotated query instead of N queries", "resolved", "medium"),
            ("Support bulk issue status transitions", "Admins should be able to close multiple stale tickets", "open", "low"),
            ("Add audit trail for label color modifications", "Log label changes to audit history table", "open", "low"),
            ("Validate hex colors on label creation", "Enforce #RRGGBB format", "closed", "medium"),
        ]

        now = timezone.now()
        assignees = [dev_user, admin_user, None]

        for idx, (title, desc, status, priority) in enumerate(issue_templates, start=1):
            created_days_ago = (25 - idx)
            created_dt = now - timedelta(days=created_days_ago, hours=random.randint(1, 12))
            
            reporter = random.choice(reporters)
            assignee = random.choice(assignees)
            created_by = admin_user if idx % 2 == 0 else dev_user

            issue = Issue(
                title=title,
                description=desc,
                status=status,
                priority=priority,
                reporter=reporter,
                assignee=assignee,
                created_by=created_by,
                created_at=created_dt,
            )
            if status in ['resolved', 'closed']:
                issue.resolved_at = created_dt + timedelta(hours=random.randint(4, 48))
            issue.validate()
            issue.save()

            # Assign random labels
            issue_labels = random.sample(labels, k=random.randint(1, 3))
            issue.labels.set(issue_labels)

            # Create initial status history
            StatusHistory.objects.create(
                issue=issue,
                from_status=None,
                to_status='open',
                changed_by=created_by,
                note="Issue created",
                changed_at=created_dt,
            )

            if status != 'open':
                StatusHistory.objects.create(
                    issue=issue,
                    from_status='open',
                    to_status=status,
                    changed_by=assignee or admin_user,
                    note=f"Moved to {status}",
                    changed_at=issue.resolved_at or (created_dt + timedelta(hours=6)),
                )

            # Add comments to some issues
            if idx % 2 == 0:
                Comment.objects.create(
                    issue=issue,
                    author=dev_user,
                    body=f"Investigating this issue. Able to reproduce on staging.",
                    created_at=created_dt + timedelta(hours=1),
                )
            if idx % 3 == 0:
                Comment.objects.create(
                    issue=issue,
                    author=admin_user,
                    body=f"Priority confirmed. Let's aim to have this resolved soon.",
                    created_at=created_dt + timedelta(hours=2),
                )

        self.stdout.write(self.style.SUCCESS(f"Successfully seeded {len(issue_templates)} issues with history and comments!"))
