from django.contrib.gis.geos import Point
from django.core.exceptions import ValidationError
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import permissions, status, viewsets, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db import transaction


from accounts.api.permissions import HasPermission
from accounts.models import UserRole
from ..models import AcademicYear, ClassRoom, Department, School, Term
from ..services.onboarding import SchoolOnboardingService
from .serializers import (
    AcademicYearSerializer,
    AcademicYearSimpleSerializer,
    ClassRoomSerializer,
    ClassRoomSimpleSerializer,
    DepartmentSerializer,
    SchoolCreateSerializer,
    SchoolSerializer,
    SchoolSimpleSerializer,
    SchoolUpdateSerializer,
    TermSerializer,
    SystemSchoolOnboardSerializer,
    SystemBulkOnboardSerializer,
    RegionalAdminCreateSchoolSerializer,
    SchoolSearchSerializer
)


# SCHOOL VIEWSET
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
        # You might want to add .select_related() / .prefetch_related() later
        return School.objects.all().order_by("school_name")

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    # ── Status actions 
    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        school = self.get_object()
        school.is_active = True
        school.save(update_fields=["is_active"])
        return Response({
            "message": f"School {school.school_name} activated",
            "school": SchoolSerializer(school).data
        })

    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        school = self.get_object()
        school.is_active = False
        school.save(update_fields=["is_active"])
        return Response({
            "message": f"School {school.school_name} deactivated",
            "school": SchoolSerializer(school).data
        })

    # ── Onboarding actions 
    @action(detail=True, methods=["get"])
    def onboarding_status(self, request, pk=None):
        school = self.get_object()
        checklist = SchoolOnboardingService.get_onboarding_checklist(school)
        return Response({
            "school": SchoolSerializer(school).data,
            "checklist": checklist
        })

    @action(detail=True, methods=["post"])
    def setup_structures(self, request, pk=None):
        school = self.get_object()
        if school.onboarding_status not in [
            School.OnboardingStatusChoices.PENDING,
            School.OnboardingStatusChoices.PRINCIPAL_CREATED
        ]:
            return Response({"error": "Structures can only be set up in early onboarding stages"}, status=400)

        try:
            result = SchoolOnboardingService.setup_basic_structures(school, request.user)
            return Response({
                "message": "Basic structures (academic year, terms, classrooms) created",
                "result": result,
                "school": SchoolSerializer(school).data
            })
        except ValueError as e:
            return Response({"error": str(e)}, status=400)

    @action(detail=True, methods=["post"])
    def complete_onboarding(self, request, pk=None):
        school = self.get_object()
        try:
            SchoolOnboardingService.complete_onboarding(school, request.user)
            return Response({
                "message": "School onboarding marked as complete",
                "school": SchoolSerializer(school).data
            })
        except ValueError as e:
            return Response({"error": str(e)}, status=400)

    # ── Enrollment management
    @action(detail=True, methods=["post"])
    def update_enrollment(self, request, pk=None):
        school = self.get_object()
        change = request.data.get("change")
        if change is None:
            return Response({"error": "Field 'change' is required (integer)"}, status=400)

        try:
            change = int(change)
            school.update_enrollment(change)
            return Response({
                "message": f"Enrollment updated by {change}",
                "current_enrollment": school.current_enrollment,
                "school": SchoolSerializer(school).data
            })
        except (ValueError, ValidationError) as e:
            return Response({"error": str(e)}, status=400)

    #  Search & statistics 
    @action(detail=False, methods=["get"])
    def search(self, request):
        query = request.query_params.get("q", "").strip()
        county = request.query_params.get("county")
        school_type = request.query_params.get("type")
        category = request.query_params.get("category")

        qs = School.objects.filter(is_active=True)

        if query:
            qs = qs.filter(
                Q(school_name__icontains=query) |
                Q(school_code__icontains=query) |
                Q(county__icontains=query) |
                Q(sub_county__icontains=query)
            )
        if county:
            qs = qs.filter(county__icontains=county)
        if school_type:
            qs = qs.filter(type=school_type)
        if category:
            qs = qs.filter(school_category=category)

        page = self.paginate_queryset(qs)
        if page is not None:
            return self.get_paginated_response(SchoolSimpleSerializer(page, many=True).data)

        return Response(SchoolSimpleSerializer(qs, many=True).data)

    @action(detail=False, methods=["get"])
    def statistics(self, request):
        qs = School.objects.all()
        total_capacity = qs.aggregate(total=Sum("capacity"))["total"] or 0
        total_enrollment = qs.aggregate(total=Sum("current_enrollment"))["total"] or 0

        return Response({
            "total_schools": qs.count(),
            "active_schools": qs.filter(is_active=True).count(),
            "total_capacity": total_capacity,
            "total_enrollment": total_enrollment,
            "total_vacancies": total_capacity - total_enrollment,
            "overall_enrollment_rate": round(
                (total_enrollment / total_capacity * 100) if total_capacity > 0 else 0, 1
            ),
            "by_type": list(qs.values("type").annotate(count=Count("id"))),
            "by_category": list(qs.values("school_category").annotate(count=Count("id"))),
            "by_county_top10": list(
                qs.values("county")
                  .annotate(count=Count("id"), enrollment=Sum("current_enrollment"))
                  .order_by("-count")[:10]
            )
        })



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
        if self.action in ["create", "update", "partial_update", "destroy", "set_current"]:
            self.required_action = "manage"
        else:
            self.required_action = "read"
        return super().get_permissions()

    def get_queryset(self):
        qs = super().get_queryset()
        school_id = self.request.query_params.get("school")
        if school_id:
            qs = qs.filter(school_id=school_id)
        return qs

    @action(detail=True, methods=["post"])
    def set_current(self, request, pk=None):
        year = self.get_object()
        AcademicYear.objects.filter(school=year.school).exclude(pk=year.pk).update(is_current=False)
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
        if self.action in ["create", "update", "partial_update", "destroy", "update_student_count"]:
            self.required_action = "manage"
        else:
            self.required_action = "read"
        return super().get_permissions()

    def get_queryset(self):
        qs = super().get_queryset()
        school_id = self.request.query_params.get("school") or getattr(self.request, "school", None)
        if school_id:
            qs = qs.filter(school_id=school_id)
        return qs

    @action(detail=False, methods=["get"])
    def by_school(self, request):
        school_id = request.query_params.get("school") or getattr(request, "school", None)
        if not school_id:
            return Response({"error": "school id required (query param or context)"}, status=400)

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
            return Response({"error": "Field 'change' is required (integer)"}, status=400)

        try:
            change = int(change)
            classroom.update_student_count(change)
            return Response({
                "message": f"Student count updated by {change}",
                "current_enrollment": classroom.current_enrollment,
                "classroom": ClassRoomSerializer(classroom).data
            })
        except (ValueError, ValidationError) as e:
            return Response({"error": str(e)}, status=400)



# DEPARTMENT VIEWSET
class DepartmentViewSet(viewsets.ModelViewSet):
    module = "departments"
    queryset = Department.objects.all().order_by("school", "department_name")
    serializer_class = DepartmentSerializer
    permission_classes = [permissions.IsAuthenticated, HasPermission]

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy", "update_budget", "update_member_count"]:
            self.required_action = "manage"
        else:
            self.required_action = "read"
        return super().get_permissions()

    def get_queryset(self):
        qs = super().get_queryset()
        school_id = self.request.query_params.get("school") or getattr(self.request, "school", None)
        if school_id:
            qs = qs.filter(school_id=school_id)
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
            return Response({
                "message": f"Budget updated to {amount}",
                "department": DepartmentSerializer(dept).data
            })
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
                return Response({"error": "Member count cannot be negative"}, status=400)
            dept.member_count = new_count
            dept.save(update_fields=["member_count"])
            return Response({
                "message": f"Member count updated by {change}",
                "department": DepartmentSerializer(dept).data
            })
        except ValueError:
            return Response({"error": "Invalid change value"}, status=400)
        



#  1. Single school onboarding (system/root admin)
class SystemSchoolOnboardingView(APIView):
    """
    System/root admin endpoint to onboard one school + principal in one request.
    """
    permission_classes = [permissions.IsAuthenticated, HasPermission]
    module = "schools"
    required_action = "create"  

    def post(self, request):
    
        serializer = SystemSchoolOnboardSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            with transaction.atomic():
                school, principal_result = SchoolOnboardingService.create_school_with_principal(
                    school_data=serializer.validated_data["school_data"],
                    principal_data=serializer.validated_data["principal_data"],
                    creator=request.user
                )

                if serializer.validated_data.get("auto_setup_structures", True):
                    SchoolOnboardingService.setup_basic_structures(school, request.user)

            return Response(
                {
                    "message": "School onboarded successfully",
                    "school": SchoolSerializer(school).data,
                    "principal": {
                        "id": str(principal_result["user"].id),
                        "login_id": principal_result["user"].login_id,
                        "full_name": principal_result["user"].get_full_name(),
                        # Never return temp_password here!
                    },
                },
                status=status.HTTP_201_CREATED,
            )

        except Exception as e:
            return Response(
                {"error": f"Failed to onboard school: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )



#  2. Bulk school onboarding (system/root admin)
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
            schools_data=serializer.validated_data["schools"],
            creator=request.user
        )

        status_code = status.HTTP_201_CREATED if results["successful"] else status.HTTP_207_MULTI_STATUS

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
class SchoolOnboardingProgressView(APIView):
    """
    GET    → view current onboarding status + checklist
    PATCH  → update status/progress (restricted)
    POST   → mark as complete
    """
    permission_classes = [permissions.IsAuthenticated, HasPermission]
    module = "schools"
    required_action = "manage_onboarding"

    def get_permissions(self):
        if self.request.method == "GET":
            self.required_action = "read_onboarding"
        return super().get_permissions()

    def get(self, request, school_id):
        school = get_object_or_404(School, id=school_id)
        checklist = SchoolOnboardingService.get_onboarding_checklist(school)
        return Response({
            "school": SchoolSerializer(school).data,
            "checklist": checklist,
            "current_status": school.onboarding_status,
            "progress": school.onboarding_progress,
        })

    def patch(self, request, school_id):
        school = get_object_or_404(School, id=school_id)

        # Only allow certain fields to be updated manually
        allowed_fields = ["onboarding_status", "onboarding_progress", "subscription_tier"]
        updates = {k: v for k, v in request.data.items() if k in allowed_fields}

        if not updates:
            return Response({"error": "No valid fields to update"}, status=400)
        for field, value in updates.items():
            setattr(school, field, value)

        school.save(update_fields=updates.keys())

        return Response({
            "message": "Onboarding progress updated",
            "school": SchoolSerializer(school).data
        })

    def post(self, request, school_id):
        school = get_object_or_404(School, id=school_id)
        try:
            SchoolOnboardingService.complete_onboarding(school, request.user)
            return Response({
                "message": "Onboarding marked as complete",
                "school": SchoolSerializer(school).data
            })
        except ValueError as e:
            return Response({"error": str(e)}, status=400)


#  4. System-wide onboarding dashboard / overview
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
                School.OnboardingStatusChoices.PENDING,
                School.OnboardingStatusChoices.PRINCIPAL_CREATED,
                School.OnboardingStatusChoices.STRUCTURES_SETUP,
            ]
        )

        data = {
            "summary": {
                "total_schools": schools.count(),
                "active_schools": schools.filter(is_active=True).count(),
                "in_trial": schools.filter(subscription_tier="FREE_TRIAL").count(),
                "onboarding_pending": pending.count(),
                "onboarding_complete": schools.filter(
                    onboarding_status=School.OnboardingStatusChoices.ACTIVE
                ).count(),
                "suspended_or_archived": schools.filter(
                    onboarding_status__in=[
                        School.OnboardingStatusChoices.SUSPENDED,
                        School.OnboardingStatusChoices.ARCHIVED,
                    ]
                ).count(),
            },
            "by_status": list(
                schools.values("onboarding_status").annotate(count=Count("id")).order_by("-count")
            ),
            "by_county": list(
                schools.values("county")
                .annotate(
                    count=Count("id"),
                    pending=Count("id", filter=Q(onboarding_status__in=[
                        School.OnboardingStatusChoices.PENDING,
                        School.OnboardingStatusChoices.PRINCIPAL_CREATED,
                        School.OnboardingStatusChoices.STRUCTURES_SETUP,
                    ])),
                )
                .order_by("-count")[:15]
            ),
            "needs_attention": list(
                pending.filter(needs_onboarding_attention=True)
                .values("id", "school_name", "county", "onboarding_status", "onboarding_progress")
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

    def get_queryset(self):
        queryset = School.objects.filter(is_active=True).select_related("principal")

        # Validate and extract search parameters
        search_params_serializer = SchoolSearchSerializer(data=self.request.query_params)
        search_params_serializer.is_valid(raise_exception=True)

        # Use .validated_data or empty dict → fixes type checker complaints
        filters = search_params_serializer.validated_data or {}

        # ── Text / fuzzy search ────────────────────────────────────────
        if q := filters.get("q"):
            queryset = queryset.filter(
                Q(school_name__icontains=q)
                | Q(school_code__icontains=q)
                | Q(county__icontains=q)
                | Q(sub_county__icontains=q)
                | Q(ward__icontains=q)
            )

        # ── Exact / choice filters ─────────────────────────────────────
        if county := filters.get("county"):
            queryset = queryset.filter(county__iexact=county)

        if sub_county := filters.get("sub_county"):
            queryset = queryset.filter(sub_county__iexact=sub_county)

        if school_type := filters.get("type"):
            queryset = queryset.filter(type=school_type)

        if category := filters.get("school_category"):
            queryset = queryset.filter(school_category=category)

        if status := filters.get("onboarding_status"):
            queryset = queryset.filter(onboarding_status=status)

        # ── Boolean / existence filters ────────────────────────────────
        if filters.get("is_active") is not None:
            queryset = queryset.filter(is_active=filters["is_active"])

        if (has_principal := filters.get("has_principal")) is not None:
            queryset = queryset.filter(principal__isnull=not has_principal)

        # ── Numeric range filters ──────────────────────────────────────
        if min_enroll := filters.get("min_enrollment"):
            queryset = queryset.filter(current_enrollment__gte=min_enroll)

        if max_enroll := filters.get("max_enrollment"):
            queryset = queryset.filter(current_enrollment__lte=max_enroll)

        # ── Ordering ───────────────────────────────────────────────────
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

        if ordering.lstrip("-") in {"school_name", "current_enrollment", "created_at", "onboarding_progress"}:
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
class RegionalAdminCreateSchoolView(APIView):
    """
    Dedicated endpoint for Regional Admins to create schools in their counties.
    Can optionally auto-create principal account.
    """
    permission_classes = [permissions.IsAuthenticated, HasPermission]
    module = "schools"
    required_action = "create"  

    def post(self, request):
        serializer = RegionalAdminCreateSchoolSerializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)

        validated_data = serializer.validated_data

        # Enforce county restriction again (serializer already checks, but double safety)
        user = request.user
        if not user.is_system_root:
            allowed_counties = set(user.managed_counties.values_list('name', flat=True))
            if validated_data['county'] not in allowed_counties:
                return Response(
                    {"county": "You can only create schools in your assigned counties"},
                    status=status.HTTP_403_FORBIDDEN
                )

        try:
            with transaction.atomic():
                school_data = {
                    k: v for k, v in validated_data.items()
                    if k not in ['principal_email', 'principal_full_name', 'auto_create_principal']
                }
                school_data['created_by'] = request.user

                # Basic onboarding defaults
                school_data.setdefault('onboarding_status', School.OnboardingStatusChoices.PENDING)
                school_data.setdefault('subscription_tier', 'FREE_TRIAL')

                school = School.objects.create(**school_data)

                if validated_data.get('auto_create_principal', True):
                    # Minimal principal creation – extend as needed
                    from accounts.models import CustomUser
                    from accounts.services.user_creation_services import UserCreationService

                    principal_data = {
                        'first_name': validated_data['principal_full_name'].split()[0],
                        'last_name': ' '.join(validated_data['principal_full_name'].split()[1:]) or '',
                        'email': validated_data['principal_email'],
                        'phone': school_data.get('phone', ''),  
                        'user_type': 'PRN',
                        # Add more fields if your UserCreationService requires them
                    }

                    result = UserCreationService.create_user(
                        creator=request.user,
                        school=school,
                        user_type="PRN",
                        user_data=principal_data
                    )

                    school.principal = result['user']
                    school.first_principal = result['user']
                    school.onboarding_status = School.OnboardingStatusChoices.PRINCIPAL_CREATED
                    school.onboarding_progress = 30
                    school.save(update_fields=['principal', 'first_principal', 'onboarding_status', 'onboarding_progress'])

                return Response(
                    {
                        "message": "School created successfully",
                        "school": SchoolSerializer(school).data
                    },
                    status=status.HTTP_201_CREATED
                )

        except Exception as e:
            return Response(
                {"error": f"School creation failed: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )