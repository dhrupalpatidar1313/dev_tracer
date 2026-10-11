from django.db import models
from django.conf import settings
from django.db.models import Count, Case, When, Value, IntegerField, Q
from django.db.models.functions import Lower

class BaseEntity(models.Model):
    class Meta:
        abstract = True

    def validate(self):
        raise NotImplementedError()

    def to_dict(self):
        result = {}
        fields = getattr(self, 'DICT_FIELDS', [f.attname for f in self._meta.concrete_fields])
        for field in fields:
            val = getattr(self, field)
            if hasattr(val, 'isoformat'):
                result[field] = str(val)
            else:
                result[field] = val
        return result


class Reporter(BaseEntity):
    name = models.CharField(max_length=100)
    email = models.CharField(max_length=254)
    team = models.CharField(max_length=50)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reporter_profile"
    )

    DICT_FIELDS = ('id', 'name', 'email', 'team')

    class Meta:
        ordering = ['id']

    def validate(self):
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("Name cannot be empty")
        if not isinstance(self.email, str) or "@" not in self.email:
            raise ValueError("Invalid email")
        if not isinstance(self.team, str) or not self.team.strip():
            raise ValueError("Team cannot be empty")

    def __str__(self):
        return self.name


class Label(models.Model):
    name = models.CharField(max_length=50)
    color = models.CharField(max_length=7, default="#888888")

    class Meta:
        constraints = [
            models.UniqueConstraint(Lower('name'), name='unique_lower_name_label')
        ]
        ordering = ['name']

    def validate(self):
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("Label name cannot be empty")
        if not isinstance(self.color, str) or not self.color.startswith('#') or len(self.color) != 7:
            # Note: A real regex could be used, but matching brief requirements here.
            raise ValueError("Label color must be a hex value like #RRGGBB")

    def __str__(self):
        return self.name


class IssueQuerySet(models.QuerySet):
    def with_related(self):
        return self.select_related('reporter', 'assignee', 'created_by').prefetch_related('labels')

    def with_counts(self):
        return self.annotate(comment_count=Count('comments', distinct=True))

    def with_priority_rank(self):
        return self.annotate(
            priority_rank=Case(
                When(priority='low', then=Value(0)),
                When(priority='medium', then=Value(1)),
                When(priority='high', then=Value(2)),
                When(priority='critical', then=Value(3)),
                output_field=IntegerField(),
            )
        )

    def active(self):
        return self.filter(status__in=['open', 'in_progress'])

    def search(self, term):
        if not term:
            return self
        return self.filter(Q(title__icontains=term) | Q(description__icontains=term))


class Issue(BaseEntity):
    VALID_STATUSES = ('open', 'in_progress', 'resolved', 'closed')
    VALID_PRIORITIES = ('low', 'medium', 'high', 'critical')
    PRIORITY_RANK = {'low': 0, 'medium': 1, 'high': 2, 'critical': 3}
    
    ALLOWED_TRANSITIONS = {
        'open': ['open', 'in_progress', 'closed'],
        'in_progress': ['in_progress', 'open', 'resolved'],
        'resolved': ['resolved', 'closed', 'open'],
        'closed': ['closed']
    }

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=[(s, s) for s in VALID_STATUSES], default='open')
    priority = models.CharField(max_length=20, choices=[(p, p) for p in VALID_PRIORITIES], default='medium')
    reporter = models.ForeignKey(Reporter, on_delete=models.PROTECT, related_name="issues")
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_issues"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_issues"
    )
    labels = models.ManyToManyField(Label, blank=True, related_name="issues")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    DICT_FIELDS = ('id', 'title', 'description', 'status', 'priority', 'reporter_id', 'created_at')
    
    objects = IssueQuerySet.as_manager()

    class Meta:
        ordering = ['id']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['priority']),
            models.Index(fields=['reporter', 'status']),
            models.Index(fields=['created_at']),
        ]

    def validate(self):
        if not isinstance(self.title, str) or not self.title.strip():
            raise ValueError("Title cannot be empty")
        if self.status not in self.VALID_STATUSES:
            raise ValueError("Invalid status. Must be one of: open, in_progress, resolved, closed")
        if self.priority not in self.VALID_PRIORITIES:
            raise ValueError("Invalid priority. Must be one of: low, medium, high, critical")

    def describe(self):
        return f"{self.title} [{self.priority}]"
        
    def can_transition_to(self, new_status):
        return new_status in self.ALLOWED_TRANSITIONS.get(self.status, [])

    def __str__(self):
        return self.title


class CriticalIssue(Issue):
    class Meta:
        proxy = True

    def describe(self):
        return f"[URGENT] {self.title} — needs immediate attention"


class LowPriorityIssue(Issue):
    class Meta:
        proxy = True

    def describe(self):
        return f"{self.title} — low priority, handle when free"


class Comment(models.Model):
    issue = models.ForeignKey(Issue, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL
    )
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']

    def validate(self):
        if not isinstance(self.body, str) or not self.body.strip():
            raise ValueError("Comment body cannot be empty")


class StatusHistory(models.Model):
    issue = models.ForeignKey(Issue, on_delete=models.CASCADE, related_name="status_history")
    from_status = models.CharField(max_length=20, null=True, blank=True)
    to_status = models.CharField(max_length=20)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL
    )
    note = models.CharField(max_length=255, blank=True)
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['changed_at', 'id']
