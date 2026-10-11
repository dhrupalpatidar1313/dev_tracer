from rest_framework import serializers
from django.contrib.auth import get_user_model
import django.contrib.auth.password_validation as validators
from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.utils import extend_schema_field

from .models import Reporter, Issue, Label, Comment, StatusHistory
from .permissions import get_role

User = get_user_model()

class StrictCharField(serializers.CharField):
    def to_internal_value(self, data):
        if not isinstance(data, str):
            self.fail('invalid')
        return super().to_internal_value(data).strip()

class StrictIntegerField(serializers.IntegerField):
    def to_internal_value(self, data):
        if isinstance(data, bool) or not isinstance(data, int):
            self.fail('invalid')
        return super().to_internal_value(data)

class EntityValidationMixin:
    def validate(self, attrs):
        attrs = super().validate(attrs)
        if self.instance:
            merged = {}
            for f in self.instance._meta.concrete_fields:
                merged[f.attname] = getattr(self.instance, f.attname)
            # Apply incoming changes
            for k, v in attrs.items():
                field = self.instance._meta.get_field(k)
                if field.is_relation and field.many_to_one:
                    merged[field.attname] = v.pk if v else None
                else:
                    merged[k] = v
                    
            temp_instance = self.instance.__class__(**{
                k: v for k, v in merged.items()
                if k in [f.attname for f in self.instance._meta.concrete_fields]
            })
            temp_instance.id = self.instance.id
        else:
            init_kwargs = {}
            for k, v in attrs.items():
                field = self.Meta.model._meta.get_field(k)
                if field.is_relation and field.many_to_one:
                    init_kwargs[field.name] = v
                else:
                    init_kwargs[k] = v
            temp_instance = self.Meta.model(**init_kwargs)

        try:
            temp_instance.validate()
        except ValueError as e:
            raise serializers.ValidationError(str(e))
        return attrs

# ---------------- Brief API Serializers ----------------

class BriefReporterSerializer(serializers.Serializer):
    id = StrictIntegerField(required=False, min_value=1, error_messages={
        'invalid': 'id must be a positive integer',
        'min_value': 'id must be a positive integer'
    })
    name = StrictCharField(allow_blank=True, error_messages={'invalid': 'Name must be a string'})
    email = StrictCharField(allow_blank=True, error_messages={'invalid': 'Email must be a string'})
    team = StrictCharField(allow_blank=True, error_messages={'invalid': 'Team must be a string'})

class BriefIssueSerializer(serializers.Serializer):
    id = StrictIntegerField(required=False, min_value=1, error_messages={
        'invalid': 'id must be a positive integer',
        'min_value': 'id must be a positive integer'
    })
    title = StrictCharField(allow_blank=True, error_messages={'invalid': 'Title must be a string'})
    description = StrictCharField(allow_blank=True, error_messages={'invalid': 'Description must be a string'})
    status = StrictCharField(allow_blank=True, error_messages={'invalid': 'Status must be a string'})
    priority = StrictCharField(allow_blank=True, error_messages={'invalid': 'Priority must be a string'})
    reporter_id = StrictIntegerField(min_value=1, error_messages={
        'invalid': 'reporter_id must be a positive integer',
        'min_value': 'reporter_id must be a positive integer'
    })

# Documentation-only response serializers for Swagger UI
class ErrorSerializer(serializers.Serializer):
    error = serializers.CharField()

class BriefReporterResponseSerializer(BriefReporterSerializer):
    id = serializers.IntegerField()

class BriefIssueResponseSerializer(BriefIssueSerializer):
    id = serializers.IntegerField()
    created_at = serializers.DateTimeField()
    message = serializers.CharField(required=False)

# ---------------- User & Auth Serializers ----------------

class UserBriefSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ('id', 'username', 'role')
        read_only_fields = fields

    @extend_schema_field(serializers.CharField())
    def get_role(self, obj):
        return get_role(obj)

class SetRoleSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=['admin', 'developer', 'viewer'])

class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField()
    email = serializers.EmailField(required=False, allow_blank=True)
    password = serializers.CharField(write_only=True)

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("A user with that username already exists.")
        return value

    def validate_password(self, value):
        try:
            validators.validate_password(password=value)
        except DjangoValidationError as e:
            raise serializers.ValidationError(list(e.messages))
        return value

class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

# ---------------- v1 Model Serializers ----------------

class ReporterSerializer(EntityValidationMixin, serializers.ModelSerializer):
    name = StrictCharField(allow_blank=True, error_messages={'invalid': 'Name must be a string'})
    email = StrictCharField(allow_blank=True, error_messages={'invalid': 'Email must be a string'})
    team = StrictCharField(allow_blank=True, error_messages={'invalid': 'Team must be a string'})
    issue_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Reporter
        fields = ('id', 'name', 'email', 'team', 'user', 'issue_count')

class LabelSerializer(EntityValidationMixin, serializers.ModelSerializer):
    name = StrictCharField(allow_blank=True, error_messages={'invalid': 'Name must be a string'})
    color = StrictCharField(allow_blank=True, error_messages={'invalid': 'Color must be a string'})

    class Meta:
        model = Label
        fields = ('id', 'name', 'color')

class IssueListSerializer(serializers.ModelSerializer):
    reporter_name = serializers.CharField(source='reporter.name', read_only=True)
    assignee = UserBriefSerializer(read_only=True)
    labels = serializers.SlugRelatedField(many=True, read_only=True, slug_field='name')
    comment_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Issue
        fields = (
            'id', 'title', 'status', 'priority', 'reporter', 'reporter_name',
            'assignee', 'labels', 'comment_count', 'created_at', 'updated_at'
        )

class IssueDetailSerializer(serializers.ModelSerializer):
    reporter = ReporterSerializer(read_only=True)
    assignee = UserBriefSerializer(read_only=True)
    created_by = UserBriefSerializer(read_only=True)
    labels = LabelSerializer(many=True, read_only=True)
    comment_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Issue
        fields = (
            'id', 'title', 'description', 'status', 'priority', 'reporter',
            'assignee', 'created_by', 'labels', 'comment_count', 'created_at',
            'updated_at', 'resolved_at'
        )

class IssueWriteSerializer(EntityValidationMixin, serializers.ModelSerializer):
    title = StrictCharField(allow_blank=True, error_messages={'invalid': 'Title must be a string'})
    description = StrictCharField(allow_blank=True, required=False, error_messages={'invalid': 'Description must be a string'})
    status = StrictCharField(allow_blank=True, required=False, default='open', error_messages={'invalid': 'Status must be a string'})
    priority = StrictCharField(allow_blank=True, required=False, default='medium', error_messages={'invalid': 'Priority must be a string'})

    class Meta:
        model = Issue
        fields = ('id', 'title', 'description', 'status', 'priority', 'reporter', 'assignee')

class TransitionSerializer(serializers.Serializer):
    status = StrictCharField(allow_blank=False, error_messages={'invalid': 'Status must be a string'})
    note = serializers.CharField(required=False, allow_blank=True)

class AssignSerializer(serializers.Serializer):
    assignee = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        allow_null=True,
        required=True
    )

class CommentSerializer(serializers.ModelSerializer):
    author = UserBriefSerializer(read_only=True)
    body = StrictCharField(allow_blank=True, error_messages={'invalid': 'Body must be a string'})

    class Meta:
        model = Comment
        fields = ('id', 'author', 'body', 'created_at', 'updated_at')
        read_only_fields = ('id', 'author', 'created_at', 'updated_at')

    def validate_body(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Comment body cannot be empty")
        return value

class StatusHistorySerializer(serializers.ModelSerializer):
    changed_by = UserBriefSerializer(read_only=True)

    class Meta:
        model = StatusHistory
        fields = ('id', 'from_status', 'to_status', 'changed_by', 'note', 'changed_at')
        read_only_fields = fields

class DashboardResponseSerializer(serializers.Serializer):
    assigned_to_me = serializers.DictField(child=serializers.IntegerField())
    created_by_me = serializers.IntegerField()
    unassigned_active = serializers.IntegerField()
    recent_activity = StatusHistorySerializer(many=True)

class DailyCountSerializer(serializers.Serializer):
    date = serializers.CharField()
    count = serializers.IntegerField()

class TopLabelSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    count = serializers.IntegerField()

class StatisticsResponseSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    by_status = serializers.DictField(child=serializers.IntegerField())
    by_priority = serializers.DictField(child=serializers.IntegerField())
    by_team = serializers.DictField(child=serializers.IntegerField())
    top_labels = TopLabelSerializer(many=True)
    avg_resolution_hours = serializers.FloatField(allow_null=True)
    created_last_30_days = DailyCountSerializer(many=True)

