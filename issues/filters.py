import django_filters
from rest_framework import filters
from rest_framework.exceptions import ValidationError
from django.db.models import Q

from .models import Issue, Reporter

class IssueFilter(django_filters.FilterSet):
    status = django_filters.CharFilter(method='filter_status')
    priority = django_filters.CharFilter(method='filter_priority')
    reporter = django_filters.NumberFilter(field_name='reporter_id')
    assignee = django_filters.CharFilter(method='filter_assignee')
    unassigned = django_filters.BooleanFilter(method='filter_unassigned')
    label = django_filters.CharFilter(method='filter_label')
    created_after = django_filters.IsoDateTimeFilter(field_name='created_at', lookup_expr='gte')
    created_before = django_filters.IsoDateTimeFilter(field_name='created_at', lookup_expr='lte')
    active = django_filters.BooleanFilter(method='filter_active')

    class Meta:
        model = Issue
        fields = ['status', 'priority', 'reporter', 'assignee', 'unassigned', 'label', 'created_after', 'created_before', 'active']

    def filter_status(self, queryset, name, value):
        if value not in Issue.VALID_STATUSES:
            raise ValidationError("Invalid status. Must be one of: open, in_progress, resolved, closed")
        return queryset.filter(status=value)

    def filter_priority(self, queryset, name, value):
        if value not in Issue.VALID_PRIORITIES:
            raise ValidationError("Invalid priority. Must be one of: low, medium, high, critical")
        return queryset.filter(priority=value)

    def filter_assignee(self, queryset, name, value):
        if value == 'me':
            request = getattr(self, 'request', None)
            if request and request.user and request.user.is_authenticated:
                return queryset.filter(assignee=request.user)
            return queryset.none()
        try:
            user_id = int(value)
            return queryset.filter(assignee_id=user_id)
        except ValueError:
            raise ValidationError("assignee must be an integer or 'me'")

    def filter_unassigned(self, queryset, name, value):
        if value is True:
            return queryset.filter(assignee__isnull=True)
        return queryset

    def filter_label(self, queryset, name, value):
        request = getattr(self, 'request', None)
        values = request.GET.getlist('label') if request else [value]
        if not values:
            values = [value]
        q = Q()
        for v in values:
            if str(v).isdigit():
                q |= Q(labels__id=int(v)) | Q(labels__name__iexact=v)
            else:
                q |= Q(labels__name__iexact=v)
        return queryset.filter(q).distinct()

    def filter_active(self, queryset, name, value):
        if value is True:
            return queryset.active()
        return queryset

class ReporterFilter(django_filters.FilterSet):
    team = django_filters.CharFilter(field_name='team', lookup_expr='exact')

    class Meta:
        model = Reporter
        fields = ['team']

class PriorityAwareOrderingFilter(filters.OrderingFilter):
    allowed_fields = ['id', 'title', 'status', 'priority', 'created_at', 'updated_at']

    def filter_queryset(self, request, queryset, view):
        if queryset.model != Issue:
            return super().filter_queryset(request, queryset, view)

        ordering = self.get_ordering(request, queryset, view)
        if ordering:
            return queryset.order_by(*ordering)
        return queryset.order_by('-created_at')

    def get_ordering(self, request, queryset, view):
        if queryset.model != Issue:
            return super().get_ordering(request, queryset, view)

        params = request.query_params.get(self.ordering_param)
        if not params:
            return ['-created_at']

        fields = [param.strip() for param in params.split(',')]
        ordering = []
        for field in fields:
            clean_field = field.lstrip('-')
            if clean_field not in self.allowed_fields:
                raise ValidationError(f"Invalid ordering. Allowed: {', '.join(self.allowed_fields)}")

            descending = field.startswith('-')
            if clean_field == 'priority':
                target = '-priority_rank' if descending else 'priority_rank'
            else:
                target = f"-{clean_field}" if descending else clean_field
            ordering.append(target)
        return ordering

