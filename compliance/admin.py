# compliance/admin.py
from django.contrib import admin
from .models import AuditLog, DataExportLog, SystemHealth, ComplianceCheck

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'action_type', 'model_name', 'timestamp', 'school')
    list_filter = ('action_type', 'model_name', 'timestamp', 'school')
    search_fields = ('user__username', 'model_name', 'user_ip')
    readonly_fields = ('timestamp',)
    date_hierarchy = 'timestamp'

@admin.register(DataExportLog)
class DataExportLogAdmin(admin.ModelAdmin):
    list_display = ('exported_by', 'export_type', 'format', 'row_count', 'created_at')
    list_filter = ('export_type', 'format', 'created_at')
    search_fields = ('exported_by__username', 'purpose')
    readonly_fields = ('created_at',)

@admin.register(SystemHealth)
class SystemHealthAdmin(admin.ModelAdmin):
    list_display = ('school', 'check_timestamp', 'performance_score', 'backup_status', 'sync_status')
    list_filter = ('backup_status', 'sync_status', 'school')
    search_fields = ('school__name', 'checked_by')
    readonly_fields = ('check_timestamp',)

@admin.register(ComplianceCheck)
class ComplianceCheckAdmin(admin.ModelAdmin):
    list_display = ('school', 'check_type', 'check_date', 'system_health_status', 'score', 'responsible_person')
    list_filter = ('check_type', 'system_health_status', 'school')
    search_fields = ('school__name', 'action_plan')
    readonly_fields = ('created_at',)