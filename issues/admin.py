from django.contrib import admin
from .models import Reporter, Label, Issue, Comment, StatusHistory

class CommentInline(admin.TabularInline):
    model = Comment
    extra = 0

class StatusHistoryInline(admin.TabularInline):
    model = StatusHistory
    extra = 0
    readonly_fields = ('from_status', 'to_status', 'changed_by', 'note', 'changed_at')
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

@admin.register(Reporter)
class ReporterAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'email', 'team')
    search_fields = ('name', 'email', 'team')

@admin.register(Label)
class LabelAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'color')
    search_fields = ('name',)

@admin.register(Issue)
class IssueAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'status', 'priority', 'reporter', 'assignee', 'created_at')
    list_filter = ('status', 'priority', 'labels')
    search_fields = ('title', 'description')
    list_select_related = ('reporter', 'assignee')
    inlines = [CommentInline, StatusHistoryInline]

@admin.register(StatusHistory)
class StatusHistoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'issue', 'from_status', 'to_status', 'changed_by', 'changed_at')
    list_select_related = ('issue', 'changed_by')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
