from django.urls import path, re_path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'reporters', views.ReporterViewSet, basename='reporter')
router.register(r'labels', views.LabelViewSet, basename='label')
router.register(r'issues', views.IssueViewSet, basename='issue')

v1_patterns = [
    path('auth/register/', views.RegisterView.as_view(), name='auth-register'),
    path('auth/login/', views.LoginView.as_view(), name='auth-login'),
    path('auth/logout/', views.LogoutView.as_view(), name='auth-logout'),
    path('auth/me/', views.MeView.as_view(), name='auth-me'),
    path('users/', views.UserListView.as_view(), name='user-list'),
    path('users/<int:pk>/set-role/', views.UserSetRoleView.as_view(), name='user-set-role'),
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),
    path('statistics/', views.StatisticsView.as_view(), name='statistics'),
    path('', include(router.urls)),
]

urlpatterns = [
    re_path(r'^(?P<version>v1)/', include(v1_patterns)),
    path('reporters/', views.BriefReporterView.as_view(), name='brief-reporters'),
    path('issues/', views.BriefIssueView.as_view(), name='brief-issues'),
]
