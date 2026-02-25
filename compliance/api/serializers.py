from rest_framework import serializers
from ..models import AuditLog, DataExportLog, SystemHealth, ComplianceCheck


class AuditLogSerializer(serializers.ModelSerializer):
    """Serializer for AuditLog model."""
    
    user_name = serializers.CharField(source='user.get_full_name', read_only=True, allow_null=True)
    school_name = serializers.CharField(source='school.name', read_only=True, allow_null=True)
    approved_by_name = serializers.CharField(source='approved_by.get_full_name', read_only=True, allow_null=True)
    
    class Meta:
        model = AuditLog
        fields = [
            'id',
            'user', 'user_name',
            'user_role',
            'user_ip',
            'user_device',
            'action_type',
            'model_name',
            'record_id',
            'field_changed',
            'old_value',
            'new_value',
            'reason',
            'approval_required',
            'approved_by', 'approved_by_name',
            'school', 'school_name',
            'timestamp',
            'location',
            'session_id',
            'checksum',
            'blockchain_hash'
        ]
        read_only_fields = ['timestamp']


class DataExportLogSerializer(serializers.ModelSerializer):
    """Serializer for DataExportLog model."""
    
    exported_by_name = serializers.CharField(source='exported_by.get_full_name', read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.get_full_name', read_only=True, allow_null=True)
    file_size_mb = serializers.SerializerMethodField()
    
    class Meta:
        model = DataExportLog
        fields = [
            'id',
            'exported_by', 'exported_by_name',
            'export_type',
            'format',
            'filters_applied',
            'row_count',
            'file_size',
            'file_size_mb',
            'download_link',
            'expires_at',
            'purpose',
            'approved_by', 'approved_by_name',
            'access_log',
            'created_at'
        ]
        read_only_fields = ['created_at']
    
    def get_file_size_mb(self, obj) -> float:
        """Convert bytes to megabytes."""
        if obj.file_size:
            return round(obj.file_size / (1024 * 1024), 2)
        return 0
    
    def validate(self, data):
        """Validate export data."""
        
        # Check if export requires approval
        if data.get('export_type') in [DataExportLog.STUDENTS, DataExportLog.FULL_BACKUP]:
            data['approval_required'] = True
        
        return data


class SystemHealthSerializer(serializers.ModelSerializer):
    """Serializer for SystemHealth model."""
    
    school_name = serializers.CharField(source='school.name', read_only=True)
    storage_total = serializers.SerializerMethodField()
    storage_usage_percent = serializers.SerializerMethodField()
    
    class Meta:
        model = SystemHealth
        fields = [
            'id',
            'school', 'school_name',
            'check_timestamp',
            'server_uptime',
            'active_users',
            'pending_tasks',
            'failed_jobs',
            'storage_used',
            'storage_available',
            'storage_total',
            'storage_usage_percent',
            'backup_status',
            'last_backup',
            'sync_status',
            'last_sync',
            'performance_score',
            'issues_detected',
            'recommendations',
            'checked_by'
        ]
        read_only_fields = ['check_timestamp']
    
    def get_storage_total(self, obj) -> int:
        """Calculate total storage."""
        return obj.storage_used + obj.storage_available
    
    def get_storage_usage_percent(self, obj) -> float:
        """Calculate storage usage percentage."""
        total = self.get_storage_total(obj)
        if total > 0:
            return round((obj.storage_used / total) * 100, 2)
        return 0


class ComplianceCheckSerializer(serializers.ModelSerializer):
    """Serializer for ComplianceCheck model."""
    
    school_name = serializers.CharField(source='school.name', read_only=True)
    responsible_person_name = serializers.CharField(source='responsible_person.get_full_name', read_only=True)
    verified_by_name = serializers.CharField(source='verified_by.get_full_name', read_only=True, allow_null=True)
    
    class Meta:
        model = ComplianceCheck
        fields = [
            'id',
            'school', 'school_name',
            'check_date',
            'check_type',
            'requirements',
            'system_health_status',
            'issues_found',
            'action_plan',
            'responsible_person', 'responsible_person_name',
            'deadline',
            'verified_by', 'verified_by_name',
            'verification_date',
            'next_check_date',
            'score',
            'created_at'
        ]
        read_only_fields = ['created_at']
    
    def validate(self, data):
        """Validate compliance check data."""
        
        # Validate dates
        check_date = data.get('check_date')
        deadline = data.get('deadline')
        next_check_date = data.get('next_check_date')
        
        if deadline and check_date and deadline < check_date:
            raise serializers.ValidationError(
                {"deadline": "Deadline cannot be before check date."}
            )
        
        if next_check_date and check_date and next_check_date <= check_date:
            raise serializers.ValidationError(
                {"next_check_date": "Next check date must be after check date."}
            )
        
        # Validate score range
        score = data.get('score')
        if score is not None and (score < 0 or score > 100):
            raise serializers.ValidationError(
                {"score": "Score must be between 0 and 100."}
            )
        
        return data


class AuditSummarySerializer(serializers.Serializer):
    """Serializer for audit summary statistics."""
    
    total_actions = serializers.IntegerField()
    today_actions = serializers.IntegerField()
    by_action_type = serializers.DictField()
    by_user = serializers.DictField()
    by_model = serializers.DictField()


class ComplianceStatsSerializer(serializers.Serializer):
    """Serializer for compliance statistics."""
    
    total_checks = serializers.IntegerField()
    compliant = serializers.IntegerField()
    non_compliant = serializers.IntegerField()
    by_check_type = serializers.DictField()
    avg_score = serializers.FloatField()