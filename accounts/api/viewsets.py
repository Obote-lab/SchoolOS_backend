from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiTypes,
    extend_schema,
    extend_schema_view,
)
from rest_framework import generics, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from schools.models import School
from ..models import CustomUser, PermissionMatrix, Role, UserRole
from .permissions import HasPermission
from .serializers import (
    BulkUserCreateSerializer,
    CustomUserCreateSerializer,
    CustomUserSerializer,
    CustomUserUpdateSerializer,
    LoginSerializer,
    LogoutSerializer,
    PasswordChangeSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    PermissionMatrixSerializer,
    RoleSerializer,
    UserRoleSerializer,
    UserSearchSerializer,
    RegionalAdminCreateSerializer,
)
from ..services.user_creation_services import UserCreationService

User = get_user_model()


@extend_schema_view(
    list=extend_schema(summary="List users (scoped by permissions)"),
    retrieve=extend_schema(summary="Get user detail"),
    update=extend_schema(summary="Update user"),
    partial_update=extend_schema(summary="Partial update user"),
    destroy=extend_schema(summary="Deactivate user"),
)
class CustomUserViewSet(viewsets.ModelViewSet):
    module = "users"
    queryset = CustomUser.objects.all().order_by("-date_joined")
    permission_classes = [permissions.IsAuthenticated, HasPermission]

    def get_serializer_class(self):
        if self.action == "create":
            return CustomUserCreateSerializer
        if self.action in ["update", "partial_update"]:
            return CustomUserUpdateSerializer
        if self.action == "bulk_create":
            return BulkUserCreateSerializer
        return CustomUserSerializer

    def get_permissions(self):
        # Dynamic required_action
        if self.action == "create":
            self.required_action = "create"
        elif self.action in ["update", "partial_update"]:
            self.required_action = "update"
        elif self.action == "destroy":
            self.required_action = "delete"
        elif self.action in ["me", "update_me"]:
            self.required_action = "read" if self.request.method == "GET" else "update"
        elif self.action in ["lock_account", "unlock_account"]:
            self.required_action = "manage_account"
        else:
            self.required_action = "read"
        return super().get_permissions()

    def get_queryset(self):
        return CustomUser.objects.all().order_by("-date_joined")

    def create(self, request, *args, **kwargs):
        return Response(
            {"error": "Direct creation disabled. Use hierarchy endpoints (e.g. bulk_create)."},
            status=status.HTTP_403_FORBIDDEN
        )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_active = False
        instance.can_login = False
        instance.save(update_fields=["is_active", "can_login"])
        return Response({"message": "User deactivated."})

    @action(detail=False, methods=["get", "patch"])
    def me(self, request):
        if request.method == "GET":
            serializer = self.get_serializer(request.user)
            return Response(serializer.data)

        serializer = CustomUserUpdateSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @action(detail=False, methods=["post"])
    def change_password(self, request):
        serializer = PasswordChangeSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"message": "Password changed successfully."})

    @action(detail=True, methods=["post"])
    def lock_account(self, request, pk=None):
        user = self.get_object()
        hours = request.data.get("hours", 24)
        user.lock_account(hours)
        return Response({
            "message": f"Account locked for {hours} hours.",
            "is_locked": user.is_locked(),
        })

    @action(detail=True, methods=["post"])
    def unlock_account(self, request, pk=None):
        user = self.get_object()
        user.unlock_account()
        return Response({"message": "Account unlocked.", "is_locked": False})

    @action(detail=False, methods=["get"])
    def search(self, request):
        serializer = UserSearchSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        query = serializer.validated_data.get("query")
        role = serializer.validated_data.get("role")
        school = serializer.validated_data.get("school")
        is_active = serializer.validated_data.get("is_active")

        queryset = CustomUser.objects.all()

        if query:
            queryset = queryset.filter(
                Q(login_id__icontains=query) |
                Q(email__icontains=query) |
                Q(phone__icontains=query) |
                Q(first_name__icontains=query) |
                Q(last_name__icontains=query)
            )

        # FIXED: No role__name — use PermissionMatrix in view or service
        # For now, filter by role name only if permitted (should be matrix-checked)
        if role:
            queryset = queryset.filter(
                user_roles__role__name=role, user_roles__is_active=True
            ).distinct()

        if school:
            queryset = queryset.filter(
                user_roles__school_id=school, user_roles__is_active=True
            ).distinct()

        if is_active is not None:
            queryset = queryset.filter(is_active=is_active)

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = CustomUserSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = CustomUserSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["post"])
    def bulk_create(self, request):
        serializer = BulkUserCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        results = serializer.save()
        return Response({
            "message": f"Created {len(results['created'])} users.",
            "created": results["created"],  # return full list
            "failed": results["failed"],
        })


class RoleViewSet(viewsets.ModelViewSet):
    module = "roles"
    queryset = Role.objects.all().order_by("permissions_tier", "name")
    serializer_class = RoleSerializer
    permission_classes = [permissions.IsAuthenticated, HasPermission]


class UserRoleViewSet(viewsets.ModelViewSet):
    module = "user_roles"
    queryset = UserRole.objects.all().select_related("user", "role", "school")
    serializer_class = UserRoleSerializer
    permission_classes = [permissions.IsAuthenticated, HasPermission]

    @action(detail=False, methods=["get"])
    def get_my_roles(self, request):
        roles = UserRole.objects.filter(user=request.user, is_active=True)
        serializer = self.get_serializer(roles, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["post"])
    def assign_role(self, request):
        from ..services.role_assignment import RoleAssignmentService
        try:
            user_role = RoleAssignmentService.assign_role(
                actor=request.user,
                target_user_id=request.data.get("user_id"),
                role_id=request.data.get("role_id"),
                school=getattr(request, "school", None),
                metadata={
                    "is_primary": request.data.get("is_primary", False),
                    "valid_until": request.data.get("valid_until"),
                }
            )
            return Response({
                "message": f"Role assigned: {user_role.role.name}",
                "user_role": UserRoleSerializer(user_role).data,
            })
        except Exception as e:
            return Response({"error": str(e)}, status=400)


class PermissionMatrixViewSet(viewsets.ModelViewSet):
    module = "permissions"
    queryset = PermissionMatrix.objects.all().select_related("role")
    serializer_class = PermissionMatrixSerializer
    permission_classes = [permissions.IsAuthenticated, HasPermission]


# ── AUTH VIEWS ──────────────────────────────────────────────────────────────
class LoginView(generics.GenericAPIView):
    serializer_class = LoginSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]

        user.last_login = timezone.now()
        user.save(update_fields=["last_login"])

        refresh = RefreshToken.for_user(user)
        refresh["school_id"] = str(user.school.id) if user.school else None

        return Response({
            "user": user.login_id,
            "user_id": str(user.id),
            "is_superuser": user.is_superuser,
            "school": str(user.school.id) if user.school else None,
            "must_change_password": serializer.validated_data.get("must_change_password", False),
            "tokens": {
                "refresh": str(refresh),
                "access": str(refresh.access_token),
            },
        })


class LogoutView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = LogoutSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        RefreshToken(serializer.validated_data["refresh"]).blacklist()
        return Response({"message": "Logged out."})


class PasswordResetRequestView(generics.GenericAPIView):
    serializer_class = PasswordResetRequestSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = CustomUser.objects.filter(login_id=serializer.validated_data["login_id"]).first()

        if user:
            from ..services.password_reset_service import PasswordResetService
            PasswordResetService.send_password_reset_email(user, request=request)

        return Response({"message": "If account exists, reset instructions sent."})


class PasswordResetConfirmView(generics.GenericAPIView):
    serializer_class = PasswordResetConfirmSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        from ..services.password_reset_service import PasswordResetService
        user = PasswordResetService.validate_reset_token(serializer.validated_data["token"])
        if not user:
            return Response({"error": "Invalid/expired token"}, status=400)

        PasswordResetService.reset_password(user, serializer.validated_data["new_password"], request=request)
        return Response({"message": "Password reset successful."})


# SCHOOL-LEVEL CREATION 
class CreateTeacherView(APIView):
    serializer_class = CustomUserCreateSerializer
    permission_classes = [permissions.IsAuthenticated, HasPermission]
    module = "users"
    required_action = "create"

    def post(self, request, school_id):
        school = get_object_or_404(School, id=school_id)
        user = UserCreationService.create_user(
            creator=request.user,
            school=school,
            user_data=request.data,
            role_name="Teacher",
            send_email=True,
        )
        return Response({
            "message": "Teacher created",
            "login_id": user.login_id,
            "user": CustomUserSerializer(user).data,
        }, status=201)


# ── SYSTEM ROOT ADMIN VIEWS 
class SystemRootCreateRegionalAdminView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasPermission]
    module = "users"
    required_action = "create_regional_admin"

    def post(self, request):
        serializer = RegionalAdminCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        user = UserCreationService.create_user(
            creator=request.user,
            school=None,
            user_data={
                "first_name": data["first_name"],
                "last_name": data["last_name"],
                "email": data["email"],
                "phone": data["phone"],
                "managed_counties": data["managed_counties"],
            },
            role_name="Regional Admin",
            send_email=True,
        )

        return Response({
            "message": "Regional Admin created",
            "login_id": user.login_id,
            "user": CustomUserSerializer(user).data,
        }, status=201)


class SystemRootDashboardView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasPermission]
    module = "system"
    required_action = "read_dashboard"

    def get(self, request):
        total_users = CustomUser.objects.count()
        total_schools = School.objects.count()
        regional_admins = CustomUser.objects.filter(user_type="RAD").count()
        recent_users = CustomUser.objects.order_by('-created_at')[:10]
        recent_schools = School.objects.order_by('-created_at')[:10]

        return Response({
            "summary": {
                "total_users": total_users,
                "total_schools": total_schools,
                "regional_admins": regional_admins,
                "active_schools": School.objects.filter(is_active=True).count(),
            },
            "recent_users": CustomUserSerializer(recent_users, many=True).data,
            "recent_schools": recent_schools.values("id", "school_name", "county", "created_at"),
        })


class SystemCreatePrincipalForSchoolView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasPermission]
    module = "users"
    required_action = "create_principal"

    def post(self, request, school_id):
        school = get_object_or_404(School, id=school_id)

        if school.principal:
            return Response({"error": "School already has a principal"}, status=400)

        user = UserCreationService.create_user(
            creator=request.user,
            school=school,
            user_data=request.data,
            role_name="Principal",
            send_email=True,
        )

        school.principal = user
        school.save(update_fields=['principal'])

        return Response({
            "message": "Principal created and assigned",
            "login_id": user.login_id,
            "user": CustomUserSerializer(user).data,
            "school_id": str(school.id),
            "school_name": school.school_name
        }, status=201)


class RegionalAdminDashboardView(APIView):
    serializer_class = RegionalAdminCreateSerializer
    permission_classes = [permissions.IsAuthenticated, HasPermission]
    module = "regional"
    required_action = "read_dashboard"

    def get(self, request):
        user = request.user
        counties = user.managed_counties.all()
        if not counties.exists():
            return Response({"error": "No counties assigned"}, status=400)

        schools = School.objects.filter(county__in=counties.values_list('name', flat=True))

        return Response({
            "regional_admin": user.get_full_name(),
            "counties": [c.name for c in counties],
            "summary": {
                "total_schools": schools.count(),
                "active_schools": schools.filter(is_active=True).count(),
                "schools_with_principal": schools.filter(principal__isnull=False).count(),
            },
            "schools": schools.values("id", "school_name", "has_principal", "is_active")[:20],
        })