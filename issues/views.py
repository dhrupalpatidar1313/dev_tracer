from typing import override

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from django.conf import settings

from drf_spectacular.utils import extend_schema, OpenApiParameter
from .models import Reporter, Issue, CriticalIssue, LowPriorityIssue
from .serializers import (
    BriefReporterSerializer, BriefIssueSerializer,
    BriefReporterResponseSerializer, BriefIssueResponseSerializer, ErrorSerializer
)
from . import services

class BriefBaseView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = []
    versioning_class = None
    error_style = "brief"

    def check_permissions(self, request):
        if not getattr(settings, 'BRIEF_API_ENABLED', True):
            self.permission_denied(request, message="Brief API is disabled")
        super().check_permissions(request)

class BriefReporterView(BriefBaseView):
    
    @extend_schema(
        tags=['Brief'],
        summary='Create a Reporter',
        request=BriefReporterSerializer,
        responses={201: BriefReporterResponseSerializer, 400: ErrorSerializer}
    )
    @override
    def post(self, request):
        serializer = BriefReporterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        reporter = Reporter(
            name=data.get('name'),
            email=data.get('email'),
            team=data.get('team')
        )
        if 'id' in data:
            reporter.id = data['id']

        try:
            reporter.validate()
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        if 'id' in data and Reporter.objects.filter(pk=reporter.id).exists():
            return Response(
                {"error": f"Reporter with id {reporter.id} already exists"},
                status=status.HTTP_400_BAD_REQUEST
            )

        services.create_reporter(reporter)
        return Response(reporter.to_dict(), status=status.HTTP_201_CREATED)
    
    @extend_schema(
        tags=['Brief'],
        summary='Get Reporters',
        parameters=[
            OpenApiParameter('id', type=int, description='Filter by ID', required=False)
        ],
        responses={200: BriefReporterResponseSerializer(many=True), 400: ErrorSerializer, 404: ErrorSerializer}
    )
    @override
    def get(self, request):
        id_param = request.query_params.get('id')
        if id_param is not None:
            try:
                obj_id = int(id_param)
            except ValueError:
                return Response({"error": "id must be an integer"}, status=status.HTTP_400_BAD_REQUEST)
            
            reporter = Reporter.objects.filter(pk=obj_id).first()
            if not reporter:
                return Response({"error": "Reporter not found"}, status=status.HTTP_404_NOT_FOUND)
            return Response(reporter.to_dict())

        reporters = Reporter.objects.all()
        return Response([r.to_dict() for r in reporters])


class BriefIssueView(BriefBaseView):
    @extend_schema(
        tags=['Brief'],
        summary='Create an Issue',
        request=BriefIssueSerializer,
        responses={201: BriefIssueResponseSerializer, 400: ErrorSerializer}
    )
    @override
    def post(self, request):
        serializer = BriefIssueSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        kwargs = {
            'title': data.get('title'),
            'description': data.get('description', ''),
            'status': data.get('status', 'open'),
            'priority': data.get('priority', 'medium'),
            'reporter_id': data.get('reporter_id')
        }
        
        priority = kwargs['priority']
        if priority == 'critical':
            issue = CriticalIssue(**kwargs)
        elif priority == 'low':
            issue = LowPriorityIssue(**kwargs)
        else:
            issue = Issue(**kwargs)

        if 'id' in data:
            issue.id = data['id']

        try:
            issue.validate()
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        if not Reporter.objects.filter(pk=issue.reporter_id).exists():
            return Response(
                {"error": f"Reporter with id {issue.reporter_id} does not exist"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if 'id' in data and Issue.objects.filter(pk=issue.id).exists():
            return Response(
                {"error": f"Issue with id {issue.id} already exists"},
                status=status.HTTP_400_BAD_REQUEST
            )

        services.create_issue(issue)
        
        resp_data = issue.to_dict()
        resp_data["message"] = issue.describe()
        return Response(resp_data, status=status.HTTP_201_CREATED)

    @extend_schema(
        tags=['Brief'],
        summary='Get Issues',
        parameters=[
            OpenApiParameter('id', type=int, description='Filter by ID', required=False),
            OpenApiParameter('status', type=str, description='Filter by status', required=False)
        ],
        responses={200: BriefIssueResponseSerializer(many=True), 400: ErrorSerializer, 404: ErrorSerializer}
    )
    @override   
    def get(self, request):
        id_param = request.query_params.get('id')
        if id_param is not None:
            try:
                obj_id = int(id_param)
            except ValueError:
                return Response({"error": "id must be an integer"}, status=status.HTTP_400_BAD_REQUEST)
            
            issue = Issue.objects.filter(pk=obj_id).first()
            if not issue:
                return Response({"error": "Issue not found"}, status=status.HTTP_404_NOT_FOUND)
            return Response(issue.to_dict())

        qs = Issue.objects.all()
        status_filter = request.query_params.get('status')
        if status_filter:
            if status_filter not in Issue.VALID_STATUSES:
                return Response(
                    {"error": "Invalid status. Must be one of: open, in_progress, resolved, closed"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            qs = qs.filter(status=status_filter)

        return Response([i.to_dict() for i in qs])


from django.contrib.auth import get_user_model, authenticate
from rest_framework.authtoken.models import Token
from rest_framework.permissions import IsAuthenticated
from .permissions import IsAdminRole
from .serializers import RegisterSerializer, LoginSerializer, UserBriefSerializer, SetRoleSerializer
from django.contrib.auth.models import Group
from drf_spectacular.utils import extend_schema, OpenApiExample

from rest_framework.throttling import ScopedRateThrottle

User = get_user_model()

class RegisterView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'auth'
    error_style = "v1"

    @extend_schema(tags=['Auth'], request=RegisterSerializer, responses={201: UserBriefSerializer})
    def post(self, request, *args, **kwargs):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = User.objects.create_user(
            username=serializer.validated_data['username'],
            email=serializer.validated_data.get('email', ''),
            password=serializer.validated_data['password']
        )
        token, _ = Token.objects.get_or_create(user=user)
        return Response({
            "token": token.key,
            "user": UserBriefSerializer(user).data
        }, status=status.HTTP_201_CREATED)

class LoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'auth'
    error_style = "v1"

    @extend_schema(tags=['Auth'], request=LoginSerializer, responses={200: UserBriefSerializer})
    def post(self, request, *args, **kwargs):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate(
            username=serializer.validated_data['username'],
            password=serializer.validated_data['password']
        )
        if not user:
            return Response({"error": "Invalid credentials", "code": "invalid_credentials"}, status=status.HTTP_400_BAD_REQUEST)
        
        token, _ = Token.objects.get_or_create(user=user)
        return Response({
            "token": token.key,
            "user": UserBriefSerializer(user).data
        })

class LogoutView(APIView):
    permission_classes = [IsAuthenticated]
    error_style = "v1"

    @extend_schema(tags=['Auth'], request=None, responses={204: None})
    def post(self, request, *args, **kwargs):
        request.user.auth_token.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

class MeView(APIView):
    permission_classes = [IsAuthenticated]
    error_style = "v1"

    @extend_schema(tags=['Auth'], responses={200: UserBriefSerializer})
    def get(self, request, *args, **kwargs):
        return Response(UserBriefSerializer(request.user).data)

class UserListView(APIView):
    permission_classes = [IsAuthenticated]
    error_style = "v1"

    @extend_schema(tags=['Auth'], responses={200: UserBriefSerializer(many=True)})
    def get(self, request, *args, **kwargs):
        users = User.objects.all()
        return Response(UserBriefSerializer(users, many=True).data)

class UserSetRoleView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]
    error_style = "v1"

    @extend_schema(tags=['Auth'], request=SetRoleSerializer, responses={200: UserBriefSerializer})
    def post(self, request, pk, *args, **kwargs):
        try:
            user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response({"error": "User not found", "code": "not_found"}, status=status.HTTP_404_NOT_FOUND)
            
        role = request.data.get('role')
        if role not in ['admin', 'developer', 'viewer']:
            return Response({"error": "Invalid role", "code": "invalid_role"}, status=status.HTTP_400_BAD_REQUEST)
            
        # Clear groups and set new one
        user.groups.clear()
        group, _ = Group.objects.get_or_create(name=role)
        user.groups.add(group)
        
        return Response(UserBriefSerializer(user).data)


# =====================================================================
#                          v1 ModelViewSets
# =====================================================================

from rest_framework import viewsets
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404
from django.db.models import Count, F, Avg, DurationField, ExpressionWrapper
from django.db.models.functions import TruncDate
from django.utils import timezone
import datetime
from django_filters.rest_framework import DjangoFilterBackend

from .models import Label, Comment, StatusHistory
from .permissions import (
    IsDeveloperOrAdmin, IsIssueEditor, IsAuthorOrAdmin
)
from .serializers import (
    ReporterSerializer, LabelSerializer, IssueListSerializer,
    IssueDetailSerializer, IssueWriteSerializer, TransitionSerializer,
    AssignSerializer, CommentSerializer, StatusHistorySerializer,
    DashboardResponseSerializer, StatisticsResponseSerializer
)
from .filters import IssueFilter, ReporterFilter


class ReporterViewSet(viewsets.ModelViewSet):
    queryset = Reporter.objects.annotate(issue_count=Count('issues')).order_by('id')
    serializer_class = ReporterSerializer
    filterset_class = ReporterFilter
    search_fields = ['name', 'email']
    ordering_fields = ['id', 'name', 'email', 'team']
    error_style = "v1"

    def get_permissions(self):
        if self.action == 'destroy':
            return [IsAuthenticated(), IsAdminRole()]
        elif self.action in ['create', 'update', 'partial_update']:
            return [IsAuthenticated(), IsDeveloperOrAdmin()]
        return [IsAuthenticated()]

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        services.delete_reporter(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['get'], url_path='issues')
    def issues(self, request, pk=None, *args, **kwargs):
        reporter = self.get_object()
        issues_qs = Issue.objects.with_related().with_counts().with_priority_rank().filter(reporter=reporter)
        filterset = IssueFilter(request.GET, queryset=issues_qs, request=request)
        if not filterset.is_valid():
            raise ValidationError(filterset.errors)
        filtered_qs = filterset.qs
        for backend in list(self.filter_backends):
            if backend != DjangoFilterBackend:
                filtered_qs = backend().filter_queryset(request, filtered_qs, self)
        page = self.paginate_queryset(filtered_qs)
        if page is not None:
            serializer = IssueListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = IssueListSerializer(filtered_qs, many=True)
        return Response(serializer.data)


class LabelViewSet(viewsets.ModelViewSet):
    queryset = Label.objects.all()
    serializer_class = LabelSerializer
    search_fields = ['name']
    ordering_fields = ['id', 'name', 'color']
    error_style = "v1"

    def get_permissions(self):
        if self.action == 'destroy':
            return [IsAuthenticated(), IsAdminRole()]
        elif self.action in ['create', 'update', 'partial_update']:
            return [IsAuthenticated(), IsDeveloperOrAdmin()]
        return [IsAuthenticated()]


class IssueViewSet(viewsets.ModelViewSet):
    queryset = Issue.objects.with_related().with_counts().with_priority_rank().all()
    filterset_class = IssueFilter
    search_fields = ['title', 'description']
    ordering_fields = ['id', 'title', 'status', 'priority', 'created_at', 'updated_at']
    error_style = "v1"

    def get_serializer_class(self):
        if self.action == 'list':
            return IssueListSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return IssueWriteSerializer
        return IssueDetailSerializer

    def get_permissions(self):
        if self.action == 'destroy':
            return [IsAuthenticated(), IsAdminRole()]
        elif self.action == 'create':
            return [IsAuthenticated(), IsDeveloperOrAdmin()]
        elif self.action in ['update', 'partial_update', 'transition', 'assign']:
            return [IsAuthenticated(), IsIssueEditor()]
        elif self.action == 'comments':
            if self.request.method == 'POST':
                return [IsAuthenticated(), IsDeveloperOrAdmin()]
            return [IsAuthenticated()]
        elif self.action == 'comment_detail':
            return [IsAuthenticated(), IsAuthorOrAdmin()]
        elif self.action in ['labels', 'label_detach']:
            if self.request.method in ['POST', 'DELETE']:
                return [IsAuthenticated(), IsIssueEditor()]
            return [IsAuthenticated()]
        return [IsAuthenticated()]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        issue = Issue(
            title=serializer.validated_data['title'],
            description=serializer.validated_data.get('description', ''),
            status=serializer.validated_data.get('status', 'open'),
            priority=serializer.validated_data.get('priority', 'medium'),
            reporter=serializer.validated_data['reporter'],
            assignee=serializer.validated_data.get('assignee', None),
            created_by=request.user,
        )
        services.create_issue(issue, actor=request.user)
        out = IssueDetailSerializer(issue)
        return Response(out.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        services.update_issue(instance, serializer.validated_data, actor=request.user)
        return Response(IssueDetailSerializer(instance).data)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'], url_path='transition')
    def transition(self, request, pk=None, *args, **kwargs):
        instance = self.get_object()
        serializer = TransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_status = serializer.validated_data['status']
        note = serializer.validated_data.get('note', '')
        services.change_status(instance, new_status, actor=request.user, note=note)
        return Response(IssueDetailSerializer(instance).data)

    @action(detail=True, methods=['post'], url_path='assign')
    def assign(self, request, pk=None, *args, **kwargs):
        instance = self.get_object()
        serializer = AssignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        assignee = serializer.validated_data['assignee']
        services.assign_issue(instance, assignee, actor=request.user)
        return Response(IssueDetailSerializer(instance).data)

    @action(detail=True, methods=['get'], url_path='history')
    def history(self, request, pk=None, *args, **kwargs):
        instance = self.get_object()
        history_qs = instance.status_history.select_related('changed_by').all()
        page = self.paginate_queryset(history_qs)
        if page is not None:
            serializer = StatusHistorySerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = StatusHistorySerializer(history_qs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get', 'post'], url_path='comments')
    def comments(self, request, pk=None, *args, **kwargs):
        instance = self.get_object()
        if request.method == 'GET':
            comments_qs = instance.comments.select_related('author').all()
            serializer = CommentSerializer(comments_qs, many=True)
            return Response(serializer.data)
        else:
            serializer = CommentSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            comment = services.add_comment(instance, request.user, serializer.validated_data['body'])
            return Response(CommentSerializer(comment).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['patch', 'delete'], url_path=r'comments/(?P<comment_id>\d+)')
    def comment_detail(self, request, pk=None, comment_id=None, *args, **kwargs):
        issue = get_object_or_404(Issue, pk=pk)
        comment = get_object_or_404(issue.comments.select_related('author'), pk=comment_id)
        self.check_object_permissions(request, comment)
        if request.method == 'PATCH':
            serializer = CommentSerializer(comment, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            services.update_comment(comment, serializer.validated_data['body'])
            return Response(CommentSerializer(comment).data)
        else:
            services.delete_comment(comment)
            return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['get', 'post'], url_path='labels')
    def labels(self, request, pk=None, *args, **kwargs):
        instance = self.get_object()
        if request.method == 'GET':
            serializer = LabelSerializer(instance.labels.all(), many=True)
            return Response(serializer.data)
        else:
            label_id = request.data.get('label')
            if not label_id:
                raise ValidationError("Missing required field: label")
            label = get_object_or_404(Label, pk=label_id)
            services.add_label(instance, label)
            return Response(LabelSerializer(instance.labels.all(), many=True).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['delete'], url_path=r'labels/(?P<label_id>\d+)')
    def label_detach(self, request, pk=None, label_id=None, *args, **kwargs):
        instance = self.get_object()
        label = get_object_or_404(Label, pk=label_id)
        services.remove_label(instance, label)
        return Response(status=status.HTTP_204_NO_CONTENT)


# =====================================================================
#                          Insights Views
# =====================================================================

class DashboardView(APIView):
    permission_classes = [IsAuthenticated]
    error_style = "v1"

    @extend_schema(tags=['Insights'], summary='Dashboard metrics for current user', responses={200: DashboardResponseSerializer})
    def get(self, request, *args, **kwargs):
        user = request.user
        assigned_counts = {s: 0 for s in Issue.VALID_STATUSES}
        for item in Issue.objects.filter(assignee=user).values('status').annotate(count=Count('id')):
            assigned_counts[item['status']] = item['count']

        created_count = Issue.objects.filter(created_by=user).count()
        unassigned_active_count = Issue.objects.filter(assignee__isnull=True, status__in=['open', 'in_progress']).count()
        recent_qs = StatusHistory.objects.select_related('changed_by', 'issue').order_by('-changed_at', '-id')[:10]
        recent_data = StatusHistorySerializer(recent_qs, many=True).data

        return Response({
            "assigned_to_me": assigned_counts,
            "created_by_me": created_count,
            "unassigned_active": unassigned_active_count,
            "recent_activity": recent_data
        })


class StatisticsView(APIView):
    permission_classes = [IsAuthenticated]
    error_style = "v1"

    @extend_schema(tags=['Insights'], summary='System-wide statistics', responses={200: StatisticsResponseSerializer})
    def get(self, request, *args, **kwargs):
        total = Issue.objects.count()

        by_status = {s: 0 for s in Issue.VALID_STATUSES}
        for item in Issue.objects.values('status').annotate(count=Count('id')):
            by_status[item['status']] = item['count']

        by_priority = {p: 0 for p in Issue.VALID_PRIORITIES}
        for item in Issue.objects.values('priority').annotate(count=Count('id')):
            by_priority[item['priority']] = item['count']

        by_team = {}
        for item in Issue.objects.values('reporter__team').annotate(count=Count('id')):
            if item['reporter__team']:
                by_team[item['reporter__team']] = item['count']

        top_labels = list(Label.objects.annotate(count=Count('issues')).order_by('-count', 'name')[:5].values('id', 'name', 'count'))

        diff = ExpressionWrapper(F('resolved_at') - F('created_at'), output_field=DurationField())
        avg_diff = Issue.objects.filter(resolved_at__isnull=False).aggregate(avg_diff=Avg(diff))['avg_diff']
        avg_resolution_hours = round(avg_diff.total_seconds() / 3600.0, 2) if avg_diff is not None else None

        thirty_days_ago = timezone.now() - datetime.timedelta(days=30)
        daily_qs = Issue.objects.filter(created_at__gte=thirty_days_ago)\
            .annotate(date=TruncDate('created_at'))\
            .values('date')\
            .annotate(count=Count('id'))\
            .order_by('date')

        created_last_30_days = [
            {"date": str(item['date']), "count": item['count']}
            for item in daily_qs
        ]

        return Response({
            "total": total,
            "by_status": by_status,
            "by_priority": by_priority,
            "by_team": by_team,
            "top_labels": top_labels,
            "avg_resolution_hours": avg_resolution_hours,
            "created_last_30_days": created_last_30_days
        })

