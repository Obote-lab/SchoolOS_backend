from django.db.models import Avg, Count, F, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from accounts.api.permissions import HasPermission
from rest_framework.response import Response
from django.db.models import Sum
from students.models import StudentProfile
from ..models import Activity, Competition, StudentActivity
from .serializers import (
    ActivitySerializer,
    ActivityStatisticsSerializer,
    CompetitionSerializer,
    StudentActivitySerializer,
    StudentTalentReportSerializer,
)
from core.choices.activities import (
    ActivityStatusChoices,
    ActivityRoleChoices,
    StudentActivityStatusChoices,
)
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from collections import defaultdict


@extend_schema(tags=["Activities"])
class ActivityViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing Activities.

    Supports:
    - CRUD operations for activities
    - Filtering by school, category, status
    - Statistics endpoint
    - Search by name, description
    """

    queryset = Activity.objects.all()
    serializer_class = ActivitySerializer
    # permission_classes = [IsAuthenticated]
    permission_classes = [IsAuthenticated, HasPermission]
    module = "activities"
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["school", "activity_category", "activity_status", "season"]
    search_fields = ["name", "description", "sub_category"]
    ordering_fields = ["name", "created_at", "current_participants"]
    ordering = ["name"]

    def get_queryset(self):
        """
        Filter activities based on user's school.
        - Superusers see all activities
        - School staff see their school's activities
        - Others see only active activities they're involved in
        """

        user = self.request.user

        if user.is_superuser:
            return Activity.objects.all()

        # If user has a school (staff)
        school = getattr(self.request, "school", None)
        if school:
            return Activity.objects.filter(school=school)
        if hasattr(user, "staff_profile") and user.staff_profile.school_id:
            return Activity.objects.filter(school=user.staff_profile.school)


        if hasattr(user, "student_profile"):
            return Activity.objects.filter(
                school=user.student_profile.school,
                activity_status=ActivityStatusChoices.ACTIVE,
            )

        return Activity.objects.none()

    @action(detail=False, methods=["get"])
    def statistics(self, request):
        """Get statistics for activities."""
        queryset = self.get_queryset()

        stats = {
            "total_activities": queryset.count(),
            "active_activities": queryset.filter(activity_status=ActivityStatusChoices.ACTIVE).count(),
            "total_participants": queryset.aggregate(total=Sum("current_participants"))[
                "total"
            ]
            or 0,
            "activities_by_category": dict(
                queryset.values("activity_category")
                .annotate(count=Count("id"))
                .values_list("activity_category", "count")
            ),
            "avg_participation_rate": queryset.filter(max_participants__gt=0).aggregate(
                avg_rate=Avg(F("current_participants") * 100.0 / F("max_participants"))
            )["avg_rate"]
            or 0,
        }

        serializer = ActivityStatisticsSerializer(stats)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def participants(self, request, pk=None):
        """Get all participants for a specific activity."""
        activity = self.get_object()
        participants = StudentActivity.objects.filter(activity=activity)

        page = self.paginate_queryset(participants)
        if page is not None:
            serializer = StudentActivitySerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = StudentActivitySerializer(participants, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def competitions(self, request, pk=None):
        """Get all competitions for a specific activity."""
        activity = self.get_object()
        competitions = Competition.objects.filter(activity=activity)

        page = self.paginate_queryset(competitions)
        if page is not None:
            serializer = CompetitionSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = CompetitionSerializer(competitions, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def available_for_student(self, request):
        """Get activities available for a specific student."""
        student_id = request.query_params.get("student_id")

        if not student_id:
            return Response(
                {"error": "student_id parameter is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            student = StudentProfile.objects.get(id=student_id)
        except StudentProfile.DoesNotExist:
            return Response(
                {"error": "Student not found."}, status=status.HTTP_404_NOT_FOUND
            )

        # Get activities from student's school that have space
        available_activities = Activity.objects.filter(
            school=student.school,
            activity_status=ActivityStatusChoices.ACTIVE,
            current_participants__lt=F("max_participants"),
        ).exclude(participants__student=student)

        serializer = ActivitySerializer(available_activities, many=True)
        return Response(serializer.data)


    @extend_schema(
    request=StudentActivitySerializer,
    responses={201: StudentActivitySerializer},
    tags=["Activities"],)
    @action(detail=True, methods=["post"], url_path="enroll-student")
    def enroll_student(self, request, pk=None):
        """Enroll a student in this activity."""
        activity = self.get_object()
        student_id = request.data.get("student_id")
        # role = request.data.get("role", StudentActivityStatusChoices.ACTIVE)
        role = request.data.get("role", ActivityRoleChoices.MEMBER)

        if not student_id:
            return Response(
                {"error": "student_id is required."}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            student = StudentProfile.objects.get(id=student_id)
        except StudentProfile.DoesNotExist:
            return Response(
                {"error": "Student not found."}, status=status.HTTP_404_NOT_FOUND
            )

        # Check if already enrolled
        if StudentActivity.objects.filter(student=student, activity=activity).exists():
            return Response(
                {"error": "Student is already enrolled in this activity."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check activity capacity
        if activity.current_participants >= activity.max_participants:
            return Response(
                {"error": "Activity has reached maximum participants."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = StudentActivitySerializer(
            data={
                "student": student.id,
                "activity": activity.id,
                "role": role,
                "start_date": request.data.get("start_date") or timezone.now().date(),
            }
        )

        serializer.is_valid(raise_exception=True)
        enrollment = serializer.save()
        return Response(
            StudentActivitySerializer(enrollment).data,
            status=status.HTTP_201_CREATED,
        )


class StudentActivityViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing StudentActivity (enrollments).

    Supports:
    - CRUD operations for student enrollments
    - Filtering by student, activity, status
    - Update attendance and performance
    - Generate talent reports
    """

    queryset = StudentActivity.objects.all()
    serializer_class = StudentActivitySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = [
        "student",
        "activity",
        "student_activity_status",
        "role",
        "performance_level",
    ]
    search_fields = [
        "student__admission_number",
        "student__user__username",
        "activity__name",
    ]

    def get_queryset(self):
        """
        Filter student activities based on user permissions.
        """
        user = self.request.user

        if user.is_superuser:
            return StudentActivity.objects.all()

        if hasattr(user, "staff_profile"):
            school = user.staff_profile.school
            return StudentActivity.objects.filter(
                Q(activity__teacher_in_charge=user)
                | Q(activity__assistant_in_charge=user)
                | Q(activity__school=school)
            ).distinct()

        # If user is a student, show only their own activities
        if hasattr(user, "student_profile"):
            student = user.student_profile
            return StudentActivity.objects.filter(student=student)

        return StudentActivity.objects.none()

    @action(detail=True, methods=["patch"])
    def update_attendance(self, request, pk=None):
        """Update attendance rate for a student activity."""
        student_activity = self.get_object()
        attendance_rate = request.data.get("attendance_rate")

        if attendance_rate is None:
            return Response(
                {"error": "attendance_rate is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            attendance_rate = float(attendance_rate)
            if not 0 <= attendance_rate <= 100:
                raise ValueError
        except (ValueError, TypeError):
            return Response(
                {"error": "attendance_rate must be a number between 0 and 100."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        student_activity.attendance_rate = attendance_rate
        student_activity.save()

        serializer = self.get_serializer(student_activity)
        return Response(serializer.data)

    @action(detail=True, methods=["patch"])
    def update_performance(self, request, pk=None):
        """Update performance metrics for a student activity."""
        student_activity = self.get_object()

        if "performance_level" in request.data:
            student_activity.performance_level = request.data["performance_level"]
        if "talent_score" in request.data:
            talent_score = request.data["talent_score"]
            try:
                talent_score = float(talent_score)
                if 0 <= talent_score <= 100:
                    student_activity.talent_score = talent_score
                else:
                    return Response(
                        {"error": "talent_score must be between 0 and 100."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            except (ValueError, TypeError):
                return Response(
                    {"error": "talent_score must be a valid number."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if "potential_level" in request.data:
            student_activity.potential_level = request.data["potential_level"]

        if "career_potential" in request.data:
            student_activity.career_potential = request.data["career_potential"]

        student_activity.save()

        serializer = self.get_serializer(student_activity)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def add_achievement(self, request, pk=None):
        """Add an achievement to student activity."""
        student_activity = self.get_object()
        achievement = request.data.get("achievement")

        if not achievement:
            return Response(
                {"error": "achievement data is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not isinstance(achievement, dict):
            return Response(
                {"error": "achievement must be a JSON object."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Initialize achievements list if empty
        if student_activity.achievements is None:
            student_activity.achievements = []

        # Add achievement
        student_activity.achievements.append(achievement)
        student_activity.save()

        serializer = self.get_serializer(student_activity)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def talent_report(self, request):
        """Generate talent report for students in activities."""
        school_id = request.query_params.get("school_id")
        min_talent_score = request.query_params.get("min_talent_score", 70)

        queryset = self.get_queryset()

        if school_id:
            queryset = queryset.filter(activity__school_id=school_id)

        # Filter by minimum talent score
        try:
            min_talent_score = float(min_talent_score)
            queryset = queryset.filter(talent_score__gte=min_talent_score)
        except (ValueError, TypeError):
            pass

        # Group by student and aggregate data
        from django.db.models import Avg, Count, Max

        talent_data = (
            queryset.values(
                "student__id",
                "student__user__first_name",
                "student__user__last_name",
                "student__admission_number",
            )
            .annotate(
                activities_count=Count("id"),
                talent_score_avg=Avg("talent_score"),
                max_potential_level=Max("potential_level"),
                has_career_potential=Max("career_potential"),
            )
            .filter(talent_score_avg__gte=min_talent_score)
        )

        # Format response
        reports = []
        for data in talent_data:
            # Get top activities for this student
            top_activities = (
                queryset.filter(student_id=data["student__id"])
                .values("activity__name")
                .annotate(score=Avg("talent_score"))
                .order_by("-score")[:3]
            )

            reports.append(
                {
                    "student_id": data["student__id"],
                    "student_name": f"{data['student__user__first_name']} {data['student__user__last_name']}",
                    "admission_number": data["student__admission_number"],
                    "activities_count": data["activities_count"],
                    "talent_score_avg": data["talent_score_avg"],
                    "potential_level": data["max_potential_level"],
                    "career_potential": data["has_career_potential"],
                    "top_activities": list(top_activities),
                }
            )

        serializer = StudentTalentReportSerializer(reports, many=True)
        return Response(serializer.data)


class CompetitionViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing Competitions.

    Supports:
    - CRUD operations for competitions
    - Filtering by activity, competition_level, date range
    - Add participants and results
    """

    queryset = Competition.objects.all()
    serializer_class = CompetitionSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["activity", "competition_level", "date"]
    search_fields = ["name", "venue", "organizer"]
    ordering_fields = ["date", "name"]
    ordering = ["-date"]

    def get_queryset(self):
        """
        Filter competitions based on user permissions.
        """
        user = self.request.user

        if user.is_superuser:
            return Competition.objects.all()

        school = getattr(self.request, "school", None)
        if school:
            return Competition.objects.filter(activity__school=school)
        if hasattr(user, "staff_profile") and user.staff_profile.school_id:
            return Competition.objects.filter(
                activity__school=user.staff_profile.school
            )
        if hasattr(user, "student_profile"):
            return Competition.objects.filter(
                activity__school=user.student_profile.school
            )
        return Competition.objects.none()


    def perform_create(self, serializer):
        """Set the created_by user when creating a competition."""
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=["post"])
    def add_participant(self, request, pk=None):
        """Add a participant to competition."""
        competition = self.get_object()
        student_id = request.data.get("student_id")
        performance = request.data.get("performance", {})

        if not student_id:
            return Response(
                {"error": "student_id is required."}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            student = StudentProfile.objects.get(id=student_id)
        except StudentProfile.DoesNotExist:
            return Response(
                {"error": "Student not found."}, status=status.HTTP_404_NOT_FOUND
            )

        # Check if student participates in the activity
        if not StudentActivity.objects.filter(
            student=student, activity=competition.activity
        ).exists():
            return Response(
                {"error": "Student is not enrolled in this activity."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Initialize participants list if empty
        if competition.participants is None:
            competition.participants = []

        # Check if already a participant
        for participant in competition.participants:
            if participant.get("student_id") == str(student_id):
                return Response(
                    {"error": "Student is already a participant in this competition."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Add participant
        participant_data = {
            "student_id": str(student_id),
            "student_name": student.user.get_full_name(),
            "admission_number": student.admission_number,
            "performance": performance,
            "added_by": str(self.request.user.id),
            "added_at": timezone.now().isoformat(),
        }

        competition.participants.append(participant_data)
        competition.save()

        serializer = self.get_serializer(competition)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def update_results(self, request, pk=None):
        """Update competition results."""
        competition = self.get_object()
        results = request.data.get("results")

        if not results:
            return Response(
                {"error": "results data is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not isinstance(results, dict):
            return Response(
                {"error": "results must be a JSON object."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        competition.results = results
        competition.save()

        serializer = self.get_serializer(competition)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def upcoming(self, request):
        """Get upcoming competitions."""
        today = timezone.now().date()
        queryset = self.get_queryset().filter(date__gte=today).order_by("date")

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def by_school(self, request):
        """Get competitions grouped by school."""
        school_id = request.query_params.get("school_id")

        if school_id:
            competitions = Competition.objects.filter(activity__school_id=school_id)
        else:
            competitions = Competition.objects.all()

        grouped = defaultdict(list)

        for comp in competitions.select_related("activity__school"):
            # school_name = comp.activity.school.name
            school_name = comp.activity.school.school_name
            serializer = self.get_serializer(comp)
            grouped[school_name].append(serializer.data)

        return Response(grouped)
