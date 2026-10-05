from django.db.models import Count, Q, Avg
from django.shortcuts import get_object_or_404
from datetime import timedelta
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from accounts.api.permissions import HasPermission
from drf_spectacular.utils import extend_schema
from ..models import SystemAuditEvent, ComplianceCheck, DataExportLog, SystemHealth
from .serializers import (
    ComplianceCheckSerializer,SystemAuditEventSerializer,
    ComplianceStatsSerializer,AuditSummarySerializer,
    DataExportLogSerializer, SystemAuditEventSerializer,SystemHealthSerializer,
)
from core.choices.compliance import (
    HealthStatusChoices,
    ComplianceStatusChoices,
)

@extend_schema(parameters=[])
class SystemAuditEventViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing System Audit Events (read-only).

    Supports:
    - View audit events with filtering
    - Get audit summary statistics
    - Search by user, action, model
    """

    serializer_class = SystemAuditEventSerializer
    permission_classes = [permissions.IsAuthenticated, HasPermission]
    module = "compliance"
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter,]

    #Only include fields that exist on SystemAuditEvent
    filterset_fields = ["action_type", "model_name", "user", "school"]
    search_fields = ["user__login_id", "model_name", "user_ip", "reason"]
    ordering_fields = ["timestamp", "action_type"]
    ordering = ["-timestamp"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return SystemAuditEvent.objects.none()

        user = self.request.user

        if user.is_superuser:
            return SystemAuditEvent.objects.all()

        queryset = SystemAuditEvent.objects.filter(user=user)

        # if hasattr(user, "staff_profile"):
        #     school = user.staff_profile.school
        #     queryset = queryset | SystemAuditEvent.objects.filter(school=school)
        school = getattr(self.request, "school", None)
        if user.is_superuser:
            return SystemAuditEvent.objects.all()
        if school:
            return SystemAuditEvent.objects.filter(school=school)
        if hasattr(user, "staff_profile") and user.staff_profile.school_id:
            return SystemAuditEvent.objects.filter(school=user.staff_profile.school)
        return SystemAuditEvent.objects.filter(user=user)

        return queryset.distinct()

    @action(detail=False, methods=["get"])
    def summary(self, request):
        """Get audit log summary statistics."""
        queryset = self.get_queryset()
        today = timezone.now().date()

        summary = {
            "total_actions": queryset.count(),
            "today_actions": queryset.filter(timestamp__date=today).count(),
            "by_action_type": dict(queryset.values("action_type").annotate(count=Count("id")).values_list("action_type", "count") ),
            "by_user": dict(queryset.values("user__login_id").annotate(count=Count("id")).order_by("-count").values_list("user__login_id", "count")[:10]),
            "by_model": dict(queryset.values("model_name").annotate(count=Count("id")).values_list("model_name", "count")[:10]),
        }

        serializer = AuditSummarySerializer(summary)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def my_activity(self, request):
        """Get current user's activity logs."""
        queryset = self.get_queryset().filter(user=request.user)

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class DataExportLogViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing Data Exports.

    Supports:
    - Request data exports
    - View export history
    - Approve/deny export requests
    - Track download access
    """

    serializer_class = DataExportLogSerializer
    # permission_classes = [permissions.IsAuthenticated]
    permission_classes = [permissions.IsAuthenticated, HasPermission]
    module = "compliance"
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["export_type", "format", "exported_by"]
    search_fields = ["purpose", "exported_by__login_id", "approved_by__login_id"]

    def get_queryset(self):
        """
        Users can see:
        - Exports they created
        - Exports they approved
        - All exports if superuser or admin
        """
        if getattr(self, "swagger_fake_view", False):
            return DataExportLog.objects.none()
        user = self.request.user

        if user.is_superuser:
            return DataExportLog.objects.all()
        queryset = DataExportLog.objects.filter(exported_by=user)
        # Add exports user approved
        queryset = queryset | DataExportLog.objects.filter(approved_by=user)

        return queryset.distinct()

    def perform_create(self, serializer):
        """Set exported_by to current user."""
        serializer.save(exported_by=self.request.user)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        """Approve an export request."""
        export = self.get_object()

        if not export.approval_required:
            return Response({"detail": "This export does not require approval."},status=status.HTTP_400_BAD_REQUEST,)

        if export.approved_by:
            return Response({"detail": "Export is already approved."},status=status.HTTP_400_BAD_REQUEST,)

        export.approved_by = request.user
        export.save()

        serializer = self.get_serializer(export)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def record_download(self, request, pk=None):
        """Record when someone downloads an export."""
        export = self.get_object()

        download_record = {
            "user_id": str(request.user.id),
            "user_name": request.user.get_full_name(),
            "timestamp": timezone.now().isoformat(),
            "ip_address": request.META.get("REMOTE_ADDR", ""),
        }

        if export.access_log is None:
            export.access_log = []

        export.access_log.append(download_record)
        export.save()

        return Response({"detail": "Download recorded successfully."})


class SystemHealthViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing System Health monitoring.

    Supports:
    - Record system health metrics
    - View system health history
    - Get current system status
    - Monitor storage and performance
    """

    serializer_class = SystemHealthSerializer
    permission_classes = [permissions.IsAuthenticated]
    module = "compliance"
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["school", "backup_status", "sync_status"]
    ordering_fields = ["check_timestamp", "performance_score"]
    ordering = ["-check_timestamp"]

    def get_queryset(self):
        """
        Users can see:
        - System health for their school
        - All records if superuser
        """
        if getattr(self, "swagger_fake_view", False):
            return SystemHealth.objects.none()
        user = self.request.user

        if user.is_superuser:
            return SystemHealth.objects.all()

        if hasattr(user, "staff_profile"):
            school = user.staff_profile.school
            return SystemHealth.objects.filter(school=school)

        if hasattr(user, "student_profile"):
            school = user.student_profile.school
            return SystemHealth.objects.filter(school=school)

        return SystemHealth.objects.none()

    @action(detail=False, methods=["get"])
    def current(self, request):
        """Get current system health status."""
        user = self.request.user

        if hasattr(user, "staff_profile"):
            school = user.staff_profile.school
        elif hasattr(user, "student_profile"):
            school = user.student_profile.school
        else:
            return Response({"error": "User is not associated with a school."},status=status.HTTP_400_BAD_REQUEST,)

        # Get latest health record for the school
        health = (SystemHealth.objects.filter(school=school).order_by("-check_timestamp").first())

        if health:
            serializer = self.get_serializer(health)
            return Response(serializer.data)

        # Create a default record if none exists
        # default_health = SystemHealth.objects.create(school=school, checked_by="system")
        # serializer = self.get_serializer(default_health)
        # return Response(serializer.data)
        if not health:
            return Response({"detail": "No health record yet."}, status=404)

    @action(detail=False, methods=["get"])
    def issues(self, request):
        """Get system health issues."""
        queryset = (
            self.get_queryset()
            .filter(
                # Q(issues_detected__len__gt=0)
                ~Q(issues_detected=[]) & ~Q(issues_detected=None)
                | Q(performance_score__lt=70)
                | Q(backup_status=HealthStatusChoices.FAILED)
            )
            .order_by("-check_timestamp")
        )

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class ComplianceCheckViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing Compliance Checks.

    Supports:
    - Create and track compliance checks
    - Assign responsible persons
    - Verify compliance
    - Schedule next checks
    - Generate compliance reports
    """

    serializer_class = ComplianceCheckSerializer
    permission_classes = [permissions.IsAuthenticated]
    module = "compliance"
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = [
        "school",
        "check_type",
        "system_health_status",
        "responsible_person",
    ]
    search_fields = ["action_plan", "requirements"]

    def get_queryset(self):
        """
        Users can see:
        - Compliance checks for their school
        - Checks they are responsible for
        - All checks if superuser
        """
        if getattr(self, "swagger_fake_view", False):
            return ComplianceCheck.objects.none()
        user = self.request.user

        if user.is_superuser:
            return ComplianceCheck.objects.all()

        queryset = ComplianceCheck.objects.filter(responsible_person=user)

        # Add checks from user's school
        if hasattr(user, "staff_profile"):
            school = user.staff_profile.school
            queryset = queryset | ComplianceCheck.objects.filter(school=school)
        elif hasattr(user, "student_profile"):
            school = user.student_profile.school
            queryset = queryset | ComplianceCheck.objects.filter(school=school)

        return queryset.distinct()

    def perform_create(self, serializer):
        """Set responsible person if not provided."""
        if "responsible_person" not in serializer.validated_data:
            serializer.validated_data["responsible_person"] = self.request.user

        serializer.save()

    @action(detail=True, methods=["post"])
    def verify(self, request, pk=None):
        """Verify a compliance check."""
        check = self.get_object()

        if check.verified_by:
            return Response({"detail": "Check is already verified."},status=status.HTTP_400_BAD_REQUEST,)

        check.verified_by = request.user
        check.verification_date = timezone.now().date()
        check.save()

        serializer = self.get_serializer(check)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def add_issue(self, request, pk=None):
        """Add an issue to compliance check."""
        check = self.get_object()
        issue = request.data.get("issue")

        if not issue:
            return Response({"error": "issue is required."}, status=status.HTTP_400_BAD_REQUEST)

        if check.issues_found is None:
            check.issues_found = []

        check.issues_found.append(issue)
        check.save()

        serializer = self.get_serializer(check)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def overdue(self, request):
        """Get overdue compliance checks."""
        today = timezone.now().date()
        queryset = (
            self.get_queryset()
            .filter(
                Q(next_check_date__lt=today)
                | Q(
                    deadline__lt=today,
                    system_health_status=ComplianceStatusChoices.NON_COMPLIANT,
                )
            )
            .order_by("next_check_date", "deadline")
        )

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def statistics(self, request):
        """Get compliance statistics."""
        queryset = self.get_queryset()

        stats = {
            "total_checks": queryset.count(),
            "compliant": queryset.filter(system_health_status=ComplianceStatusChoices.COMPLIANT).count(),
            "non_compliant": queryset.filter(system_health_status=ComplianceStatusChoices.NON_COMPLIANT).count(),
            "by_check_type": dict(queryset.values("check_type").annotate(count=Count("id")).values_list("check_type", "count")),
            "avg_score": queryset.aggregate(avg=Avg("score"))["avg"] or 0,
        }

        serializer = ComplianceStatsSerializer(stats)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def upcoming(self, request):
        """Get upcoming compliance checks."""
        today = timezone.now().date()
        next_week = today + timedelta(days=7)

        queryset = (self.get_queryset().filter(next_check_date__range=[today, next_week]).order_by("next_check_date"))

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
