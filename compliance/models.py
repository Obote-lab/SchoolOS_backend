import uuid
from django.db import models
from django.conf import settings


class AuditLog(models.Model):
    """Model for tracking all system actions."""
    
    # Action type choices
    CREATE = 'Create'
    READ = 'Read'
    UPDATE = 'Update'
    DELETE = 'Delete'
    LOGIN = 'Login'
    LOGOUT = 'Logout'
    EXPORT = 'Export'
    PRINT = 'Print'
    APPROVE = 'Approve'
    ACTION_CHOICES = [
        (CREATE, 'Create'),
        (READ, 'Read'),
        (UPDATE, 'Update'),
        (DELETE, 'Delete'),
        (LOGIN, 'Login'),
        (LOGOUT, 'Logout'),
        (EXPORT, 'Export'),
        (PRINT, 'Print'),
        (APPROVE, 'Approve'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='audit_logs'
    )
    user_role = models.CharField(max_length=100, blank=True)
    user_ip = models.GenericIPAddressField(blank=True, null=True)
    user_device = models.CharField(max_length=500, blank=True)
    action_type = models.CharField(max_length=20, choices=ACTION_CHOICES)
    model_name = models.CharField(max_length=100)
    record_id = models.CharField(max_length=100, null=True, blank=True)
    field_changed = models.CharField(max_length=100, blank=True)
    old_value = models.TextField(blank=True)
    new_value = models.TextField(blank=True)
    reason = models.TextField(blank=True)
    approval_required = models.BooleanField(default=False)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,blank=True,related_name='audit_approvals')
    school = models.ForeignKey('schools.School',on_delete=models.SET_NULL,null=True,blank=True,related_name='audit_logs')
    timestamp = models.DateTimeField(auto_now_add=True)
    location = models.CharField(max_length=200, blank=True)  # Simplified from point
    session_id = models.CharField(max_length=100, blank=True)
    checksum = models.CharField(max_length=64, blank=True)
    blockchain_hash = models.CharField(max_length=128, blank=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['action_type', 'model_name']),
            models.Index(fields=['school', 'timestamp']),
        ]
    
    def __str__(self):
        return f"{self.action_type} on {self.model_name} by {self.user}"


class DataExportLog(models.Model):
    """Model for tracking data exports."""
    
    # Export type choices
    STUDENTS = 'Students'
    FINANCE = 'Finance'
    ACADEMICS = 'Academics'
    HEALTH = 'Health'
    FULL_BACKUP = 'Full_Backup'
    EXPORT_CHOICES = [
        (STUDENTS, 'Students'),
        (FINANCE, 'Finance'),
        (ACADEMICS, 'Academics'),
        (HEALTH, 'Health'),
        (FULL_BACKUP, 'Full Backup'),
    ]
    
    # Format choices
    EXCEL = 'Excel'
    PDF = 'PDF'
    CSV = 'CSV'
    JSON = 'JSON'
    FORMAT_CHOICES = [
        (EXCEL, 'Excel'),
        (PDF, 'PDF'),
        (CSV, 'CSV'),
        (JSON, 'JSON'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    exported_by = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name='data_exports' )
    export_type = models.CharField(max_length=20, choices=EXPORT_CHOICES)
    format = models.CharField(max_length=10, choices=FORMAT_CHOICES)
    filters_applied = models.JSONField(default=dict, blank=True)
    row_count = models.IntegerField(default=0)
    file_size = models.BigIntegerField(default=0)  # in bytes
    download_link = models.URLField(blank=True)
    expires_at = models.DateTimeField()
    purpose = models.TextField(blank=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,null=True,blank=True,related_name='export_approvals')
    approval_required = models.BooleanField(default=False)
    access_log = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.export_type} export by {self.exported_by}"


class SystemHealth(models.Model):
    """Model for tracking system health metrics."""
    
    # Status choices
    SUCCESS = 'Success'
    WARNING = 'Warning'
    FAILED = 'Failed'
    PENDING = 'Pending'
    STATUS_CHOICES = [
        (SUCCESS, 'Success'),
        (WARNING, 'Warning'),
        (FAILED, 'Failed'),
        (PENDING, 'Pending'),
    ]
    
    # Sync status choices
    SYNCED = 'Synced'
    SYNC_PENDING = 'Pending'
    SYNC_FAILED = 'Failed'
    SYNC_CHOICES = [
        (SYNCED, 'Synced'),
        (SYNC_PENDING, 'Pending'),
        (SYNC_FAILED, 'Failed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey('schools.School', on_delete=models.CASCADE, related_name='system_health' )
    check_timestamp = models.DateTimeField(auto_now_add=True)
    server_uptime = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)  # in hours
    active_users = models.IntegerField(default=0)
    pending_tasks = models.IntegerField(default=0)
    failed_jobs = models.IntegerField(default=0)
    storage_used = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)  # in GB
    storage_available = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)  # in GB
    backup_status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=PENDING)
    last_backup = models.DateTimeField(null=True, blank=True)
    sync_status = models.CharField(max_length=10, choices=SYNC_CHOICES, default=SYNC_PENDING)
    last_sync = models.DateTimeField(null=True, blank=True)
    performance_score = models.DecimalField(max_digits=5, decimal_places=2, default=100.0)  # 1-100
    issues_detected = models.JSONField(default=list, blank=True)
    recommendations = models.TextField(blank=True)
    checked_by = models.CharField(max_length=100, blank=True)
    
    class Meta:
        ordering = ['-check_timestamp']
        verbose_name_plural = "System Health"
    
    def __str__(self):
        return f"System Health for {self.school} at {self.check_timestamp}"
    
    def save(self, *args, **kwargs):
        # Auto-calculate storage usage percentage
        if self.storage_used > 0 and self.storage_available > 0:
            total = self.storage_used + self.storage_available
            usage_percent = (self.storage_used / total) * 100
            
            # Adjust performance score based on storage usage
            if usage_percent > 90:
                self.performance_score = max(0, self.performance_score - 30)
            elif usage_percent > 80:
                self.performance_score = max(0, self.performance_score - 15)
            
            # Add warning if storage is low
            if usage_percent > 90 and 'low_storage' not in self.issues_detected:
                self.issues_detected = list(self.issues_detected)

        
        super().save(*args, **kwargs)


class ComplianceCheck(models.Model):
    """Model for tracking compliance checks."""
    
    # Check type choices
    NEMIS = 'NEMIS'
    TSC = 'TSC'
    KNEC = 'KNEC'
    MINISTRY = 'Ministry'
    SAFETY = 'Safety'
    FINANCIAL = 'Financial'
    CHECK_CHOICES = [
        (NEMIS, 'NEMIS'),
        (TSC, 'TSC'),
        (KNEC, 'KNEC'),
        (MINISTRY, 'Ministry'),
        (SAFETY, 'Safety'),
        (FINANCIAL, 'Financial'),
    ]
    
    # Status choices
    COMPLIANT = 'Compliant'
    PARTIAL = 'Partial'
    NON_COMPLIANT = 'Non_Compliant'
    NOT_APPLICABLE = 'Not_Applicable'
    STATUS_CHOICES = [
        (COMPLIANT, 'Compliant'),
        (PARTIAL, 'Partial'),
        (NON_COMPLIANT, 'Non Compliant'),
        (NOT_APPLICABLE, 'Not Applicable'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey('schools.School',on_delete=models.CASCADE,related_name='compliance_checks')
    check_date = models.DateField()
    check_type = models.CharField(max_length=20, choices=CHECK_CHOICES)
    requirements = models.JSONField(default=list, blank=True)
    system_health_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PARTIAL)
    issues_found = models.JSONField(default=list, blank=True)
    action_plan = models.TextField(blank=True)
    responsible_person = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,related_name='compliance_responsibilities')
    deadline = models.DateField(null=True, blank=True)
    verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,null=True, blank=True, related_name='compliance_verifications')
    verification_date = models.DateField(null=True, blank=True)
    next_check_date = models.DateField(null=True, blank=True)
    score = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)  # 0-100
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-check_date']
        verbose_name_plural = "Compliance Checks"
    
    def __str__(self):
        return f"{self.check_type} check for {self.school} on {self.check_date}"
    
    def save(self, *args, **kwargs):
        # Auto-calculate score based on status
        if self.system_health_status == self.COMPLIANT:
            self.score = 100.0
        elif self.system_health_status == self.PARTIAL:
            self.score = 50.0
        elif self.system_health_status == self.NON_COMPLIANT:
            self.score = 0.0
        elif self.system_health_status == self.NOT_APPLICABLE:
            self.score = 100.0
        
        # Auto-set next check date if not provided (6 months later)
        if not self.next_check_date and self.check_date:
            import datetime
            self.next_check_date = self.check_date + datetime.timedelta(days=180)
        
        super().save(*args, **kwargs)