# staff/api/viewsets.py
import logging
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend

from accounts.api.permissions import HasPermission  
from .serializers import (
    StaffProfileListSerializer,
    StaffProfileDetailSerializer,
    StaffProfileCreateSerializer,
    StaffProfileUpdateSerializer,
    StaffAttendanceListSerializer,
    ClockInSerializer,
    ClockOutSerializer,
    StaffAttendanceCreateSerializer
)
from ..models import StaffProfile, StaffAttendance

logger = logging.getLogger(__name__)



#   Permissions (reused)
class IsSchoolAdminOrSelf(IsAuthenticated, HasPermission):
    """Staff can see own profile; admins see all in school"""
    required_action = "manage_staff"

    def has_object_permission(self, request, view, obj):
        if isinstance(obj, StaffProfile):
            return obj.user == request.user or request.user.school == obj.school
        return False



#   StaffProfile ViewSet
@extend_schema(tags=["Staff Profiles"])
class StaffProfileViewSet(viewsets.ModelViewSet):
    """
    Manage staff profiles (CRUD + status actions).
    Admins manage all in school; staff view own profile.
    """
    queryset = StaffProfile.objects.select_related(
        "user", "school", "department"
    ).prefetch_related("subjects_taught", "classes_assigned")
    permission_classes = [IsAuthenticated]

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["staff_type", "employment_type", "department", "is_active"]
    search_fields = ["staff_id", "user__first_name", "user__last_name", "user__phone", "tsc_number"]
    ordering_fields = ["staff_id", "date_employed", "job_title"]
    ordering = ["staff_id"]

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [IsAuthenticated()]
        if self.action in ["create", "update", "partial_update", "destroy", "deactivate", "activate"]:
            return [IsSchoolAdminOrSelf()]
        return super().get_permissions()

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user

        # Staff see only own profile
        if hasattr(user, "staff_profile"):
            return qs.filter(user=user)

        # Admins see all in their school
        if user.school:
            return qs.filter(school=user.school)

        return qs.none()

    def get_serializer_class(self):
        if self.action == "create":
            return StaffProfileCreateSerializer
        if self.action in ["update", "partial_update"]:
            return StaffProfileUpdateSerializer
        if self.action == "list":
            return StaffProfileListSerializer
        return StaffProfileDetailSerializer

    @extend_schema(summary="Deactivate staff", request=None, responses={200: dict})
    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        """Mark staff as inactive (syncs user.is_active)"""
        staff = self.get_object()
        exit_date = request.data.get("exit_date")
        exit_reason = request.data.get("exit_reason", "")

        staff.deactivate(exit_date=exit_date, reason=exit_reason)

        return Response({
            "status": "deactivated",
            "message": f"Staff {staff.staff_id} deactivated",
            "exit_date": staff.exit_date,
        })

    @extend_schema(summary="Activate staff", request=None, responses={200: dict})
    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        """Reactivate staff (syncs user.is_active)"""
        staff = self.get_object()
        staff.activate()

        return Response({
            "status": "activated",
            "message": f"Staff {staff.staff_id} activated",
        })



#   StaffAttendance ViewSet
@extend_schema(tags=["Staff Attendance"])
class StaffAttendanceViewSet(viewsets.ModelViewSet):
    """
    Manage staff attendance records (CRUD + clock actions).
    Staff can clock in/out; admins view/manage school-wide.
    """
    queryset = StaffAttendance.objects.select_related("staff__user", "recorded_by")
    permission_classes = [IsAuthenticated]

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["staff", "status", "date"]
    search_fields = ["staff__staff_id", "staff__user__first_name", "staff__user__last_name", "notes"]
    ordering_fields = ["date", "status"]
    ordering = ["-date"]

    def get_permissions(self):
        if self.action in ["clock_in", "clock_out"]:
            return [IsAuthenticated()]
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsSchoolAdminOrSelf()]
        return [IsAuthenticated()]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user

        # Staff see only own attendance
        if hasattr(user, "staff_profile"):
            return qs.filter(staff__user=user)

        # Admins see all in school
        if user.school:
            return qs.filter(staff__school=user.school)

        return qs.none()

    def get_serializer_class(self):
        if self.action == "create":
            return StaffAttendanceCreateSerializer
        return StaffAttendanceListSerializer

    def perform_create(self, serializer):
        """Auto-set recorded_by"""
        serializer.save(recorded_by=self.request.user)

    @extend_schema(
        summary="Clock in for today",
        request=None,
        responses={200: StaffAttendanceListSerializer}
    )
    @action(detail=False, methods=["post"], url_path="clock-in")
    def clock_in(self, request):
        """Clock in for the current day (creates/updates today's record)"""
        staff = get_object_or_404(StaffProfile, user=request.user, is_active=True)
        today = timezone.now().date()

        attendance, created = StaffAttendance.objects.get_or_create(
            staff=staff,
            date=today,
            defaults={
                "status": StaffAttendance.StatusChoices.PRESENT,
                "recorded_by": request.user,
            }
        )

        if not created:
            if attendance.status == StaffAttendance.StatusChoices.ABSENT:
                attendance.status = StaffAttendance.StatusChoices.PRESENT
                attendance.recorded_by = request.user
                attendance.save()
            else:
                return Response(
                    {"detail": "Already clocked in or recorded today"},
                    status=status.HTTP_400_BAD_REQUEST
                )

        return Response(StaffAttendanceListSerializer(attendance).data)

    @extend_schema(
        summary="Clock out for today",
        request=None,
        responses={200: StaffAttendanceListSerializer}
    )
    @action(detail=False, methods=["post"], url_path="clock-out")
    def clock_out(self, request):
        """Clock out for the current day (updates today's record)"""
        staff = get_object_or_404(StaffProfile, user=request.user, is_active=True)
        today = timezone.now().date()

        try:
            attendance = StaffAttendance.objects.get(staff=staff, date=today)
            if attendance.status not in [StaffAttendance.StatusChoices.PRESENT, StaffAttendance.StatusChoices.LATE]:
                return Response(
                    {"detail": "Cannot clock out — no active attendance today"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            attendance.status = StaffAttendance.StatusChoices.PRESENT 
            attendance.recorded_by = request.user
            attendance.save()

            return Response(StaffAttendanceListSerializer(attendance).data)

        except StaffAttendance.DoesNotExist:
            return Response(
                {"detail": "No attendance record found for today"},
                status=status.HTTP_400_BAD_REQUEST
            )

    @extend_schema(
        summary="Get today's attendance (school-wide)",
        responses={200: StaffAttendanceListSerializer(many=True)}
    )
    @action(detail=False, methods=["get"], url_path="today")
    def today(self, request):
        """List all attendance records for today (admin only)"""
        if not request.user.school:
            return Response({"detail": "Not authorized"}, status=403)

        today = timezone.now().date()
        qs = self.get_queryset().filter(date=today)

        serializer = StaffAttendanceListSerializer(qs, many=True)
        return Response(serializer.data)