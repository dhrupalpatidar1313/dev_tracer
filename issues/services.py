from django.db import transaction
from django.db.models import ProtectedError
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from django.contrib.auth.models import Group

from .models import Reporter, Issue, Comment, Label, StatusHistory
from .permissions import get_role
from .exceptions import Conflict

def create_reporter(reporter):
    with transaction.atomic():
        reporter.validate()
        reporter.save()
    return reporter

def update_reporter(reporter, changes):
    with transaction.atomic():
        for field, value in changes.items():
            setattr(reporter, field, value)
        reporter.validate()
        reporter.save()
    return reporter

def delete_reporter(reporter):
    with transaction.atomic():
        try:
            reporter.delete()
        except ProtectedError:
            raise Conflict("Cannot delete reporter with existing issues")

def create_issue(issue, actor=None):
    with transaction.atomic():
        issue.validate()
        issue.save()
        StatusHistory.objects.create(
            issue=issue,
            from_status=None,
            to_status=issue.status,
            changed_by=actor,
            note=""
        )
    return issue

def change_status(issue, to_status, actor=None, note=""):
    with transaction.atomic():
        # Lock the row for update
        locked_issue = Issue.objects.select_for_update().get(pk=issue.pk)
        old_status = locked_issue.status
        
        if old_status != to_status:
            if not locked_issue.can_transition_to(to_status):
                raise ValidationError(f"Invalid status transition: {old_status} -> {to_status}")
            
            locked_issue.status = to_status
            
            # set/clear resolved_at: set on entering resolved or closed if empty; cleared on returning to open/in_progress
            if to_status in ['resolved', 'closed']:
                if not locked_issue.resolved_at:
                    locked_issue.resolved_at = timezone.now()
            elif to_status in ['open', 'in_progress']:
                locked_issue.resolved_at = None
                
            locked_issue.save()
            
            StatusHistory.objects.create(
                issue=locked_issue,
                from_status=old_status,
                to_status=to_status,
                changed_by=actor,
                note=note or ""
            )
            
            issue.status = locked_issue.status
            issue.resolved_at = locked_issue.resolved_at
            issue.updated_at = locked_issue.updated_at
            
    return issue

def update_issue(issue, changes, actor=None):
    with transaction.atomic():
        new_status = changes.pop('status', None)
        
        for field, value in changes.items():
            setattr(issue, field, value)
        issue.validate()
        issue.save()
        
        if new_status and new_status != issue.status:
            change_status(issue, new_status, actor=actor)
            
    return issue

def assign_issue(issue, assignee, actor=None):
    with transaction.atomic():
        if assignee is not None:
            role = get_role(assignee)
            if role not in ['developer', 'admin']:
                raise ValidationError("Assignee must be a developer or admin")
        issue.assignee = assignee
        issue.save(update_fields=['assignee', 'updated_at'])
    return issue

def add_label(issue, label):
    with transaction.atomic():
        issue.labels.add(label)
    return issue

def remove_label(issue, label):
    with transaction.atomic():
        issue.labels.remove(label)
    return issue

def add_comment(issue, author, body):
    with transaction.atomic():
        comment = Comment(issue=issue, author=author, body=body)
        comment.validate()
        comment.save()
    return comment

def update_comment(comment, body):
    with transaction.atomic():
        comment.body = body
        comment.validate()
        comment.save()
    return comment

def delete_comment(comment):
    with transaction.atomic():
        comment.delete()

def set_user_role(user, role):
    with transaction.atomic():
        if role not in ['admin', 'developer', 'viewer']:
            raise ValidationError("Invalid role")
        user.groups.clear()
        group, _ = Group.objects.get_or_create(name=role)
        user.groups.add(group)
    return user
