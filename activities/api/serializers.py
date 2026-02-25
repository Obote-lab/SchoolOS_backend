from rest_framework import serializers
from django.conf import settings
from ..models import Activity, StudentActivity, Competition
from staff.models import StaffProfile

class ActivitySerializer(serializers.ModelSerializer):
    """Serializer for Activity model."""
    
    school_name = serializers.CharField(source='school.name', read_only=True)
    school_code = serializers.CharField(source='school.code', read_only=True)
    teacher_name = serializers.CharField(source='teacher_in_charge.get_full_name', read_only=True)
    assistant_name = serializers.CharField(source='assistant_in_charge.get_full_name', read_only=True, allow_null=True)
    
    class Meta:
        model = Activity
        fields = [
            'id',
            'school', 'school_name', 'school_code',
            'name', 'activity_category', 'sub_category',
            'description',
            'teacher_in_charge', 'teacher_name',
            'assistant_in_charge', 'assistant_name',
            'max_participants', 'current_participants',
            'schedule', 'equipment_needed',
            'budget_allocated', 'budget_used',
            'achievements',
            'activity_status', 'season',
            'performance_metrics', 'prerequisites',
            'uniform_required', 'parent_consent_required', 'risk_assessment_done',
            'created_at'
        ]
        read_only_fields = ['current_participants', 'created_at']
    
    def validate(self, data):
        """Custom validation for Activity."""
        
        # Ensure budget_used doesn't exceed budget_allocated
        if 'budget_used' in data and 'budget_allocated' in data:
            if data['budget_used'] > data['budget_allocated']:
                raise serializers.ValidationError(
                    {"budget_used": "Budget used cannot exceed budget allocated."}
                )
        
        # Validate max_participants
        if 'max_participants' in data and data['max_participants'] <= 0:
            raise serializers.ValidationError(
                {"max_participants": "Maximum participants must be greater than 0."}
            )
        
        # Validate that teacher and assistant are staff members
        teacher = data.get('teacher_in_charge')
        assistant = data.get('assistant_in_charge')
        

        if teacher and not StaffProfile.objects.filter(user=teacher).exists():
            raise serializers.ValidationError(
                {"teacher_in_charge": "Teacher in charge must be a staff member."}
            )
        
        if assistant and not StaffProfile.objects.filter(user=assistant).exists():
            raise serializers.ValidationError(
                {"assistant_in_charge": "Assistant in charge must be a staff member."}
            )
        
        return data


class SimpleActivitySerializer(serializers.ModelSerializer):
    """Simplified serializer for nested representations."""
    
    class Meta:
        model = Activity
        fields = ['id', 'name', 'activity_category', 'activity_status', 'current_participants']


class StudentActivitySerializer(serializers.ModelSerializer):
    """Serializer for StudentActivity model."""
    
    student_name = serializers.CharField(source='student.user.get_full_name', read_only=True)
    student_admission = serializers.CharField(source='student.admission_number', read_only=True)
    activity_name = serializers.CharField(source='activity.name', read_only=True)
    activity_category = serializers.CharField(source='activity.activity_category', read_only=True)
    
    class Meta:
        model = StudentActivity
        fields = [
            'id',
            'student', 'student_name', 'student_admission',
            'activity', 'activity_name', 'activity_category',
            'role', 'start_date', 'end_date',
            'student_status', 'performance_level',
            'achievements', 'hours_logged', 'attendance_rate',
            'coach_feedback', 'improvement_areas',
            'talent_score', 'potential_level', 'career_potential',
            'recommendations',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']
    
    def validate(self, data):
        """Custom validation for StudentActivity."""
        
        student = data.get('student') or getattr(self.instance, 'student', None)
        activity = data.get('activity') or getattr(self.instance, 'activity', None)
        
        if student and activity:
            if student.school != activity.school:
                raise serializers.ValidationError(
                    "Student and activity must belong to the same school."
                )
            
            # Check if activity has space
            if activity.current_participants >= activity.max_participants:
                raise serializers.ValidationError(
                    f"Activity '{activity.name}' has reached maximum participants."
                )
        
        # Validate dates
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        
        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError(
                {"end_date": "End date must be after start date."}
            )
        
        # Validate numeric ranges
        talent_score = data.get('talent_score')
        if talent_score is not None and (talent_score < 0 or talent_score > 100):
            raise serializers.ValidationError(
                {"talent_score": "Talent score must be between 0 and 100."}
            )
        
        attendance_rate = data.get('attendance_rate')
        if attendance_rate is not None and (attendance_rate < 0 or attendance_rate > 100):
            raise serializers.ValidationError(
                {"attendance_rate": "Attendance rate must be between 0 and 100."}
            )
        return data

class CompetitionSerializer(serializers.ModelSerializer):
    """Serializer for Competition model."""
    
    activity_name = serializers.CharField(source='activity.name', read_only=True)
    activity_category = serializers.CharField(source='activity.activity_category', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    
    class Meta:
        model = Competition
        fields = [
            'id',
            'activity', 'activity_name', 'activity_category',
            'name', 'level', 'date', 'venue', 'organizer',
            'results', 'participants', 'media_links',
            'learnings', 'next_competition',
            'budget_used', 'sponsors',
            'created_by', 'created_by_name',
            'created_at'
        ]
        read_only_fields = ['created_at']
    
    def validate(self, data):
        """Custom validation for Competition."""
        
        activity = data.get('activity') or getattr(self.instance, 'activity', None)
        created_by = data.get('created_by') or getattr(self.instance, 'created_by', None)
        if activity and created_by:
            if activity.school != created_by.school:
                raise serializers.ValidationError(
                    "Competition creator must belong to the same school as the activity."
                )
        
        budget_used = data.get('budget_used', 0)
        if budget_used < 0:
            raise serializers.ValidationError(
                {"budget_used": "Budget used cannot be negative."}
            )
        
        return data


class ActivityStatisticsSerializer(serializers.Serializer):
    """Serializer for activity statistics."""
    
    total_activities = serializers.IntegerField()
    active_activities = serializers.IntegerField()
    total_participants = serializers.IntegerField()
    activities_by_category = serializers.DictField()
    avg_participation_rate = serializers.FloatField()


class StudentTalentReportSerializer(serializers.Serializer):
    """Serializer for student talent report."""
    
    student_id = serializers.UUIDField()
    student_name = serializers.CharField()
    admission_number = serializers.CharField()
    activities_count = serializers.IntegerField()
    talent_score_avg = serializers.FloatField()
    potential_level = serializers.CharField()
    career_potential = serializers.BooleanField()
    top_activities = serializers.ListField()