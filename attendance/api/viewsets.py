from rest_framework import viewsets, generics, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Count, Sum
from django.utils import timezone
from datetime import timedelta
from django.shortcuts import get_object_or_404

from .permissions import IsSchoolStaff, IsAttendanceManager
from ..models import AttendanceSession, AttendanceRecord, AttendancePattern
from schools.models import Term
from students.models import Student

from .serializers import (
    # List / summary
    AttendanceSessionListSerializer,
    AttendanceRecordListSerializer,
    # Detail
    AttendanceSessionDetailSerializer,
    AttendanceRecordDetailSerializer,
    AttendancePatternSerializer,
    # Write
    AttendanceSessionCreateUpdateSerializer,
    AttendanceRecordWriteSerializer,
    # Bulk
    BulkAttendanceCreateSerializer,
    # Self check-in/out
    StudentCheckInSerializer,
    StudentCheckOutSerializer,
    # Statistics & reports (read-only)
    DailyAttendanceStatsSerializer,
    TodaySchoolAttendanceSerializer,
    WeeklyAttendanceTrendSerializer,
    AtRiskStudentsAlertSerializer,
    ClassDailyAttendanceSummarySerializer,
    MonthlyAttendanceCalendarSerializer,
    AttendanceExportFlatSerializer,
    AttendanceReportRequestSerializer,
)


class AttendanceSessionViewSet(viewsets.ModelViewSet):
    """Manage attendance sessions (assemblies, lessons, etc.)"""
    permission_classes = [IsAuthenticated, IsSchoolStaff]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['session_type', 'date', 'attendance_session_status', 'conducted_by']
    search_fields = ['notes', 'location']

    def get_queryset(self):
        qs = AttendanceSession.objects.filter(school=self.request.user.school)
        start = self.request.query_params.get('start_date')
        end = self.request.query_params.get('end_date')
        if start and end:
            qs = qs.filter(date__range=[start, end])
        elif start:
            qs = qs.filter(date__gte=start)
        elif end:
            qs = qs.filter(date__lte=end)
        return qs

    def get_serializer_class(self):
        if self.action == 'list':
            return AttendanceSessionListSerializer
        if self.action in ['create', 'partial_update', 'update']:
            return AttendanceSessionCreateUpdateSerializer
        return AttendanceSessionDetailSerializer

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy', 'start', 'complete']:
            return [IsAuthenticated(), IsAttendanceManager()]
        return super().get_permissions()

    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        session = self.get_object()
        if session.attendance_session_status != AttendanceSession.AttendanceStatusChoices.SCHEDULED:
            return Response({"detail": "Session already started or completed"}, status=400)
        session.attendance_session_status = AttendanceSession.AttendanceStatusChoices.ONGOING
        session.save(update_fields=['attendance_session_status'])
        return Response({"status": "started", "session": AttendanceSessionDetailSerializer(session).data})

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        session = self.get_object()
        if session.attendance_session_status != AttendanceSession.AttendanceStatusChoices.ONGOING:
            return Response({"detail": "Session not ongoing"}, status=400)
        session.attendance_session_status = AttendanceSession.AttendanceStatusChoices.COMPLETED
        session.verified_by = request.user
        session.save(update_fields=['attendance_session_status', 'verified_by'])
        session.update_actual_count()
        return Response({"status": "completed"})

    @action(detail=True, methods=['get'])
    def summary(self, request, pk=None):
        session = self.get_object()
        return Response(AttendanceSessionDetailSerializer(session).data)


class AttendanceRecordViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsSchoolStaff]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['student', 'session', 'status', 'device_used']

    def get_queryset(self):
        qs = AttendanceRecord.objects.filter(session__school=self.request.user.school)
        if hasattr(self.request.user, 'student_profile'):
            qs = qs.filter(student=self.request.user.student_profile)
        return qs

    def get_serializer_class(self):
        if self.action == 'list':
            return AttendanceRecordListSerializer
        if self.action in ['create', 'update', 'partial_update']:
            return AttendanceRecordWriteSerializer
        return AttendanceRecordDetailSerializer

    @action(detail=False, methods=['post'], url_path='bulk')
    def bulk_mark(self, request):
        serializer = BulkAttendanceCreateSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        return Response(result, status=status.HTTP_201_CREATED if result['created_count'] else status.HTTP_200_OK)

    @action(detail=False, methods=['post'])
    def check_in(self, request):
        serializer = StudentCheckInSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        record = serializer.save()
        return Response(AttendanceRecordDetailSerializer(record).data)

    @action(detail=False, methods=['post'])
    def check_out(self, request):
        serializer = StudentCheckOutSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        record = serializer.save()
        return Response(AttendanceRecordDetailSerializer(record).data)


class AttendancePatternViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated, IsSchoolStaff]
    serializer_class = AttendancePatternSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['student', 'academic_year', 'term']

    def get_queryset(self):
        return AttendancePattern.objects.filter(student__school=self.request.user.school)

    @action(detail=False, methods=['get'], url_path='student-summary')
    def student_summary(self, request):
        """Get student's attendance summary patterns"""
        student_id = request.query_params.get('student')
        if not student_id:
            return Response({'detail': 'student parameter is required'}, status=400)

        patterns = AttendancePattern.objects.filter(
            student_id=student_id,
            student__school=request.user.school
        ).order_by('-academic_year__year', '-term__sequence')

        serializer = self.get_serializer(patterns, many=True)
        return Response(serializer.data)



#  Dashboard & Statistics Views
class TodayAttendanceView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated, IsSchoolStaff]
    serializer_class = TodaySchoolAttendanceSerializer

    def get_object(self):
        today = timezone.now().date()
        school = self.request.user.school

        sessions = AttendanceSession.objects.filter(school=school, date=today)
        records = AttendanceRecord.objects.filter(session__school=school, session__date=today)

        most_common_type = sessions.values('session_type').annotate(count=Count('id')).order_by('-count').first()

        data = {
            'date': today,
            'total_expected_students': sessions.aggregate(total=Count('expected_count'))['total'] or 0,
            'total_checked_in': records.count(),
            'present': records.filter(status='present').count(),
            'late': records.filter(status='late').count(),
            'absent': records.filter(status='absent').count(),
            'excused_or_sick': records.filter(status__in=['excused', 'sick']).count(),
            'sessions_completed': sessions.filter(attendance_session_status='completed').count(),
            'sessions_ongoing': sessions.filter(attendance_session_status='ongoing').count(),
        }
        data['attendance_percentage'] = (
            (data['present'] + data['late']) / data['total_checked_in'] * 100
            if data['total_checked_in'] > 0 else 0
        )
        data['most_common_session_type'] = most_common_type['session_type'] if most_common_type else None

        return data


class AttendanceDashboardView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated, IsSchoolStaff]

    def get(self, request):
        today_data = TodayAttendanceView().get_object()

        # Very basic weekly trend (you can improve this a lot)
        today = timezone.now().date()
        week_start = today - timedelta(days=today.weekday())
        daily = []
        for i in range(7):
            d = week_start + timedelta(days=i)
            recs = AttendanceRecord.objects.filter(session__school=request.user.school, session__date=d)
            total = recs.count()
            present_late = recs.filter(status__in=['present','late']).count()
            rate = (present_late / total * 100) if total > 0 else 0
            daily.append({'date': d, 'rate': rate, 'total': total})

        avg_rate = sum(d['rate'] for d in daily) / len(daily) if daily else 0

        data = {
            'today': today_data,
            'weekly_trend': {
                'week_start': week_start,
                'week_end': week_start + timedelta(days=6),
                'daily_stats': daily,
                'average_attendance': round(avg_rate, 1),
            },
            # You can add at-risk students, monthly calendar, etc. here
        }
        return Response(data)


class AttendanceReportView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated, IsAttendanceManager]
    serializer_class = AttendanceReportRequestSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        report_type = data['report_type']
        start = data['start_date']
        end = data.get('end_date', timezone.now().date())
        class_id = data.get('class_id')
        student_id = data.get('student_id')

        qs = AttendanceRecord.objects.filter(
            session__school=request.user.school,
            session__date__range=[start, end]
        )

        if class_id:
            student_ids = Student.objects.filter(current_class_id=class_id).values_list('id', flat=True)
            qs = qs.filter(student_id__in=student_ids)
        if student_id:
            qs = qs.filter(student_id=student_id)

        if report_type == 'export_flat':
            # Flat export ready for CSV
            flat_data = qs.values(
                'session__date',
                'session__session_type',
                'session__start_time',
                'student__admission_number',
                'student__user__first_name',
                'student__user__last_name',
                'status',
                'check_in_time',
                'reason',
                'verified_by__first_name',
                'verified_by__last_name',
            )
            # You would normally return CSV here or paginated JSON
            return Response(list(flat_data))
        summary = {
            'period': f"{start} → {end}",
            'total_records': qs.count(),
            'by_status': qs.values('status').annotate(count=Count('id')).order_by('status'),
        }
        return Response(summary)
    


#  Dashboard & Quick Stats Views
class TodayStatsView(generics.RetrieveAPIView):
    """
    Today's school-wide attendance snapshot
    Used for principal / admin dashboard widget
    """
    permission_classes = [IsAuthenticated, IsSchoolStaff]
    serializer_class = TodaySchoolAttendanceSerializer

    def get_object(self):
        today = timezone.now().date()
        school = self.request.user.school

        sessions_today = AttendanceSession.objects.filter(school=school, date=today)
        records_today = AttendanceRecord.objects.filter(
            session__school=school,
            session__date=today
        )

        most_common = sessions_today.values('session_type').annotate(
            cnt=Count('id')
        ).order_by('-cnt').first()

        data = {
            'date': today,
            'total_expected_students': sessions_today.aggregate(total=Sum('expected_count'))['total'] or 0,
            'total_checked_in': records_today.count(),
            'present': records_today.filter(status='present').count(),
            'late': records_today.filter(status='late').count(),
            'absent': records_today.filter(status='absent').count(),
            'excused_or_sick': records_today.filter(status__in=['excused', 'sick']).count(),
            'attendance_percentage': 0,
            'most_common_session_type': most_common['session_type'] if most_common else None,
            'sessions_completed': sessions_today.filter(attendance_session_status='completed').count(),
            'sessions_ongoing': sessions_today.filter(attendance_session_status='ongoing').count(),
        }

        if data['total_checked_in'] > 0:
            data['attendance_percentage'] = round(
                (data['present'] + data['late']) / data['total_checked_in'] * 100, 1
            )

        return data


class WeeklyTrendView(generics.GenericAPIView):
    """
    Simple 7-day attendance trend
    Can be extended to last 4 weeks, etc.
    """
    permission_classes = [IsAuthenticated, IsSchoolStaff]
    serializer_class = WeeklyAttendanceTrendSerializer

    def get(self, request):
        today = timezone.now().date()
        start = today - timedelta(days=6)  # last 7 days including today

        daily_data = []
        total_rate = 0
        lowest = {'rate': 100, 'date': None, 'absences': 0}
        highest = {'rate': 0, 'date': None, 'absences': 0}

        for i in range(7):
            d = start + timedelta(days=i)
            records = AttendanceRecord.objects.filter(
                session__school=request.user.school,
                session__date=d
            )
            total = records.count()
            good = records.filter(status__in=['present', 'late']).count()
            rate = (good / total * 100) if total > 0 else 0
            absences = records.filter(status='absent').count()

            daily_data.append({
                'date': d,
                'total': total,
                'present_late': good,
                'absent': absences,
                'rate': round(rate, 1)
            })

            total_rate += rate

            if rate < lowest['rate']:
                lowest = {'date': d, 'rate': rate, 'absences': absences}
            if rate > highest['rate']:
                highest = {'date': d, 'rate': rate, 'absences': 0}  

        avg = round(total_rate / 7, 1) if daily_data else 0
        trend = 'stable'
        if daily_data:
            recent = [d['rate'] for d in daily_data[-3:]]
            if len(recent) >= 3 and all(recent[i] < recent[i-1] for i in range(1, len(recent))):
                trend = 'down'
            elif len(recent) >= 3 and all(recent[i] > recent[i-1] for i in range(1, len(recent))):
                trend = 'up'

        data = {
            'week_start': start,
            'week_end': today,
            'daily_stats': daily_data,
            'average_attendance': avg,
            'trend_direction': trend,
            'lowest_day': lowest,
            'highest_day': highest,
        }

        return Response(WeeklyAttendanceTrendSerializer(data).data)


class AtRiskStudentsView(generics.ListAPIView):
    """
    Students with concerning attendance (low % or consecutive misses)
    """
    permission_classes = [IsAuthenticated, IsAttendanceManager]
    serializer_class = AtRiskStudentsAlertSerializer

    def get_queryset(self):
        current_term = Term.objects.filter(is_current=True).first()
        if not current_term:
            return AttendancePattern.objects.none()

        return AttendancePattern.objects.filter(
            term=current_term,
            student__school=self.request.user.school
        ).filter(
            Q(attendance_rate__lt=75) | Q(absent_count__gte=5)
        ).select_related('student__user').order_by('attendance_rate')


#  Class & Monthly Views
class ClassDailySummaryView(generics.GenericAPIView):
    """
    Daily attendance summary for one class (form teacher view)
    """
    permission_classes = [IsAuthenticated, IsSchoolStaff]
    serializer_class = ClassDailyAttendanceSummarySerializer

    def get(self, request):
        class_id = request.query_params.get('class_id')
        target_date = request.query_params.get('date', timezone.now().date())

        if not class_id:
            return Response({"detail": "class_id required"}, status=400)

        try:
            class_obj = Class.objects.get(id=class_id, school=request.user.school)
        except Class.DoesNotExist:
            return Response({"detail": "Class not found"}, status=404)

        students = class_obj.students.filter(is_active=True)  

        # Get class-related sessions that day (adjust filtering logic)
        sessions = AttendanceSession.objects.filter(
            date=target_date,
            school=request.user.school,
            reference_id=class_id, 
        ).order_by('start_time')

        # Build per-student summary
        student_rows = []
        for student in students:
            row = {
                'student_name': student.user.get_full_name(),
                'admission': student.admission_number,
                'status_counts': {'present': 0, 'late': 0, 'absent': 0, 'excused': 0},
                'late_times': [],
                'absent_reasons': [],
            }
            for session in sessions:
                rec = AttendanceRecord.objects.filter(session=session, student=student).first()
                if rec:
                    row['status_counts'][rec.status] += 1
                    if rec.status == 'late' and rec.check_in_time:
                        row['late_times'].append(rec.check_in_time.strftime('%H:%M'))
                    if rec.status == 'absent' and rec.reason:
                        row['absent_reasons'].append(rec.reason[:60])
            student_rows.append(row)

        # Aggregate
        total_students = students.count()
        present = sum(r['status_counts']['present'] for r in student_rows)
        late = sum(r['status_counts']['late'] for r in student_rows)
        absent = sum(r['status_counts']['absent'] for r in student_rows)
        excused = sum(r['status_counts']['excused'] for r in student_rows)

        data = {
            'date': target_date,
            'class_name': class_obj.name,  # adjust field
            'class_id': str(class_obj.id),
            'total_students': total_students,
            'present': present,
            'late': late,
            'absent': absent,
            'excused': excused,
            'attendance_rate': round((present + late) / (total_students * sessions.count()) * 100, 1) if sessions.count() > 0 else 0,
            'late_students': [r for r in student_rows if r['status_counts']['late'] > 0],
            'absent_students': [r for r in student_rows if r['status_counts']['absent'] > 0],
        }

        return Response(ClassDailyAttendanceSummarySerializer(data).data)



#  Export Example (very basic – extend with pagination or file response)
class AttendanceExportView(generics.ListAPIView):
    permission_classes = [IsAuthenticated, IsAttendanceManager]
    serializer_class = AttendanceExportFlatSerializer

    def get_queryset(self):
        start = self.request.query_params.get('start_date')
        end = self.request.query_params.get('end_date', timezone.now().date())
        if not start:
            return AttendanceRecord.objects.none()

        qs = AttendanceRecord.objects.filter(
            session__school=self.request.user.school,
            session__date__range=[start, end]
        ).select_related(
            'session', 'student__user', 'verified_by'
        ).order_by('session__date', 'session__start_time', 'student__admission_number')

        # Optional filters: class_id, student_id, status, etc.
        return qs