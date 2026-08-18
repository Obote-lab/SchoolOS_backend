from datetime import timedelta
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics, request, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from accounts.api.permissions import HasPermission
from ..models import AttendancePattern, AttendanceRecord, AttendanceSession
from .permissions import IsAttendanceManager, IsSchoolStaff
from .serializers import (
    AtRiskStudentsAlertSerializer,
    AttendanceExportFlatSerializer,
    AttendancePatternSerializer,
    AttendanceRecordCreateSerializer,
    AttendanceRecordDetailSerializer,
    AttendanceRecordListSerializer,
    AttendanceReportRequestSerializer,
    AttendanceSessionCreateSerializer,
    AttendanceSessionDetailSerializer,
    AttendanceSessionListSerializer,
    BulkAttendanceCreateSerializer,
    ClassDailyAttendanceSummarySerializer,
    StudentCheckInSerializer,
    StudentCheckOutSerializer,
    TodaySchoolAttendanceSerializer,
    WeeklyAttendanceTrendSerializer,
)
from schools.models import Term
from core.choices.attendance import (
    AttendanceRecordStatusChoices,
    AttendanceSessionStatusChoices,
)
from core.choices.academic import TermStatusChoices
from students.models import StudentProfile


class AttendanceSessionViewSet(viewsets.ModelViewSet):
    queryset = AttendanceSession.objects.select_related(
        "school", "academic_year", "term", "conducted_by", "verified_by"
    )
    permission_classes = [IsAuthenticated, IsSchoolStaff]

    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["session_type", "date", "attendance_session_status"]
    search_fields = ["notes", "venue_name"]

    def get_serializer_class(self):
        if self.action == "list":
            return AttendanceSessionListSerializer
        if self.action in ["create", "update", "partial_update"]:
            return AttendanceSessionCreateSerializer
        return AttendanceSessionDetailSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return AttendanceSession.objects.none()
        return AttendanceSession.objects.filter(school=self.request.school)

    @action(detail=True, methods=["post"])
    def start(self, request, pk=None):
        session = self.get_object()
        if session.attendance_session_status != AttendanceSessionStatusChoices.SCHEDULED:
            return Response({"detail": "Session already started or completed"}, status=400)

        session.attendance_session_status = AttendanceSessionStatusChoices.ONGOING
        session.save(update_fields=["attendance_session_status"])
        return Response(AttendanceSessionDetailSerializer(session).data)


    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        session = self.get_object()
        if session.attendance_session_status != AttendanceSessionStatusChoices.ONGOING:
            return Response({"detail": "Session not ongoing"}, status=400)

        session.attendance_session_status = AttendanceSessionStatusChoices.COMPLETED
        session.verified_by = request.user
        session.save(update_fields=["attendance_session_status", "verified_by"])
        session.update_actual_count()
        return Response(AttendanceSessionDetailSerializer(session).data)

class AttendanceRecordViewSet(viewsets.ModelViewSet):
    queryset = AttendanceRecord.objects.select_related("session", "student", "verified_by")
    permission_classes = [IsAuthenticated, IsSchoolStaff]

    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["session", "student", "attendance_record_status", "device_used"]

    def get_serializer_class(self):
        if self.action == "list":
            return AttendanceRecordListSerializer
        if self.action in ["create", "update", "partial_update"]:
            return AttendanceRecordCreateSerializer
        return AttendanceRecordDetailSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return AttendanceRecord.objects.none()

        qs = AttendanceRecord.objects.filter(session__school=self.request.school)

        if hasattr(self.request.user, "student_profile"):
            qs = qs.filter(student=self.request.user.student_profile)

        return qs

    @action(detail=False, methods=["post"], url_path="bulk")
    def bulk_mark(self, request):
        serializer = BulkAttendanceCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        return Response(result, status=status.HTTP_201_CREATED)


    @action(detail=False, methods=["post"])
    def check_in(self, request):
        serializer = StudentCheckInSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        record = serializer.save()
        return Response(AttendanceRecordDetailSerializer(record).data)

    @action(detail=False, methods=["post"])
    def check_out(self, request):
        serializer = StudentCheckOutSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        record = serializer.save()
        return Response(AttendanceRecordDetailSerializer(record).data)


class AttendancePatternViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AttendancePattern.objects.select_related("student", "academic_year", "term")
    serializer_class = AttendancePatternSerializer
    permission_classes = [IsAuthenticated, IsSchoolStaff]

    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["student", "academic_year", "term", "risk_level"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return AttendancePattern.objects.none()
        return AttendancePattern.objects.filter(student__school=self.request.school)


#  DASHBOARD VIEWS
class TodayAttendanceView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated, IsSchoolStaff]
    serializer_class = TodaySchoolAttendanceSerializer

    def get_object(self):
        today = timezone.now().date()
        school = self.request.school

        sessions = AttendanceSession.objects.filter(school=school, date=today)
        records = AttendanceRecord.objects.filter(session__school=school, session__date=today)

        most_common = sessions.values("session_type").annotate(count=Count("id")).order_by("-count").first()

        total_expected = sessions.aggregate(total=Sum("expected_count"))["total"] or 0
        total_checked = records.count()

        data = {
            "date": today,
            "total_expected_students": total_expected,
            "total_checked_in": total_checked,
            "present": records.filter( attendance_record_status=AttendanceRecordStatusChoices.PRESENT).count(),
            "late": records.filter(attendance_record_status=AttendanceRecordStatusChoices.LATE).count(),
            "absent": records.filter(attendance_record_status=AttendanceRecordStatusChoices.ABSENT).count(),
            "excused_or_sick": records.filter(
                attendance_record_status__in=[
                    AttendanceRecordStatusChoices.EXCUSED,
                    AttendanceRecordStatusChoices.SICK,
                ]
            ).count(),
            "attendance_percentage": (
                round(
                    records.filter(
                        attendance_record_status__in=[
                            AttendanceRecordStatusChoices.PRESENT,
                            AttendanceRecordStatusChoices.LATE,
                        ]
                    ).count()
                    / total_checked
                    * 100,
                    1,
                )
                if total_checked
                else 0
            ),
            "sessions_completed": sessions.filter(
                attendance_session_status=AttendanceSessionStatusChoices.COMPLETED
            ).count(),
            "sessions_ongoing": sessions.filter(
                attendance_session_status=AttendanceSessionStatusChoices.ONGOING
            ).count(),
        }
        return data


class WeeklyTrendView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated, IsSchoolStaff]
    serializer_class = WeeklyAttendanceTrendSerializer

    def get(self, request):
        today = timezone.now().date()
        start = today - timedelta(days=6)

        daily = []
        total_rate = 0.0
        lowest = {"rate": 100.0, "date": None, "absences": 0}
        highest = {"rate": 0.0, "date": None, "absences": 0}

        for i in range(7):
            d = start + timedelta(days=i)
            records = AttendanceRecord.objects.filter(
                session__school=request.school, session__date=d
            )
            total = records.count()
            good = records.filter(attendance_record_status__in=["present", "late"]).count()
            rate = (good / total * 100) if total > 0 else 0
            absences = records.filter(attendance_record_status="absent").count()

            daily.append({
                "date": d,
                "rate": round(rate, 1),
                "total": total,
                "absences": absences,
            })
            total_rate += rate

            if rate < lowest["rate"]:
                lowest = {"date": d, "rate": rate, "absences": absences}
            if rate > highest["rate"]:
                highest = {"date": d, "rate": rate, "absences": 0}

        avg = round(total_rate / 7, 1) if daily else 0

        # Trend logic (your code is fine)
        trend = "stable"
        if len(daily) >= 3:
            recent = [d["rate"] for d in daily[-3:]]
            if all(recent[i] < recent[i-1] for i in range(1, len(recent))):
                trend = "down"
            elif all(recent[i] > recent[i-1] for i in range(1, len(recent))):
                trend = "up"

        data = {
            "week_start": start,
            "week_end": today,
            "daily_stats": daily,
            "average_attendance": avg,
            "trend_direction": trend,
            "lowest_day": lowest,
            "highest_day": highest,
        }
        return Response(data)


class AtRiskStudentsView(generics.ListAPIView):
    permission_classes = [IsAuthenticated, IsAttendanceManager]
    serializer_class = AtRiskStudentsAlertSerializer
    queryset = AttendancePattern.objects.none()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return AttendancePattern.objects.none()

        school = getattr(self.request, "school", None) or getattr(
            self.request.user, "school", None
        )
        if not school:
            return AttendancePattern.objects.none()

        # term_status=ACTIVE can match many schools' terms → use __in
        active_terms = Term.objects.filter(term_status=TermStatusChoices.ACTIVE)
        # Prefer school-scoped terms if Term links via academic_year__school:
        active_terms = active_terms.filter(academic_year__school=school)

        if not active_terms.exists():
            return AttendancePattern.objects.none()

        return (
            AttendancePattern.objects.filter(
                term__in=active_terms,
                student__school=school,
            )
            .filter(
                Q(attendance_rate__lt=75) | Q(consecutive_absent_days__gte=5)
            )
            .select_related("student__user", "term", "academic_year")
            .order_by("attendance_rate")
        )

class AttendanceReportView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated, IsAttendanceManager]
    serializer_class = AttendanceReportRequestSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        report_type = data["report_type"]
        start = data["start_date"]
        end = data.get("end_date", timezone.now().date())
        class_id = data.get("class_id")
        student_id = data.get("student_id")

        # Report – school + StudentProfile
        qs = AttendanceRecord.objects.filter(
            session__school=getattr(request, "school", None) or request.user.school,
            session__date__range=[start, end],
        )
        if class_id:
            student_ids = StudentProfile.objects.filter(current_class_id=class_id).values_list("id", flat=True)
            qs = qs.filter(student_id__in=student_ids)
            if student_id:
                qs = qs.filter(student_id=student_id)

        if report_type == "export_flat":
            # Flat export ready for CSV
            flat_data = qs.values(
                "session__date",
                "session__session_type",
                "session__start_time",
                "student__admission_number",
                "student__user__first_name",
                "student__user__last_name",
                "attendance_record_status",
                "check_in_time",
                "reason",
                "verified_by__first_name",
                "verified_by__last_name",
            )
            # You would normally return CSV here or paginated JSON
            return Response(list(flat_data))
        summary = {
            "period": f"{start} → {end}",
            "total_records": qs.count(),
            "by_status": qs.values("attendance_record_status")
            .annotate(count=Count("id"))
            .order_by("attendance_record_status"),
        }
        return Response(summary)


#  Class & Monthly Views
class ClassDailySummaryView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated, IsSchoolStaff]
    serializer_class = ClassDailyAttendanceSummarySerializer

    def get(self, request):
        class_id = request.query_params.get("class_id")
        target_date = request.query_params.get("date", timezone.now().date())

        if not class_id:
            return Response({"detail": "class_id is required"}, status=400)

        # FIX: Use correct model name (assuming it's in schools app)
        try:
            from schools.models import ClassRoom   # or whatever your class model is called
            class_obj = ClassRoom.objects.get(id=class_id, school=request.user.school)
        except Exception:
            return Response({"detail": "Class not found"}, status=404)

        students = class_obj.students.filter(is_active=True)

        # Get class-related sessions that day (adjust filtering logic)
        sessions = AttendanceSession.objects.filter(
            date=target_date,
            school=request.user.school,
            reference_id=class_id,
        ).order_by("start_time")

        # Build per-student summary
        student_rows = []
        for student in students:
            row = {
                "student_name": student.user.get_full_name(),
                "admission": student.admission_number,
                "status_counts": {"present": 0, "late": 0, "absent": 0, "excused": 0},
                "late_times": [],
                "absent_reasons": [],
            }
            for session in sessions:
                rec = AttendanceRecord.objects.filter(
                    session=session, student=student
                ).first()
                if rec:
                    row["status_counts"][rec.attendance_record_status] += 1
                    if rec.attendance_record_status == "late" and rec.check_in_time:
                        row["late_times"].append(rec.check_in_time.strftime("%H:%M"))
                    if rec.attendance_record_status == "absent" and rec.reason:
                        row["absent_reasons"].append(rec.reason[:60])
            student_rows.append(row)

        # Aggregate
        total_students = students.count()
        present = sum(r["status_counts"]["present"] for r in student_rows)
        late = sum(r["status_counts"]["late"] for r in student_rows)
        absent = sum(r["status_counts"]["absent"] for r in student_rows)
        excused = sum(r["status_counts"]["excused"] for r in student_rows)

        data = {
            "date": target_date,
            "class_name": class_obj.name,  # adjust field
            "class_id": str(class_obj.id),
            "total_students": total_students,
            "present": present,
            "late": late,
            "absent": absent,
            "excused": excused,
            "attendance_rate": (
                round((present + late) / (total_students * sessions.count()) * 100, 1)
                if sessions.count() > 0
                else 0
            ),
            "late_students": [
                r for r in student_rows if r["status_counts"]["late"] > 0
            ],
            "absent_students": [
                r for r in student_rows if r["status_counts"]["absent"] > 0
            ],
        }

        return Response(ClassDailyAttendanceSummarySerializer(data).data)


#  Export Example (very basic – extend with pagination or file response)
class AttendanceExportView(generics.ListAPIView):
    permission_classes = [IsAuthenticated, IsAttendanceManager]
    serializer_class = AttendanceExportFlatSerializer

    def get_queryset(self):
        start = self.request.query_params.get("start_date")
        end = self.request.query_params.get("end_date", timezone.now().date())
        if not start:
            return AttendanceRecord.objects.none()

        qs = (
            AttendanceRecord.objects.filter(
                session__school=self.request.user.school,
                session__date__range=[start, end],
            )
            .select_related("session", "student__user", "verified_by")
            .order_by(
                "session__date", "session__start_time", "student__admission_number"
            )
        )

        # Optional filters: class_id, student_id, status, etc.
        return qs