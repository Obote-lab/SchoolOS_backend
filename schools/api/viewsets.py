from django.contrib.gis.geos import Point
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import generics, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from accounts.api.permissions import HasPermission
from accounts.models import UserRole
from ..models import AcademicYear, ClassRoom, Department, School, Term
from ..services.onboarding import SchoolOnboardingService
from core.choices.schools import OnboardingStatusChoices
from .serializers import (
    AcademicYearSerializer,
    AcademicYearSimpleSerializer,
    ClassRoomSerializer,
    ClassRoomSimpleSerializer,
    DepartmentSerializer,
    RegionalAdminCreateSchoolSerializer,
    SchoolCreateSerializer,
    SchoolSearchSerializer,
    SchoolSerializer,
    SchoolSimpleSerializer,
    SchoolUpdateSerializer,
    SystemBulkOnboardSerializer,
    SystemSchoolOnboardSerializer,
    TermSerializer,
)


# SCHOOL VIEWSET
@extend_schema_view(
    list=extend_schema(summary="List schools"),
    retrieve=extend_schema(summary="Get school", responses={200: SchoolSerializer}),
    create=extend_schema(
        summary="Create school + principal",
        request=SchoolCreateSerializer,
        responses={201: SchoolSerializer},
    ),
    update=extend_schema(request=SchoolUpdateSerializer),
    partial_update=extend_schema(request=SchoolUpdateSerializer),
    destroy=extend_schema(summary="Delete school"),
)
class SchoolViewSet(viewsets.ModelViewSet):
    """
    Main endpoint for school CRUD and onboarding operations.
    Permissions enforced via HasPermission + PermissionMatrix.
    """

    module = "schools"
    queryset = School.objects.all().order_by("school_name")
    permission_classes = [permissions.IsAuthenticated, HasPermission]

    def get_serializer_class(self):
        if self.action == "create":
            return SchoolCreateSerializer
        if self.action in ["update", "partial_update"]:
            return SchoolUpdateSerializer
        if self.action in ["list", "search"]:
            return SchoolSimpleSerializer
        return SchoolSerializer

    def get_permissions(self):
        if self.action == "create":
            self.required_action = "create"
        elif self.action in ["update", "partial_update"]:
            self.required_action = "update"
        elif self.action == "destroy":
            self.required_action = "delete"
        elif self.action in ["activate", "deactivate"]:
            self.required_action = "manage_status"
        elif self.action in ["setup_structures", "complete_onboarding"]:
            self.required_action = "manage_onboarding"
        elif self.action == "update_enrollment":
            self.required_action = "update_enrollment"
        else:
            self.required_action = "read"
        return super().get_permissions()

    def get_queryset(self):
        qs = School.objects.all().select_related( "principal", "deputy_academic", "deputy_admin", "created_by" ).order_by("school_name")
        user = self.request.user
        if user.is_superuser:
            return qs

        school = getattr(self.request, "school", None)
        if school is not None:
            return qs.filter(pk=school.pk)

        has_elevated = user.user_roles.filter(is_active=True,role__name__in=["Regional Admin", "County Admin", "System Root"],).exists()
        if has_elevated:
            return qs
        # School-level staff: only schools from their roles
        return qs.filter(Q(user_roles__user=user, user_roles__is_active=True)| Q(principal=user)).distinct()

    def perform_create(self, serializer):
        serializer.save()


    # ── Status actions
    @extend_schema(responses={200: SchoolSerializer})
    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        school = self.get_object()
        school.is_active = True
        school.save(update_fields=["is_active"])
        return Response(
            {
                "message": f"School {school.school_name} activated",
                "school": SchoolSerializer(school).data,
            }
        )

    @extend_schema(responses={200: SchoolSerializer})
    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        school = self.get_object()
        school.is_active = False
        school.save(update_fields=["is_active"])
        return Response(
            {
                "message": f"School {school.school_name} deactivated",
                "school": SchoolSerializer(school).data,
            }
        )

    # ── Onboarding actions
    @extend_schema(responses={200: OpenApiTypes.OBJECT})
    @action(detail=True, methods=["get"])
    def onboarding_status(self, request, pk=None):
        school = self.get_object()
        checklist = {}
        return Response({
            "school": SchoolSerializer(school).data,
            "checklist": checklist,
        })


    @extend_schema(responses={200: OpenApiTypes.OBJECT, 400: OpenApiTypes.OBJECT})
    @action(detail=True, methods=["post"])
    def setup_structures(self, request, pk=None):
        school = self.get_object()
        if school.onboarding_status not in [
            OnboardingStatusChoices.PENDING,
            OnboardingStatusChoices.PRINCIPAL_CREATED,
        ]:
            return Response(
                {"error": "Structures can only be set up in early onboarding stages"},
                status=400,
            )

        try:
            result = SchoolOnboardingService.setup_basic_structures(school, request.user)
            return Response({
                "message": "Basic structures (academic year, terms, classrooms) created",
                "result": result,
                "school": SchoolSerializer(school).data,
            })
        except ValueError as e:
            return Response({"error": str(e)}, status=400)


    @extend_schema(responses={200: SchoolSerializer, 400: OpenApiTypes.OBJECT})
    @action(detail=True, methods=["post"])
    def complete_onboarding(self, request, pk=None):
        school = self.get_object()
        try:
            SchoolOnboardingService.complete_onboarding(school, request.user)
            return Response(
                {
                    "message": "School onboarding marked as complete",
                    "school": SchoolSerializer(school).data,
                }
            )
        except ValueError as e:
            return Response({"error": str(e)}, status=400)

    # ── Enrollment management
    @extend_schema(
    request={"application/json": {"type": "object", "properties": {"change": {"type": "integer"}}}},
    responses={200: SchoolSerializer, 400: OpenApiTypes.OBJECT},
    )
    @action(detail=True, methods=["post"])
    def update_enrollment(self, request, pk=None):
        school = self.get_object()
        change = request.data.get("change")
        if change is None:
            return Response(
                {"error": "Field 'change' is required (integer)"}, status=400
            )

        try:
            change = int(change)
            school.update_enrollment(change)
            return Response(
                {
                    "message": f"Enrollment updated by {change}",
                    "current_enrollment": school.current_enrollment,
                    "school": SchoolSerializer(school).data,
                }
            )
        except (ValueError, ValidationError) as e:
            return Response({"error": str(e)}, status=400)

    #  Search & statistics
    @extend_schema(
    parameters=[
        OpenApiParameter("q", str, required=False),
        OpenApiParameter("county", str, required=False),
        OpenApiParameter("school_type", str, required=False),
        OpenApiParameter("category", str, required=False),
    ],
    responses={200: SchoolSimpleSerializer(many=True)},)
    @action(detail=False, methods=["get"])
    def search(self, request):
        query = request.query_params.get("q", "").strip()
        county = request.query_params.get("county")
        school_type = request.query_params.get("school_type")
        category = request.query_params.get("category")

        qs = School.objects.filter(is_active=True)

        if query:
            qs = qs.filter(
                Q(school_name__icontains=query)
                | Q(school_code__icontains=query)
                | Q(county__icontains=query)
                | Q(sub_county__icontains=query)
            )
        if county:
            qs = qs.filter(county__icontains=county)
        if school_type:
            qs = qs.filter(school_type=school_type)
        if category:
            qs = qs.filter(school_category=category)

        page = self.paginate_queryset(qs)
        if page is not None:
            return self.get_paginated_response(
                SchoolSimpleSerializer(page, many=True).data
            )

        return Response(SchoolSimpleSerializer(qs, many=True).data)

    @extend_schema(responses={200: OpenApiTypes.OBJECT})
    @action(detail=False, methods=["get"])
    def statistics(self, request):
        qs = School.objects.all()
        total_capacity = qs.aggregate(total=Sum("capacity"))["total"] or 0
        total_enrollment = qs.aggregate(total=Sum("current_enrollment"))["total"] or 0

        return Response(
            {
                "total_schools": qs.count(),
                "active_schools": qs.filter(is_active=True).count(),
                "total_capacity": total_capacity,
                "total_enrollment": total_enrollment,
                "total_vacancies": total_capacity - total_enrollment,
                "overall_enrollment_rate": round(
                    (
                        (total_enrollment / total_capacity * 100)
                        if total_capacity > 0
                        else 0
                    ),
                    1,
                ),
                "by_type": list(qs.values("school_type").annotate(count=Count("id"))),
                "by_category": list(
                    qs.values("school_category").annotate(count=Count("id"))
                ),
                "by_county_top10": list(
                    qs.values("county")
                    .annotate(count=Count("id"), enrollment=Sum("current_enrollment"))
                    .order_by("-count")[:10]
                ),
            }
        )


# ACADEMIC YEAR VIEWSET
class AcademicYearViewSet(viewsets.ModelViewSet):
    module = "academic_years"
    queryset = AcademicYear.objects.all().order_by("-start_date")
    serializer_class = AcademicYearSerializer
    permission_classes = [permissions.IsAuthenticated, HasPermission]

    def get_serializer_class(self):
        if self.action == "list":
            return AcademicYearSimpleSerializer
        return AcademicYearSerializer

    def get_permissions(self):
        if self.action in [
            "create",
            "update",
            "partial_update",
            "destroy",
            "set_current",
        ]:
            self.required_action = "manage"
        else:
            self.required_action = "read"
        return super().get_permissions()

    def get_queryset(self):
        qs = super().get_queryset().select_related("school")
        school_id = self.request.query_params.get("school")
        if school_id:
            return qs.filter(school_id=school_id)
        school = getattr(self.request, "school", None)
        if school is not None:
            return qs.filter(school_id=school.pk)
        return qs

    @action(detail=True, methods=["post"])
    def set_current(self, request, pk=None):
        year = self.get_object()
        AcademicYear.objects.filter(school=year.school).exclude(pk=year.pk).update(
            is_current=False
        )
        year.is_current = True
        year.save(update_fields=["is_current"])
        return Response({"message": f"{year.year} is now the current academic year"})


# TERM VIEWSET
class TermViewSet(viewsets.ModelViewSet):
    module = "terms"
    queryset = Term.objects.all().order_by("academic_year", "sequence")
    serializer_class = TermSerializer
    permission_classes = [permissions.IsAuthenticated, HasPermission]

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            self.required_action = "manage"
        else:
            self.required_action = "read"
        return super().get_permissions()

    def get_queryset(self):
        qs = super().get_queryset()
        academic_year_id = self.request.query_params.get("academic_year")
        school_id = self.request.query_params.get("school")
        if academic_year_id:
            qs = qs.filter(academic_year_id=academic_year_id)
        if school_id:
            qs = qs.filter(academic_year__school_id=school_id)
        return qs


# CLASSROOM VIEWSET
class ClassRoomViewSet(viewsets.ModelViewSet):
    module = "classrooms"
    queryset = ClassRoom.objects.all().order_by("school", "level", "stream")
    permission_classes = [permissions.IsAuthenticated, HasPermission]

    def get_serializer_class(self):
        if self.action in ["list", "by_school"]:
            return ClassRoomSimpleSerializer
        return ClassRoomSerializer

    def get_permissions(self):
        if self.action in [
            "create",
            "update",
            "partial_update",
            "destroy",
            "update_student_count",
        ]:
            self.required_action = "manage"
        else:
            self.required_action = "read"
        return super().get_permissions()

    def get_queryset(self):
        qs = super().get_queryset()
        school_param = self.request.query_params.get("school")
        if school_param:
            return qs.filter(school_id=school_param)

        school = getattr(self.request, "school", None)
        if school is not None:
            return qs.filter(school_id=school.pk)  # use .pk
        return qs

    @action(detail=False, methods=["get"])
    def by_school(self, request):
        school_id = request.query_params.get("school") or getattr(
            request, "school", None
        )
        if not school_id:
            return Response(
                {"error": "school id required (query param or context)"}, status=400
            )

        qs = self.get_queryset().filter(school_id=school_id)
        grouped = {}
        for cr in qs:
            grouped.setdefault(cr.level, []).append(ClassRoomSimpleSerializer(cr).data)
        return Response(grouped)

    @action(detail=True, methods=["post"])
    def update_student_count(self, request, pk=None):
        classroom = self.get_object()
        change = request.data.get("change")
        if change is None:
            return Response(
                {"error": "Field 'change' is required (integer)"}, status=400
            )

        try:
            change = int(change)
            classroom.update_student_count(change)
            return Response(
                {
                    "message": f"Student count updated by {change}",
                    "current_enrollment": classroom.current_enrollment,
                    "classroom": ClassRoomSerializer(classroom).data,
                }
            )
        except (ValueError, ValidationError) as e:
            return Response({"error": str(e)}, status=400)


# DEPARTMENT VIEWSET
class DepartmentViewSet(viewsets.ModelViewSet):
    module = "departments"
    queryset = Department.objects.all().order_by("school", "department_name")
    serializer_class = DepartmentSerializer
    permission_classes = [permissions.IsAuthenticated, HasPermission]

    def get_permissions(self):
        if self.action in [
            "create",
            "update",
            "partial_update",
            "destroy",
            "update_budget",
            "update_member_count",
        ]:
            self.required_action = "manage"
        else:
            self.required_action = "read"
        return super().get_permissions()

    def get_queryset(self):
        qs = super().get_queryset()
        school_param = self.request.query_params.get("school")
        if school_param:
            return qs.filter(school_id=school_param)

        school = getattr(request, "school", None)
        school_id = request.query_params.get("school") or (school.pk if school else None)
        if school is not None:
            return qs.filter(school_id=school.pk)  # use .pk
        return qs

    @action(detail=True, methods=["post"])
    def update_budget(self, request, pk=None):
        dept = self.get_object()
        amount = request.data.get("amount")
        if amount is None:
            return Response({"error": "Field 'amount' is required"}, status=400)

        try:
            dept.budget = float(amount)
            dept.save(update_fields=["budget"])
            return Response(
                {
                    "message": f"Budget updated to {amount}",
                    "department": DepartmentSerializer(dept).data,
                }
            )
        except ValueError:
            return Response({"error": "Invalid amount format"}, status=400)

    @action(detail=True, methods=["post"])
    def update_member_count(self, request, pk=None):
        dept = self.get_object()
        change = request.data.get("change")
        if change is None:
            return Response({"error": "Field 'change' is required"}, status=400)

        try:
            new_count = dept.member_count + int(change)
            if new_count < 0:
                return Response(
                    {"error": "Member count cannot be negative"}, status=400
                )
            dept.member_count = new_count
            dept.save(update_fields=["member_count"])
            return Response(
                {
                    "message": f"Member count updated by {change}",
                    "department": DepartmentSerializer(dept).data,
                }
            )
        except ValueError:
            return Response({"error": "Invalid change value"}, status=400)


#  1. Single school onboarding (system/root admin)
@extend_schema(
    summary="Onboard one school + principal (system/root only)",
    request=SystemSchoolOnboardSerializer,
    responses={
        201: OpenApiResponse(description="School onboarded", response=SchoolSerializer),
        400: OpenApiResponse(description="Validation or failure"),
    },
)
class SystemSchoolOnboardingView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasPermission]
    module = "schools"
    required_action = "create"

    def post(self, request):
        serializer = SystemSchoolOnboardSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        school = serializer.save()  # if create() is on the serializer
        return Response(
            {
                "message": "School onboarded successfully",
                "school": SchoolSerializer(school).data,
            },
            status=status.HTTP_201_CREATED,
        )

#  2. Bulk school onboarding (system/root admin)
@extend_schema(
    summary="Bulk onboard multiple schools (system/root only)",
    request=SystemBulkOnboardSerializer,
    responses={
        201: OpenApiResponse(
            description="Bulk onboarding results",
            response=OpenApiTypes.OBJECT,  # results dict
        ),
        207: OpenApiResponse(description="Partial success"),
        400: OpenApiResponse(description="Validation or input error"),
    },
)
class SystemBulkOnboardingView(APIView):
    """
    Bulk onboard multiple schools (for system/root admins or chain operators).
    Expects list of {school_data, principal_data} objects.
    """

    permission_classes = [permissions.IsAuthenticated, HasPermission]
    module = "schools"
    required_action = "bulk_create"

    def post(self, request):

        serializer = SystemBulkOnboardSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        results = SchoolOnboardingService.bulk_onboard_schools(
            schools_data=serializer.validated_data["schools"], creator=request.user
        )

        status_code = (
            status.HTTP_201_CREATED
            if results["successful"]
            else status.HTTP_207_MULTI_STATUS
        )

        return Response(
            {
                "message": f"Bulk onboarding: {len(results['successful'])} successful, {len(results['failed'])} failed",
                "summary": {
                    "total": len(results["successful"]) + len(results["failed"]),
                    "successful": len(results["successful"]),
                    "failed": len(results["failed"]),
                },
                "results": results,
            },
            status=status_code,
        )


#  3. School-specific onboarding progress & control
@extend_schema(
    summary="View and manage school onboarding progress",
    description="GET: current status + checklist\nPATCH: update status/progress\nPOST: mark as complete",
    responses={
        200: OpenApiResponse(
            description="Onboarding details",
            response=SchoolSerializer,  # or OpenApiTypes.OBJECT if no serializer
        ),
        400: OpenApiResponse(description="Invalid request"),
        404: OpenApiResponse(description="School not found"),
    },
)
class SchoolOnboardingProgressView(APIView):
    """
    GET    → view current onboarding status + checklist
    PATCH  → update status/progress (restricted)
    POST   → mark as complete
    """

    permission_classes = [permissions.IsAuthenticated, HasPermission]
    module = "schools"
    required_action = "manage_onboarding"
    serializer_class = SchoolSerializer

    def get_permissions(self):
        if self.request.method == "GET":
            self.required_action = "read_onboarding"
        return super().get_permissions()

    def get(self, request, school_id):
        school = get_object_or_404(School, id=school_id)
        checklist = {
            "has_principal": school.principal_id is not None,
            "has_academic_year": school.academic_years.exists(),
            "has_classrooms": school.classrooms.exists(),
            "onboarding_status": school.onboarding_status,
        }
        # Do not call SchoolOnboardingService.get_onboarding_checklist unless it exists
        return Response({
            "school": SchoolSerializer(school).data,
            "checklist": checklist,
            "current_status": school.onboarding_status,
            "progress": school.onboarding_progress,
        })

    def patch(self, request, school_id):
        school = get_object_or_404(School, id=school_id)

        # Only allow certain fields to be updated manually
        allowed_fields = [
            "onboarding_status",
            "onboarding_progress",
            "subscription_tier",
        ]
        updates = {k: v for k, v in request.data.items() if k in allowed_fields}

        if not updates:
            return Response({"error": "No valid fields to update"}, status=400)
        for field, value in updates.items():
            setattr(school, field, value)

        school.save(update_fields=updates.keys())

        return Response(
            {
                "message": "Onboarding progress updated",
                "school": SchoolSerializer(school).data,
            }
        )

    def post(self, request, school_id):
        school = get_object_or_404(School, id=school_id)
        try:
            SchoolOnboardingService.complete_onboarding(school, request.user)
            return Response(
                {
                    "message": "Onboarding marked as complete",
                    "school": SchoolSerializer(school).data,
                }
            )
        except ValueError as e:
            return Response({"error": str(e)}, status=400)


#  4. System-wide onboarding dashboard / overview
@extend_schema(
    summary="System-wide onboarding dashboard overview",
    responses={
        200: OpenApiResponse(
            description="Onboarding statistics and summaries",
            response=OpenApiTypes.OBJECT,  # summary dict
        )
    },
)
class SystemOnboardingDashboardView(APIView):
    """
    High-level overview for system admins: onboarding stats, pending schools, etc.
    """

    permission_classes = [permissions.IsAuthenticated, HasPermission]
    module = "schools"
    required_action = "read_dashboard"

    def get(self, request):
        schools = School.objects.all()

        pending = schools.filter(
            onboarding_status__in=[
                OnboardingStatusChoices.PENDING,
                OnboardingStatusChoices.PRINCIPAL_CREATED,
                OnboardingStatusChoices.STRUCTURES_SETUP,
            ]
        )

        data = {
            "summary": {
                "total_schools": schools.count(),
                "active_schools": schools.filter(is_active=True).count(),
                "in_trial": schools.filter(subscription_tier="FREE_TRIAL").count(),
                "onboarding_pending": pending.count(),
                "onboarding_complete": schools.filter(
                    onboarding_status=OnboardingStatusChoices.ACTIVE
                ).count(),
                "suspended_or_archived": schools.filter(
                    onboarding_status__in=[
                        OnboardingStatusChoices.SUSPENDED,
                        OnboardingStatusChoices.ARCHIVED,
                    ]
                ).count(),
            },
            "by_status": list(
                schools.values("onboarding_status")
                .annotate(count=Count("id"))
                .order_by("-count")
            ),
            "by_county": list(
                schools.values("county")
                .annotate(
                    count=Count("id"),
                    pending=Count(
                        "id",
                        filter=Q(
                            onboarding_status__in=[
                                OnboardingStatusChoices.PENDING,
                                OnboardingStatusChoices.PRINCIPAL_CREATED,
                                OnboardingStatusChoices.STRUCTURES_SETUP,
                            ]
                        ),
                    ),
                )
                .order_by("-count")[:15]
            ),
            "needs_attention": list(
                pending.filter(needs_onboarding_attention=True)
                .values(
                    "id",
                    "school_name",
                    "county",
                    "onboarding_status",
                    "onboarding_progress",
                )
                .order_by("onboarded_date")[:10]
            ),
        }

        return Response(data)


#   ADVANCED SCHOOL SEARCH (public / filtered)
class SchoolSearchView(generics.ListAPIView):
    """
    Advanced search endpoint for schools.
    Supports filtering, partial matching, and basic sorting.
    Example usage:
        GET /v1/schools/search/advanced/?q=nairobi&type=secondary&county=Nairobi&min_enrollment=200
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = SchoolSimpleSerializer
    queryset = School.objects.none()

    def get_queryset(self):
        
        if getattr(self, "swagger_fake_view", False):
            return School.objects.none()
        queryset = School.objects.filter(is_active=True).select_related("principal")
        # Validate and extract search parameters
        search_params_serializer = SchoolSearchSerializer(
            data=self.request.query_params
        )
        search_params_serializer.is_valid(raise_exception=True)

        # Use .validated_data or empty dict → fixes type checker complaints
        filters = search_params_serializer.validated_data or {}

        # ── Text / fuzzy search
        if q := filters.get("q"):
            queryset = queryset.filter(
                Q(school_name__icontains=q)
                | Q(school_code__icontains=q)
                | Q(county__icontains=q)
                | Q(sub_county__icontains=q)
                | Q(ward__icontains=q)
            )

        # ── Exact / choice filters
        if county := filters.get("county"):
            queryset = queryset.filter(county__iexact=county)

        if sub_county := filters.get("sub_county"):
            queryset = queryset.filter(sub_county__iexact=sub_county)

        if school_type := filters.get("school_type"):
            queryset = queryset.filter(school_type=school_type)

        if category := filters.get("school_category"):
            queryset = queryset.filter(school_category=category)

        if status := filters.get("onboarding_status"):
            queryset = queryset.filter(onboarding_status=status)

        # ── Boolean / existence filters
        if filters.get("is_active") is not None:
            queryset = queryset.filter(is_active=filters["is_active"])

        if (has_principal := filters.get("has_principal")) is not None:
            queryset = queryset.filter(principal__isnull=not has_principal)

        # ── Numeric range filters
        if min_enroll := filters.get("min_enrollment"):
            queryset = queryset.filter(current_enrollment__gte=min_enroll)

        if max_enroll := filters.get("max_enrollment"):
            queryset = queryset.filter(current_enrollment__lte=max_enroll)

        # ── Ordering
        ordering = filters.get("ordering", "-created_at")
        allowed_order_fields = {
            "school_name",
            "current_enrollment",
            "created_at",
            "onboarding_progress",
            "-school_name",
            "-current_enrollment",
            "-created_at",
            "-onboarding_progress",
        }

        if ordering.lstrip("-") in {
            "school_name",
            "current_enrollment",
            "created_at",
            "onboarding_progress",
        }:
            queryset = queryset.order_by(ordering)
        # else: keep default ordering (or raise 400 if you want strict validation)

        return queryset.distinct()

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(
            {
                "count": queryset.count(),
                "results": serializer.data,
            }
        )


#   REGIONAL ADMIN SCHOOL CREATION
@extend_schema(
    summary="Regional Admin creates a school in their county",
    request=RegionalAdminCreateSchoolSerializer,
    responses={
        201: OpenApiResponse(description="School created", response=SchoolSerializer),
        400: OpenApiResponse(description="Validation error"),
        403: OpenApiResponse(description="Permission denied (wrong county)"),
    },
)
class RegionalAdminCreateSchoolView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasPermission]
    module = "schools"
    required_action = "create"

    def post(self, request):
        serializer = RegionalAdminCreateSchoolSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        # implement create() on the serializer (as in previous message) OR:
        data = serializer.validated_data
        name_parts = data.pop("principal_full_name").split()
        principal_data = {
            "first_name": name_parts[0],
            "last_name": " ".join(name_parts[1:]) or name_parts[0],
            "email": data.pop("principal_email"),
        }
        data.pop("auto_create_principal", None)

        school, principal = SchoolOnboardingService.create_school_with_principal(
            school_data=data,
            principal_data=principal_data,
            creator=request.user,
        )
        return Response(
            {
                "message": "School created successfully",
                "school": SchoolSerializer(school).data,
                "principal_login_id": principal.login_id,
            },
            status=status.HTTP_201_CREATED,
        )