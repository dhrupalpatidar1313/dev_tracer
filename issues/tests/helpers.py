from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.test import APIClient
from rest_framework.authtoken.models import Token
from ..models import Reporter, Issue, Label

User = get_user_model()

def make_user(role='developer', username=None):
    if not username:
        import uuid
        username = f"{role}_{uuid.uuid4().hex[:6]}"
    user = User.objects.create_user(username=username, password='Password123!')
    user.groups.clear()
    group, _ = Group.objects.get_or_create(name=role)
    user.groups.add(group)
    if role == 'admin':
        user.is_superuser = True
        user.is_staff = True
        user.save()
    return user

def auth_client(user):
    client = APIClient()
    token, _ = Token.objects.get_or_create(user=user)
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    return client

def make_reporter(name="Test Reporter", email="test@reporter.com", team="backend", user=None):
    rep = Reporter.objects.create(name=name, email=email, team=team, user=user)
    return rep

def make_issue(reporter=None, title="Test Issue", status="open", priority="medium", created_by=None, assignee=None):
    if not reporter:
        reporter = make_reporter()
    issue = Issue.objects.create(
        title=title,
        status=status,
        priority=priority,
        reporter=reporter,
        created_by=created_by,
        assignee=assignee
    )
    return issue
