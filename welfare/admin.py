from django.contrib import admin
from .models import DisciplineIncident, SickBayRecord, CounselingSession, WellnessCheck

@admin.register(DisciplineIncident)
class DisciplineIncidentAdmin(admin.ModelAdmin):
    list_display = ('incident_code', 'student', 'discipline_category', 'severity', 'discipline_status', 'date_occurred')
    list_filter = ('discipline_category', 'severity', 'discipline_status', 'date_occurred')
    search_fields = ('incident_code', 'student__admission_number', 'description')
    readonly_fields = ('incident_code', 'created_at', 'updated_at')

@admin.register(SickBayRecord)
class SickBayRecordAdmin(admin.ModelAdmin):
    list_display = ('student', 'complaint', 'date', 'is_contagious', 'attended_by')
    list_filter = ('is_contagious', 'class_excused', 'referred_to_hospital')
    search_fields = ('student__admission_number', 'complaint')

@admin.register(CounselingSession)
class CounselingSessionAdmin(admin.ModelAdmin):
    list_display = ('student', 'counselor', 'session_type', 'date', 'counseling_status')
    list_filter = ('session_type', 'counseling_status', 'date')
    search_fields = ('student__admission_number', 'reason')

@admin.register(WellnessCheck)
class WellnessCheckAdmin(admin.ModelAdmin):
    list_display = ('student', 'check_date', 'academic_stress_level', 'overall_wellness')
    list_filter = ('academic_stress_level', 'nutrition_quality', 'exercise_frequency')
    search_fields = ('student__admission_number',)