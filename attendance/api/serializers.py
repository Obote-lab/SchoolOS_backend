from rest_framework import serializers
from django.utils import timezone
from django.db import transaction, models
from django.db.models import Count, Q
from ..models import AttendanceSession, AttendanceRecord, AttendancePattern
from students.models import Student 


#  List / Summary Serializers
class AttendanceSessionListSerializer(serializers.ModelSerializer):
    session_type_display = serializers.CharField(source='get_session_type_display', read_only=True)
    status_display = serializers.CharField(source='get_attendance_session_status_display', read_only=True)
    conducted_by_name = serializers.CharField(source='conducted_by.get_full_name', read_only=True, allow_null=True)

    class Meta:
        model = AttendanceSession
        fields = [
            'id', 'session_type', 'session_type_display',
            'date', 'start_time', 'end_time',
            'expected_count', 'actual_count',
            'attendance_session_status', 'status_display',
            'conducted_by', 'conducted_by_name',
            'location',
        ]
        read_only_fields = fields


class AttendanceRecordListSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.user.get_full_name', read_only=True)
    student_admission = serializers.CharField(source='student.admission_number', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    device_used_display = serializers.CharField(source='get_device_used_display', read_only=True)

    class Meta:
        model = AttendanceRecord
        fields = [
            'id', 'student', 'student_name', 'student_admission',
            'status', 'status_display',
            'check_in_time', 'check_out_time',
            'device_used', 'device_used_display',
            'created_at',
        ]
        read_only_fields = fields



#  Detail Serializers
class AttendanceSessionDetailSerializer(serializers.ModelSerializer):
    session_type_display = serializers.CharField(source='get_session_type_display', read_only=True)
    status_display = serializers.CharField(source='get_attendance_session_status_display', read_only=True)
    conducted_by_name = serializers.CharField(source='conducted_by.get_full_name', read_only=True, allow_null=True)
    verified_by_name = serializers.CharField(source='verified_by.get_full_name', read_only=True, allow_null=True)

    summary = serializers.SerializerMethodField()

    class Meta:
        model = AttendanceSession
        fields = [
            'id', 'session_type', 'session_type_display',
            'date', 'start_time', 'end_time',
            'expected_count', 'actual_count',
            'attendance_session_status', 'status_display',
            'conducted_by', 'conducted_by_name',
            'verified_by', 'verified_by_name',
            'notes', 'location', 'weather',
            'automated', 'device_id',
            'summary',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'summary']

    def get_summary(self, obj):
        return obj.records.aggregate(
            total=Count('id'),
            present=Count('id', filter=Q(status='present')),
            late=Count('id', filter=Q(status='late')),
            absent=Count('id', filter=Q(status='absent')),
            excused=Count('id', filter=Q(status='excused')),
            sick=Count('id', filter=Q(status='sick')),
            suspended=Count('id', filter=Q(status='suspended')),
        )


class AttendanceRecordDetailSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.user.get_full_name', read_only=True)
    student_admission = serializers.CharField(source='student.admission_number', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    device_used_display = serializers.CharField(source='get_device_used_display', read_only=True)
    verified_by_name = serializers.CharField(source='verified_by.get_full_name', read_only=True, allow_null=True)
    session_info = AttendanceSessionListSerializer(source='session', read_only=True)

    class Meta:
        model = AttendanceRecord
        fields = '__all__'
        read_only_fields = [
            'id', 'created_at', 'session_info',
            'student_name', 'student_admission',
            'status_display', 'device_used_display', 'verified_by_name',
        ]


class AttendancePatternSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.user.get_full_name', read_only=True)
    admission_number = serializers.CharField(source='student.admission_number', read_only=True)
    academic_year_name = serializers.CharField(source='academic_year.year_name', read_only=True) 
    term_name = serializers.CharField(source='term.name', read_only=True)

    class Meta:
        model = AttendancePattern
        fields = '__all__'
        read_only_fields = ['id', 'last_updated', 'student_name', 'admission_number', 'academic_year_name', 'term_name']


#  Write / Create Serializers
class AttendanceSessionCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = AttendanceSession
        fields = [
            'session_type', 'reference_id',
            'date', 'start_time', 'end_time',
            'expected_count', 'notes', 'location', 'weather',
        ]
        extra_kwargs = {
            'school': {'read_only': True},
            'academic_year': {'read_only': True},
            'term': {'read_only': True},
            'conducted_by': {'read_only': True},
            'verified_by': {'read_only': True},
            'actual_count': {'read_only': True},
            'attendance_session_status': {'read_only': True},
        }

    def validate(self, data):
        if data.get('end_time') and data.get('start_time') and data['end_time'] <= data['start_time']:
            raise serializers.ValidationError({'end_time': 'End time must be after start time.'})
        return data

    def create(self, validated_data):
        request = self.context['request']
        user = request.user
        school = user.school 

        validated_data.update({
            'school': school,
            'conducted_by': user,
            'academic_year': school.current_academic_year,
            'term': school.current_term,
            'attendance_session_status': AttendanceSession.AttendanceStatusChoices.SCHEDULED,
        })
        return super().create(validated_data)


class AttendanceRecordWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = AttendanceRecord
        fields = [
            'session', 'student', 'status',
            'check_in_time', 'check_out_time',
            'reason', 'doctor_note',
            'device_used', 'location',  
        ]
        extra_kwargs = {
            'verified_by': {'read_only': True},
        }

    def validate(self, data):
        session = data['session']
        student = data['student']
        if session.school_id != student.school_id:
            raise serializers.ValidationError("Student does not belong to this session's school.")
        return data

    def create(self, validated_data):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            validated_data['verified_by'] = request.user
        if not validated_data.get('check_in_time') and validated_data['status'] in ['present', 'late']:
            validated_data['check_in_time'] = timezone.now()
        return super().create(validated_data)



#  Bulk Operations
class BulkAttendanceItemSerializer(serializers.Serializer):
    student = serializers.UUIDField()
    status = serializers.ChoiceField(choices=AttendanceRecord.AttendanceRecordStatusChoices.choices)
    check_in_time = serializers.DateTimeField(required=False, allow_null=True)
    reason = serializers.CharField(required=False, allow_blank=True, max_length=500)


class BulkAttendanceCreateSerializer(serializers.Serializer):
    session = serializers.UUIDField()
    records = BulkAttendanceItemSerializer(many=True)

    @transaction.atomic
    def create(self, validated_data):
        request = self.context['request']
        school = request.user.school  # adjust relation
        session_id = validated_data['session']

        session = AttendanceSession.objects.select_for_update().filter(
            id=session_id, school=school
        ).first()
        if not session:
            raise serializers.ValidationError("Session not found or access denied.")

        created = []
        errors = []

        for item in validated_data['records']:
            try:
                student = Student.objects.get(id=item['student'], school=school)

                record, is_new = AttendanceRecord.objects.update_or_create(
                    session=session,
                    student=student,
                    defaults={
                        'status': item['status'],
                        'check_in_time': item.get('check_in_time'),
                        'reason': item.get('reason', ''),
                        'device_used': 'manual',
                        'verified_by': request.user,
                    }
                )
                created.append({
                    'record_id': str(record.id),
                    'student_id': str(student.id),
                    'status': record.status,
                    'was_created': is_new,
                })

            except Student.DoesNotExist:
                errors.append({'student': str(item['student']), 'error': 'Student not found in school'})
            except Exception as e:
                errors.append({'student': str(item['student']), 'error': str(e)})

        return {
            'session': str(session.id),
            'created_count': len(created),
            'created': created,
            'errors_count': len(errors),
            'errors': errors,
        }



#  Self Check-in / Check-out (mobile/kiosk)
class StudentCheckInSerializer(serializers.Serializer):
    session = serializers.UUIDField()
    device_used = serializers.ChoiceField(
        choices=AttendanceRecord.DeviceUsedChoices.choices,
        default=AttendanceRecord.DeviceUsedChoices.MOBILE_APP
    )
    location = serializers.CharField(required=False, allow_blank=True)

    def validate(self, data):
        request = self.context['request']
        school = request.user.school  # or student.school if student is auth
        if not AttendanceSession.objects.filter(id=data['session'], school=school).exists():
            raise serializers.ValidationError("Invalid or inaccessible session.")
        return data

    def create(self, validated_data):
        request = self.context['request']
        # Assuming authenticated student or staff acting for student
        student = getattr(request.user, 'student_profile', None)  
        if not student:
            raise serializers.ValidationError("No student profile associated.")

        record, created = AttendanceRecord.objects.get_or_create(
            session_id=validated_data['session'],
            student=student,
            defaults={
                'status': 'present',
                'check_in_time': timezone.now(),
                'device_used': validated_data['device_used'],
                'location': validated_data.get('location', ''),
                'verified_by': request.user,
            }
        )

        if not created and not record.check_in_time:
            record.check_in_time = timezone.now()
            record.device_used = validated_data['device_used']
            record.location = validated_data.get('location', record.location)
            record.save()

        return record


class StudentCheckOutSerializer(serializers.Serializer):
    session = serializers.UUIDField()

    def validate(self, data):
        request = self.context['request']
        school = request.user.school
        if not AttendanceSession.objects.filter(id=data['session'], school=school).exists():
            raise serializers.ValidationError("Invalid session.")
        return data

    def create(self, validated_data):
        student = getattr(self.context['request'].user, 'student_profile', None)
        if not student:
            raise serializers.ValidationError("No student profile.")

        try:
            record = AttendanceRecord.objects.get(
                session_id=validated_data['session'],
                student=student,
            )
            if record.check_out_time:
                raise serializers.ValidationError("Already checked out.")
            record.check_out_time = timezone.now()
            record.save()
            return record
        except AttendanceRecord.DoesNotExist:
            raise serializers.ValidationError("No check-in record found for this session.")



#  Statistics / Reports (read-only)
class DailyAttendanceStatsSerializer(serializers.Serializer):
    date = serializers.DateField(read_only=True)
    total_sessions = serializers.IntegerField(read_only=True)
    total_records = serializers.IntegerField(read_only=True)
    present = serializers.IntegerField(read_only=True)
    late = serializers.IntegerField(read_only=True)
    absent = serializers.IntegerField(read_only=True)
    excused = serializers.IntegerField(read_only=True)
    attendance_rate = serializers.FloatField(read_only=True)


class StudentDateRangeSummarySerializer(serializers.Serializer):
    student = serializers.UUIDField()
    start_date = serializers.DateField()
    end_date = serializers.DateField()

    def validate(self, data):
        if data['start_date'] > data['end_date']:
            raise serializers.ValidationError("start_date cannot be after end_date")
        if (data['end_date'] - data['start_date']).days > 366:
            raise serializers.ValidationError("Date range cannot exceed 1 year")
        school = self.context['request'].user.school
        if not Student.objects.filter(id=data['student'], school=school).exists():
            raise serializers.ValidationError("Student not found in your school")
        return data




#  Dashboard & Report Serializers (added)
class TodaySchoolAttendanceSerializer(serializers.Serializer):
    """Quick stats for today's dashboard (school-wide)"""
    date = serializers.DateField(read_only=True)
    total_expected_students = serializers.IntegerField(read_only=True)
    total_checked_in = serializers.IntegerField(read_only=True)
    present = serializers.IntegerField(read_only=True)
    late = serializers.IntegerField(read_only=True)
    absent = serializers.IntegerField(read_only=True)
    excused_or_sick = serializers.IntegerField(read_only=True)
    attendance_percentage = serializers.FloatField(read_only=True)
    most_common_session_type = serializers.CharField(read_only=True, allow_null=True)
    sessions_completed = serializers.IntegerField(read_only=True)
    sessions_ongoing = serializers.IntegerField(read_only=True)


class WeeklyAttendanceTrendSerializer(serializers.Serializer):
    """Weekly summary – usually last 7 days"""
    week_start = serializers.DateField(read_only=True)
    week_end = serializers.DateField(read_only=True)
    daily_stats = serializers.ListField(child=serializers.DictField(),read_only=True)
    average_attendance = serializers.FloatField(read_only=True)
    trend_direction = serializers.ChoiceField(
        choices=[('up', 'Improving'), ('down', 'Declining'), ('stable', 'Stable')],
        read_only=True
    )
    lowest_day = serializers.DictField(read_only=True, allow_null=True)   # {date, rate, absences}
    highest_day = serializers.DictField(read_only=True, allow_null=True)


class AtRiskStudentsAlertSerializer(serializers.Serializer):
    """Alert list for students with concerning attendance patterns"""
    student_id = serializers.UUIDField(read_only=True)
    admission_number = serializers.CharField(read_only=True)
    full_name = serializers.CharField(read_only=True)
    current_term_attendance_rate = serializers.FloatField(read_only=True)
    consecutive_absent_days = serializers.IntegerField(read_only=True)
    total_absent_this_term = serializers.IntegerField(read_only=True)
    risk_level = serializers.ChoiceField(
        choices=[
            ('low', 'Low'),
            ('medium', 'Medium'),
            ('high', 'High'),
            ('critical', 'Critical'),
        ],
        read_only=True
    )
    last_absent_date = serializers.DateField(read_only=True, allow_null=True)
    recommended_action = serializers.CharField(read_only=True, allow_blank=True)


class ClassDailyAttendanceSummarySerializer(serializers.Serializer):
    """Daily attendance for one class / form (teacher view)"""
    date = serializers.DateField(read_only=True)
    class_name = serializers.CharField(read_only=True)          # e.g. "Form 2A"
    class_id = serializers.UUIDField(read_only=True)
    total_students = serializers.IntegerField(read_only=True)
    present = serializers.IntegerField(read_only=True)
    late = serializers.IntegerField(read_only=True)
    absent = serializers.IntegerField(read_only=True)
    excused = serializers.IntegerField(read_only=True)
    attendance_rate = serializers.FloatField(read_only=True)
    late_students = serializers.ListField(
        child=serializers.DictField(),   # [{student_name, admission, time}]
        read_only=True,
        allow_empty=True
    )
    absent_students = serializers.ListField(
        child=serializers.DictField(),   # [{student_name, admission, reason?}]
        read_only=True,
        allow_empty=True
    )


class MonthlyAttendanceCalendarSerializer(serializers.Serializer):
    """Monthly view – summary per day (good for student/parent portal)"""
    year = serializers.IntegerField(read_only=True)
    month = serializers.IntegerField(read_only=True)
    month_name = serializers.CharField(read_only=True)
    total_school_days = serializers.IntegerField(read_only=True)
    days_attended = serializers.IntegerField(read_only=True)
    monthly_rate = serializers.FloatField(read_only=True)
    daily_summary = serializers.ListField(
        # child=serializers.DictField(     
        #     # children={
        #     #     'date': serializers.DateField(),
        #     #     'weekday': serializers.CharField(),
        #     #     'status_summary': serializers.DictField(),  
        #     #     'rate': serializers.FloatField(allow_null=True),
        #     # }
        # ),
        read_only=True
    )


class AttendanceExportFlatSerializer(serializers.Serializer):
    """Flat structure suitable for CSV/Excel export"""
    date = serializers.DateField()
    session_type = serializers.CharField()
    session_start_time = serializers.TimeField()
    student_admission_number = serializers.CharField()
    student_full_name = serializers.CharField()
    class_name = serializers.CharField(allow_null=True)
    status = serializers.CharField()
    status_display = serializers.CharField()
    check_in_time = serializers.DateTimeField(allow_null=True)
    reason = serializers.CharField(allow_blank=True)
    recorded_by = serializers.CharField(allow_null=True)
    verified_by = serializers.CharField(allow_null=True)


class AttendanceReportRequestSerializer(serializers.Serializer):
    """Input for generating reports (used in POST body)"""
    report_type = serializers.ChoiceField(choices=[
        ('daily', 'Daily School Summary'),
        ('class_daily', 'Class Daily Register'),
        ('student_term', 'Student Term Report'),
        ('monthly_calendar', 'Monthly Calendar View'),
        ('at_risk_list', 'At-Risk Students List'),
        ('export_flat', 'Export All Records (CSV/Excel)'),
    ])
    start_date = serializers.DateField()
    end_date = serializers.DateField(required=False)
    class_id = serializers.UUIDField(required=False, allow_null=True)
    student_id = serializers.UUIDField(required=False, allow_null=True)
    include_details = serializers.BooleanField(default=False)

    def validate(self, data):
        if data['start_date'] > (data.get('end_date') or timezone.now().date()):
            raise serializers.ValidationError("Start date cannot be in the future or after end date.")
        return data