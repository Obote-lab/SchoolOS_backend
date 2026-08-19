import logging

from django.shortcuts import get_object_or_404
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.api.permissions import HasPermission
from core.choices.staff import StaffAttendanceStatusChoices
from ..models import StaffAttendance, StaffProfile
from .serializers import (
    StaffAttendanceCreateSerializer,
    StaffAttendanceListSerializer,
    StaffProfileCreateSerializer,
    StaffProfileDetailSerializer,
    StaffProfileListSerializer,
    StaffProfileUpdateSerializer,
    StaffDeactivateSerializer,

)

logger = logging.getLogger(__name__)



from drf_spectacular.utils import extend_schema, extend_schema_view
from drf_spectacular.types import OpenApiTypes

@extend_schema_view(
    list=extend_schema(summary="List staff", responses={200: StaffProfileListSerializer(many=True)}, tags=["Staff"]),
    retrieve=extend_schema(responses={200: StaffProfileDetailSerializer}, tags=["Staff"]),
    create=extend_schema(request=StaffProfileCreateSerializer, responses={201: StaffProfileDetailSerializer}, tags=["Staff"]),
    update=extend_schema(request=StaffProfileUpdateSerializer, responses={200: StaffProfileDetailSerializer}, tags=["Staff"]),
    partial_update=extend_schema(request=StaffProfileUpdateSerializer, responses={200: StaffProfileDetailSerializer}, tags=["Staff"]),
    destroy=extend_schema(tags=["Staff"]),
)
class StaffProfileViewSet(viewsets.ModelViewSet):
    """
    Manage staff profiles.
    - Staff can view their own profile
    - School admins can manage all staff in their school
    """

    module = "staff"
    queryset = StaffProfile.objects.select_related("user", "school", "department")
    permission_classes = [IsAuthenticated, HasPermission]

    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["staff_type", "employment_type", "department", "is_active"]
    search_fields = [
        "staff_id",
        "user__first_name",
        "user__last_name",
        "user__phone",
        "tsc_number",
        "job_title",
    ]
    ordering_fields = ["staff_id", "date_employed", "job_title"]
    ordering = ["staff_id"]

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            self.required_action = "read"
        elif self.action == "create":
            self.required_action = "create"
        elif self.action in ["update", "partial_update", "deactivate", "activate"]:
            self.required_action = "update"
        elif self.action == "destroy":
            self.required_action = "delete"
        else:
            self.required_action = "read"
        return super().get_permissions()

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_superuser:
            return qs

        school = getattr(self.request, "school", None) or getattr(user, "school", None)

        # Elevated school roles see whole school roster
        elevated = user.user_roles.filter(
            is_active=True,
            role__name__in=[
                "Principal", "Deputy Principal", "Administrator",
                "Head of Department", "HR", "System Root",
            ],
        ).exists()
        if elevated and school:
            return qs.filter(school=school)

        if hasattr(user, "staff_profile"):
            return qs.filter(user=user)

        if school:
            return qs.filter(school=school)

        return qs.none()

    def get_serializer_class(self):
        if self.action == "create":
            return StaffProfileCreateSerializer
        if self.action in ["update", "partial_update"]:
            return StaffProfileUpdateSerializer
        if self.action == "list":
            return StaffProfileListSerializer
        return StaffProfileDetailSerializer


    @extend_schema(
    summary="Deactivate staff",
    request=StaffDeactivateSerializer,  # or OpenApiTypes.OBJECT
    responses={200: OpenApiTypes.OBJECT},
    tags=["Staff"],
    )
    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        staff = self.get_object()
        exit_date = request.data.get("exit_date")
        exit_reason = request.data.get("exit_reason", "")

        staff.deactivate(exit_date=exit_date, reason=exit_reason)

        return Response({
            "status": "deactivated",
            "message": f"Staff {staff.staff_id} has been deactivated.",
            "exit_date": staff.exit_date,
        })

    @extend_schema(summary="Activate staff member")
    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        staff = self.get_object()
        staff.activate()

        return Response({
            "status": "activated",
            "message": f"Staff {staff.staff_id} has been activated.",
        })



@extend_schema()
class StaffAttendanceViewSet(viewsets.ModelViewSet):
    """
    Manage staff attendance records.
    """

    module = "staff"
    queryset = StaffAttendance.objects.select_related(
        "staff__user", "recorded_by"
    )
    permission_classes = [IsAuthenticated, HasPermission]

    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["staff", "status", "date"]
    search_fields = [
        "staff__staff_id",
        "staff__user__first_name",
        "staff__user__last_name",
        "notes",
    ]
    ordering_fields = ["date", "status"]
    ordering = ["-date"]

    def get_permissions(self):
        if self.action in ["list", "retrieve", "clock_in", "clock_out"]:
            self.required_action = "read"
        elif self.action == "create":
            self.required_action = "create"
        elif self.action in ["update", "partial_update"]:
            self.required_action = "update"
        elif self.action == "destroy":
            self.required_action = "delete"
        else:
            self.required_action = "read"
        return super().get_permissions()

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user

        if user.is_superuser:
            return qs

        # Staff see only their own attendance
        if hasattr(user, "staff_profile"):
            return qs.filter(staff__user=user)

        school = getattr(self.request, "school", None) or user.school
        if school:
            return qs.filter(staff__school=school)

        return qs.none()

    def get_serializer_class(self):
        if self.action == "create":
            return StaffAttendanceCreateSerializer
        return StaffAttendanceListSerializer

    def perform_create(self, serializer):
        serializer.save(recorded_by=self.request.user)

    @extend_schema(summary="Clock in for today")
    @action(detail=False, methods=["post"], url_path="clock-in")
    def clock_in(self, request):
        staff = get_object_or_404(StaffProfile, user=request.user, is_active=True)
        today = timezone.now().date()

        attendance, created = StaffAttendance.objects.get_or_create(
            staff=staff,
            date=today,
            defaults={
                "status": StaffAttendanceStatusChoices.PRESENT,
                "recorded_by": request.user,
            },
        )

        if not created and attendance.status == StaffAttendanceStatusChoices.ABSENT:
            attendance.status = StaffAttendanceStatusChoices.PRESENT
            attendance.recorded_by = request.user
            attendance.save(update_fields=["status", "recorded_by"])

        return Response(StaffAttendanceListSerializer(attendance).data)

    @extend_schema(summary="Clock out for today")
    @action(detail=False, methods=["post"], url_path="clock-out")
    def clock_out(self, request):
        staff = get_object_or_404(StaffProfile, user=request.user, is_active=True)
        today = timezone.now().date()

        try:
            attendance = StaffAttendance.objects.get(staff=staff, date=today)
        except StaffAttendance.DoesNotExist:
            return Response(
                {"detail": "No attendance record found for today."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if attendance.status not in [
            StaffAttendanceStatusChoices.PRESENT,
            StaffAttendanceStatusChoices.LATE,
        ]:
            return Response(
                {"detail": "Cannot clock out — no active attendance today."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        attendance.recorded_by = request.user
        attendance.save(update_fields=["recorded_by"])

        return Response(StaffAttendanceListSerializer(attendance).data)