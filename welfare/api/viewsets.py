from rest_framework import viewsets, generics, status, filters
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Count, Q, Avg
from django.shortcuts import get_object_or_404
from django.utils import timezone
from datetime import timedelta
from ..models import DisciplineIncident, SickBayRecord, CounselingSession, WellnessCheck
from .serializers import (
    DisciplineIncidentListSerializer, SickBayRecordListSerializer,
    DisciplineIncidentDetailSerializer, SickBayRecordDetailSerializer,
    CounselingSessionDetailSerializer, WellnessCheckDetailSerializer,
    DisciplineIncidentCreateSerializer, SickBayRecordCreateSerializer,
    CounselingSessionCreateSerializer,
    ResolveIncidentSerializer, ScheduleFollowUpSerializer, CompleteSessionSerializer,
    WelfareStatisticsSerializer, StudentWelfareSummarySerializer,
    WelfareDashboardSerializer, WelfareReportSerializer, WelfareAlertsSerializer,
    FinanceDashboardSerializer, FinanceReportSerializer, MpesaCallbackSerializer,
)


#  DISCIPLINE INCIDENT VIEWS 
class DisciplineIncidentViewSet(viewsets.ModelViewSet):
    """Discipline incident management"""
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['student', 'discipline_category', 'severity', 'discipline_status', 'reported_by']
    search_fields = ['incident_code', 'description', 'location']
    
    def get_queryset(self):
        # Filter by date range if provided
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
  
        queryset = DisciplineIncident.objects.none()

        user = self.request.user
        if hasattr(user, 'student_profile'):
            queryset = DisciplineIncident.objects.filter(student=user.student_profile)
        else:
            queryset = DisciplineIncident.objects.all()

        
        if start_date and end_date:
            queryset = queryset.filter(date_occurred__date__range=[start_date, end_date])
        
        # Filter by student if user is a student
        user = self.request.user
        if hasattr(user, 'student_profile'):
            queryset = queryset.filter(student=user.student_profile)
        
        return queryset
    
    def get_serializer_class(self):
        if self.action == 'list':
            return DisciplineIncidentListSerializer
        elif self.action == 'create':
            return DisciplineIncidentCreateSerializer
        return DisciplineIncidentDetailSerializer
    
    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        """Resolve incident"""
        incident = self.get_object()
        serializer = ResolveIncidentSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        incident = serializer.update(incident, serializer.validated_data)
        return Response({'status': 'resolved', 'incident_code': incident.incident_code})
    
    @action(detail=True, methods=['post'])
    def schedule_follow_up(self, request, pk=None):
        """Schedule follow-up"""
        incident = self.get_object()
        serializer = ScheduleFollowUpSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        incident = serializer.update(incident, serializer.validated_data)
        return Response({'status': 'follow_up_scheduled'})
    
    @action(detail=True, methods=['post'])
    def notify_parent(self, request, pk=None):
        """Notify parent about incident"""
        incident = self.get_object()
        incident.parent_notified = True
        incident.parent_response = request.data.get('parent_response', '')
        incident.save()
        return Response({'status': 'parent_notified'})
    
    @action(detail=False, methods=['get'])
    def recent(self, request):
        """Get recent incidents"""
        recent = DisciplineIncident.objects.all().order_by('-date_occurred')[:10]
        serializer = self.get_serializer(recent, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def pending(self, request):
        """Get pending incidents"""
        pending = DisciplineIncident.objects.filter(discipline_status__in=['reported', 'investigating'])
        serializer = self.get_serializer(pending, many=True)
        return Response(serializer.data)


#  SICK BAY RECORD VIEWS 
class SickBayRecordViewSet(viewsets.ModelViewSet):
    """Sick bay record management"""
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['student', 'attended_by', 'is_contagious', 'class_excused']
    
    def get_queryset(self):
        # Filter by date range if provided
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        
        queryset = SickBayRecord.objects.all()

        user = self.request.user
        if hasattr(user, 'student_profile'):
            queryset = SickBayRecord.objects.filter(student=user.student_profile)
        else:
            queryset = SickBayRecord.objects.all()

        
        
        if start_date and end_date:
            queryset = queryset.filter(date__date__range=[start_date, end_date])
        
        # Filter by student if user is a student
        user = self.request.user
        if hasattr(user, 'student_profile'):
            queryset = queryset.filter(student=user.student_profile)
        
        return queryset
    
    def get_serializer_class(self):
        if self.action == 'list':
            return SickBayRecordListSerializer
        elif self.action == 'create':
            return SickBayRecordCreateSerializer
        return SickBayRecordDetailSerializer
    
    def perform_create(self, serializer):
        serializer.save(attended_by=self.request.user)
    
    @action(detail=True, methods=['post'])
    def notify_parent(self, request, pk=None):
        """Notify parent about medical issue"""
        record = self.get_object()
        record.parent_notified = True
        record.parent_response = request.data.get('parent_response', '')
        record.save()
        return Response({'status': 'parent_notified'})
    
    @action(detail=True, methods=['post'])
    def schedule_follow_up(self, request, pk=None):
        """Schedule medical follow-up"""
        record = self.get_object()
        record.follow_up_required = True
        record.follow_up_date = request.data.get('follow_up_date')
        record.save()
        return Response({'status': 'follow_up_scheduled'})
    
    @action(detail=False, methods=['get'])
    def today(self, request):
        """Get today's sick bay visits"""
        today = timezone.now().date()
        visits = SickBayRecord.objects.filter(date__date=today)
        serializer = self.get_serializer(visits, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def contagious(self, request):
        """Get contagious cases"""
        contagious = SickBayRecord.objects.filter(is_contagious=True).order_by('-date')
        serializer = self.get_serializer(contagious, many=True)
        return Response(serializer.data)


#  COUNSELING SESSION VIEWS 
class CounselingSessionViewSet(viewsets.ModelViewSet):
    """Counseling session management"""
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['student', 'counselor', 'session_type', 'counseling_status']
    search_fields = ['reason', 'location']
    queryset = CounselingSession.objects.none()

    
    def get_queryset(self):
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        queryset = CounselingSession.objects.all()

        user = self.request.user
        if hasattr(user, 'student_profile'):
            queryset = CounselingSession.objects.filter(student=user.student_profile)
        else:
            queryset = CounselingSession.objects.all()
        
        if start_date and end_date:
            queryset = queryset.filter(date__date__range=[start_date, end_date])
        
        user = self.request.user 
        if hasattr(user, 'student_profile'):
            queryset = queryset.filter(student=user.student_profile)
        
        if not self.request.user.has_perm('welfare.view_counseling_sessions'):
            queryset = queryset.filter(counselor=self.request.user)

        return queryset
    
    def get_serializer_class(self):
        if self.action == 'list':
            return CounselingSessionDetailSerializer
        elif self.action == 'create':
            return CounselingSessionCreateSerializer
        return CounselingSessionDetailSerializer
    
    def perform_create(self, serializer):
        serializer.save(counselor=self.request.user)
    
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """Complete counseling session"""
        session = self.get_object()
        serializer = CompleteSessionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        session = serializer.update(session, serializer.validated_data)
        return Response({'status': 'completed'})
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel counseling session"""
        session = self.get_object()
        session.counseling_status = 'cancelled'
        session.save()
        return Response({'status': 'cancelled'})
    
    @action(detail=False, methods=['get'])
    def upcoming(self, request):
        """Get upcoming sessions"""
        upcoming = CounselingSession.objects.filter(
            date__gte=timezone.now(),
            counseling_status='scheduled'
        ).order_by('date')
        serializer = self.get_serializer(upcoming, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def my_sessions(self, request):
        """Get counselor's sessions"""
        sessions = CounselingSession.objects.filter(counselor=request.user).order_by('-date')
        serializer = self.get_serializer(sessions, many=True)
        return Response(serializer.data)


#  WELLNESS CHECK VIEWS 
class WellnessCheckViewSet(viewsets.ModelViewSet):
    """Wellness check management"""
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['student', 'checked_by', 'academic_stress_level']
    
    def get_queryset(self):
        # Filter by date range if provided
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        
        queryset = WellnessCheck.objects.all()

        user = self.request.user
        if hasattr(user, 'student_profile'):
            queryset = WellnessCheck.objects.filter(student=user.student_profile)
        else:
            queryset = WellnessCheck.objects.all()
            
        if start_date and end_date:
            queryset = queryset.filter(check_date__range=[start_date, end_date])
        
        # Filter by student if user is a student
        user = self.request.user
        if hasattr(user, 'student_profile'):
            queryset = queryset.filter(student=user.student_profile)
        
        return queryset
    
    def get_serializer_class(self):
        return WellnessCheckDetailSerializer
    
    def perform_create(self, serializer):
        serializer.save(checked_by=self.request.user)
    
    @action(detail=False, methods=['get'])
    def recent(self, request):
        """Get recent wellness checks"""
        recent = WellnessCheck.objects.all().order_by('-check_date')[:10]
        serializer = self.get_serializer(recent, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def critical(self, request):
        """Get critical wellness cases"""
        critical = WellnessCheck.objects.filter(
            Q(academic_stress_level='critical') |
            Q(mental_wellbeing_score__lt=4) |
            Q(physical_wellbeing_score__lt=4) |
            Q(social_wellbeing_score__lt=4)
        ).order_by('-check_date')
        serializer = self.get_serializer(critical, many=True)
        return Response(serializer.data)


#  DASHBOARD & STATISTICS VIEWS 
class WelfareDashboardView(generics.GenericAPIView):
    """Welfare dashboard"""
    permission_classes = [IsAuthenticated]
    serializer_class = WelfareDashboardSerializer 
    queryset = DisciplineIncident.objects.none() 
    # queryset = None 
    
    def get(self, request):
        data = {
            'today_stats': self.get_today_stats(),
            'recent_incidents': self.get_recent_incidents(),
            'today_sick_visits': self.get_today_sick_visits(),
            'upcoming_sessions': self.get_upcoming_sessions(),
            'critical_wellness': self.get_critical_wellness(),
        }
        return Response(data)
    
    def get_today_stats(self):
        """Get today's welfare statistics"""
        today = timezone.now().date()
        
        incidents = DisciplineIncident.objects.filter(date_occurred__date=today)
        sick_visits = SickBayRecord.objects.filter(date__date=today)
        sessions = CounselingSession.objects.filter(date__date=today)
        
        return {
            'date': today,
            'incidents_today': incidents.count(),
            'open_incidents': incidents.filter(discipline_status__in=['reported', 'investigating']).count(),
            'sick_visits': sick_visits.count(),
            'contagious_cases': sick_visits.filter(is_contagious=True).count(),
            'counseling_sessions': sessions.count(),
        }
    
    def get_recent_incidents(self):
        """Get recent discipline incidents"""
        recent = DisciplineIncident.objects.all().order_by('-date_occurred')[:5]
        return DisciplineIncidentListSerializer(recent, many=True).data
    
    def get_today_sick_visits(self):
        """Get today's sick bay visits"""
        today = timezone.now().date()
        visits = SickBayRecord.objects.filter(date__date=today)
        return SickBayRecordListSerializer(visits, many=True).data
    
    def get_upcoming_sessions(self):
        """Get upcoming counseling sessions"""
        upcoming = CounselingSession.objects.filter(
            date__gte=timezone.now(),
            counseling_status='scheduled'
        ).order_by('date')[:5]
        return CounselingSessionDetailSerializer(upcoming, many=True).data
    
    def get_critical_wellness(self):
        """Get critical wellness cases"""
        critical = WellnessCheck.objects.filter(
            academic_stress_level='critical'
        ).order_by('-check_date')[:5]
        return WellnessCheckDetailSerializer(critical, many=True).data


class WelfareStatisticsView(generics.GenericAPIView):
    """Welfare statistics"""
    permission_classes = [IsAuthenticated]
    serializer_class = WelfareStatisticsSerializer
    queryset = DisciplineIncident.objects.none()
    
    def post(self, request):
        """Get welfare statistics"""
        serializer = WelfareStatisticsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        stats = serializer.get_statistics()
        return Response(stats)


class StudentWelfareView(generics.GenericAPIView):
    """Student welfare summary"""
    permission_classes = [IsAuthenticated]
    serializer_class = StudentWelfareSummarySerializer
    queryset = DisciplineIncident.objects.none()
    
    def get(self, request):
        """Get student welfare summary"""
        student_id = request.query_params.get('student')
        
        if not student_id:
            # If user is a student, use their own ID
            user = request.user
            if hasattr(user, 'student_profile'):
                student_id = user.student_profile.id
            else:
                return Response({'error': 'student parameter required'}, status=400)
        
        serializer = StudentWelfareSummarySerializer(data={'student_id': student_id})
        serializer.is_valid(raise_exception=True)
        summary = serializer.get_summary(student_id)
        return Response(summary)


#  REPORT VIEWS 
class WelfareReportView(generics.GenericAPIView):
    """Welfare reports"""
    permission_classes = [IsAuthenticated]
    serializer_class = WelfareReportSerializer
    queryset = DisciplineIncident.objects.none() 
    
    def post(self, request):
        """Generate welfare report"""
        report_type = request.data.get('type', 'incidents')
        start_date = request.data.get('start_date')
        end_date = request.data.get('end_date')
        student_id = request.data.get('student')
        
        if not start_date or not end_date:
            return Response({'error': 'start_date and end_date required'}, status=400)
        
        if report_type == 'incidents':
            report = self.generate_incident_report(start_date, end_date, student_id)
        elif report_type == 'health':
            report = self.generate_health_report(start_date, end_date, student_id)
        elif report_type == 'counseling':
            report = self.generate_counseling_report(start_date, end_date, student_id)
        elif report_type == 'wellness':
            report = self.generate_wellness_report(start_date, end_date, student_id)
        else:
            return Response({'error': 'Invalid report type'}, status=400)
        
        return Response(report)
    
    def generate_incident_report(self, start_date, end_date, student_id=None):
        """Generate discipline incident report"""
        incidents = DisciplineIncident.objects.filter(
            date_occurred__date__range=[start_date, end_date]
        )
        
        if student_id:
            incidents = incidents.filter(student_id=student_id)
        
        by_category = incidents.values('discipline_category').annotate(
            count=Count('id'),
            minor=Count('id', filter=Q(severity='minor')),
            moderate=Count('id', filter=Q(severity='moderate')),
            major=Count('id', filter=Q(severity='major')),
            critical=Count('id', filter=Q(severity='critical')),
        )
        
        by_status = incidents.values('discipline_status').annotate(count=Count('id'))
        
        return {
            'report_type': 'incidents',
            'period': f"{start_date} to {end_date}",
            'total_incidents': incidents.count(),
            'by_category': list(by_category),
            'by_status': list(by_status),
            'top_students': incidents.values(
                'student__admission_number',
                'student__user__first_name',
                'student__user__last_name'
            ).annotate(count=Count('id')).order_by('-count')[:10],
        }
    
    def generate_health_report(self, start_date, end_date, student_id=None):
        """Generate health report"""
        sick_records = SickBayRecord.objects.filter(
            date__date__range=[start_date, end_date]
        )
        
        if student_id:
            sick_records = sick_records.filter(student_id=student_id)
        
        by_complaint = sick_records.values('complaint').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        return {
            'report_type': 'health',
            'period': f"{start_date} to {end_date}",
            'total_visits': sick_records.count(),
            'contagious_cases': sick_records.filter(is_contagious=True).count(),
            'hospital_referrals': sick_records.filter(referred_to_hospital=True).count(),
            'class_excused': sick_records.filter(class_excused=True).count(),
            'top_complaints': list(by_complaint),
        }
    
    def generate_counseling_report(self, start_date, end_date, student_id=None):
        """Generate counseling report"""
        sessions = CounselingSession.objects.filter(
            date__date__range=[start_date, end_date]
        )
        
        if student_id:
            sessions = sessions.filter(student_id=student_id)
        
        by_type = sessions.values('session_type').annotate(
            count=Count('id'),
            completed=Count('id', filter=Q(counseling_status='completed')),
            cancelled=Count('id', filter=Q(counseling_status='cancelled')),
        )
        
        return {
            'report_type': 'counseling',
            'period': f"{start_date} to {end_date}",
            'total_sessions': sessions.count(),
            'completed_sessions': sessions.filter(counseling_status='completed').count(),
            'by_type': list(by_type),
            'top_counselors': sessions.values(
                'counselor__first_name',
                'counselor__last_name'
            ).annotate(count=Count('id')).order_by('-count')[:5],
        }
    
    def generate_wellness_report(self, start_date, end_date, student_id=None):
        """Generate wellness report"""
        wellness_checks = WellnessCheck.objects.filter(
            check_date__range=[start_date, end_date]
        )
        if student_id:
            wellness_checks = wellness_checks.filter(student_id=student_id)
        
        avg_scores = wellness_checks.aggregate(
            avg_mental=Avg('mental_wellbeing_score'),
            avg_physical=Avg('physical_wellbeing_score'),
            avg_social=Avg('social_wellbeing_score'),
        )
        
        by_stress_level = wellness_checks.values('academic_stress_level').annotate(
            count=Count('id')
        )
        return {
            'report_type': 'wellness',
            'period': f"{start_date} to {end_date}",
            'total_checks': wellness_checks.count(),
            'average_scores': avg_scores,
            'by_stress_level': list(by_stress_level),
            'low_wellness': wellness_checks.filter(
                Q(mental_wellbeing_score__lt=4) |
                Q(physical_wellbeing_score__lt=4) |
                Q(social_wellbeing_score__lt=4)
            ).count(),
        }


#  ALERT VIEWS 
class WelfareAlertsView(generics.GenericAPIView):
    """Welfare alerts"""
    permission_classes = [IsAuthenticated]
    serializer_class = WelfareAlertsSerializer
    queryset = DisciplineIncident.objects.none() 
    
    def get(self, request):
        """Get welfare alerts"""
        alerts = []
        
        # Pending incidents
        pending_incidents = DisciplineIncident.objects.filter(
            discipline_status__in=['reported', 'investigating']
        ).count()
        if pending_incidents > 0:
            alerts.append({
                'type': 'pending_incidents',
                'message': f'{pending_incidents} pending discipline incidents',
                'priority': 'high'
            })
        
        # Contagious cases
        contagious = SickBayRecord.objects.filter(
            is_contagious=True,
            date__date=timezone.now().date()
        ).count()
        if contagious > 0:
            alerts.append({
                'type': 'contagious_cases',
                'message': f'{contagious} contagious cases today',
                'priority': 'high'
            })
        
        # Critical wellness
        critical_wellness = WellnessCheck.objects.filter(
            academic_stress_level='critical'
        ).count()
        if critical_wellness > 0:
            alerts.append({
                'type': 'critical_wellness',
                'message': f'{critical_wellness} students with critical stress',
                'priority': 'high'
            })
        upcoming_sessions = CounselingSession.objects.filter(
            date__date=timezone.now().date(),
            counseling_status='scheduled'
        ).count()
        if upcoming_sessions > 0:
            alerts.append({
                'type': 'upcoming_sessions',
                'message': f'{upcoming_sessions} counseling sessions today',
                'priority': 'medium'
            })
        
        return Response(alerts)
    

# class WelfareReportExportView(generics.GenericAPIView):
#     """Export welfare reports to Excel/PDF"""
#     permission_classes = [IsAuthenticated]
    
#     def post(self, request):
#         report_type = request.data.get('type')
#         format = request.data.get('format', 'excel')
        
#         if format == 'excel':
#             import pandas as pd
#             from django.http import HttpResponse
#             df = pd.DataFrame([])
#             response = HttpResponse(content_type='application/vnd.ms-excel')
#             response['Content-Disposition'] = 'attachment; filename="welfare_report.xlsx"'
#             df.to_excel(response, index=False)
#             return response
        
#         elif format == 'pdf':
#             from django.http import HttpResponse
#             from reportlab.pdfgen import canvas
            
#             response = HttpResponse(content_type='application/pdf')
#             response['Content-Disposition'] = 'attachment; filename="welfare_report.pdf"'
#             p = canvas.Canvas(response)
#             # Add PDF content
#             p.drawString(100, 800, "Welfare Report")
#             p.showPage()
#             p.save()
#             return response