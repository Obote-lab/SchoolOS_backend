# from django.contrib import admin
# from .models import AttendanceSession, AttendanceRecord, AttendancePattern

# @admin.register(AttendanceSession)
# class AttendanceSessionAdmin(admin.ModelAdmin):
#     list_display = ('date', 'session_type', 'attendance_session_status', 'conducted_by', 'actual_count')
#     list_filter = ('date', 'session_type', 'attendance_session_status')
#     search_fields = ('location', 'notes', 'conducted_by__username')

# @admin.register(AttendanceRecord)
# class AttendanceRecordAdmin(admin.ModelAdmin):
#     list_display = ('student', 'session', 'status', 'check_in_time', 'device_used')
#     list_filter = ('status', 'device_used', 'session__date')
#     search_fields = ('student__admission_number', 'student__user__username')

# @admin.register(AttendancePattern)
# class AttendancePatternAdmin(admin.ModelAdmin):
#     list_display = ('student', 'academic_year', 'term', 'attendance_rate')
#     list_filter = ('academic_year', 'term')
#     search_fields = ('student__admission_number',)