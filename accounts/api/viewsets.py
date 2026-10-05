from django.contrib.auth import get_user_model
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import generics, permissions, request, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken


from core.choices.identity import AuditActionChoices
from schools.models import School
from ..models import CustomUser, PermissionMatrix, Role, UserRole
from ..services.account_activation_service import AccountActivationService
from ..services.password_reset_service import PasswordResetService
from ..services.role_assignment import RoleAssignmentService
from ..services.user_creation_services import UserCreationService
from .permissions import HasPermission
from .serializers import (
    AccountActivationSerializer,
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
    RegionalAdminCreateSerializer,
    RoleSerializer,
    SystemRootDashboardResponseSerializer,
    UserRoleSerializer,
    UserSearchSerializer,
    ResendActivationSerializer,
    CreateTeacherSerializer,
    CreatePrincipalSerializer,
    DashboardStatsSerializer,
    MessageSerializer,
    RegionalAdminDashboardResponseSerializer,
    LoginResponseSerializer,
    UserCreatedResponseSerializer,
    BulkUserCreateResponseSerializer,
    AccountActivatedResponseSerializer,
    RoleAssignmentSerializer,
    RoleRevocationSerializer,
    PromotionSerializer,
    TransferSerializer,
)
from core.audit import create_audit_log

User = get_user_model()


# User ViewSet
@extend_schema_view(
    list=extend_schema(summary="List users (scoped by permissions)"),
    retrieve=extend_schema(summary="Get user detail"),
    update=extend_schema(summary="Update user", request=CustomUserUpdateSerializer),
    partial_update=extend_schema(summary="Partial update user", request=CustomUserUpdateSerializer),
    destroy=extend_schema(summary="Deactivate user",responses={200: MessageSerializer},),
    create=extend_schema(exclude=True,),
)
class CustomUserViewSet(viewsets.ModelViewSet):
    module = "users"
    queryset = CustomUser.objects.select_related("school").order_by("-date_joined")
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
        if self.action == "create":
            self.required_action = "create"
        elif self.action in ["update", "partial_update"]:
            self.required_action = "update"
        elif self.action == "destroy":
            self.required_action = "delete"
        elif self.action in ["me"]:
            self.required_action = "read" if self.request.method == "GET" else "update"
        elif self.action in ["lock_account", "unlock_account"]:
            self.required_action = "update"
        else:
            self.required_action = "read"
        return super().get_permissions()

    def get_queryset(self):
        queryset = super().get_queryset()
        school = getattr(self.request, "school", None)
        if school:
            queryset = queryset.filter(
                Q(school=school) | Q(user_roles__school=school)
            ).distinct()
        return queryset

    def create(self, request, *args, **kwargs):
        return Response(
            {"error": "Direct user creation is disabled. Use dedicated endpoints."},
            status=status.HTTP_403_FORBIDDEN,
        )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_active = False
        instance.can_login = False
        instance.save(update_fields=["is_active", "can_login"])

        highest_role = request.user.get_highest_tier()
        role_name = highest_role.name if highest_role else ""

        create_audit_log(
            actor=request.user,
            action=AuditActionChoices.DELETE,
            model_name="CustomUser",
            record_id=instance.id,
            school=instance.school,
            reason="User account deactivated",
            new_value=f"{instance.login_id} deactivated",
            request=request,
        )
        return Response(
            {"message": "User account deactivated."},
            status=status.HTTP_200_OK,
        )


    @extend_schema(
    methods=["GET"],
    responses={200: CustomUserSerializer},
    )
    @extend_schema(
        methods=["PATCH"],
        request=CustomUserUpdateSerializer,
        responses={200: CustomUserSerializer},
    )
    @action(detail=False, methods=["get", "patch"])
    def me(self, request):
        if request.method == "GET":
            serializer = self.get_serializer(request.user)
            return Response(serializer.data)

        serializer = CustomUserUpdateSerializer(
            request.user, data=request.data, partial=True, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)



    @extend_schema(
    request=PasswordChangeSerializer,
    responses={200: MessageSerializer},
    )
    @action(detail=False, methods=["post"])
    def change_password(self, request):
        serializer = PasswordChangeSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"message": "Password changed successfully."})



    @extend_schema(
    request={"application/json": {"type": "object", "properties": {"hours": {"type": "integer"}}}},
    responses={200: MessageSerializer},
    )
    @action(detail=True, methods=["post"])
    def lock_account(self, request, pk=None):
        user = self.get_object()
        hours = int(request.data.get("hours", 24))
        user.lock_account(hours=hours)
        return Response({
            "message": f"Account locked for {hours} hours.",
            "is_locked": user.is_locked(),
        })

    @extend_schema(responses={200: MessageSerializer})
    @action(detail=True, methods=["post"])
    def unlock_account(self, request, pk=None):
        user = self.get_object()
        user.unlock_account()
        return Response({"message": "Account unlocked.", "is_locked": False})

    @extend_schema(
    parameters=[UserSearchSerializer],  # query params
    responses={200: CustomUserSerializer(many=True)},
    )
    @action(detail=False, methods=["get"])
    def search(self, request):
        serializer = UserSearchSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        queryset = self.get_queryset()

        if data.get("query"):
            q = data["query"]
            queryset = queryset.filter(
                Q(login_id__icontains=q)
                | Q(email__icontains=q)
                | Q(phone__icontains=q)
                | Q(first_name__icontains=q)
                | Q(last_name__icontains=q)
            )

        if data.get("role"):
            queryset = queryset.filter(
                user_roles__role__name=data["role"],
                user_roles__is_active=True,
            ).distinct()

        if data.get("school"):
            queryset = queryset.filter(
                user_roles__school_id=data["school"],
                user_roles__is_active=True,
            ).distinct()

        if data.get("is_active") is not None:
            queryset = queryset.filter(is_active=data["is_active"])

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = CustomUserSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        return Response(CustomUserSerializer(queryset, many=True).data)

    @extend_schema(
    request=BulkUserCreateSerializer,
    responses={200: BulkUserCreateResponseSerializer},
    )
    @action(detail=False, methods=["post"])
    def bulk_create(self, request):
        serializer = BulkUserCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        results = serializer.save()
        return Response({
            "message": f"Created {len(results['created'])} users.",
            "created": results["created"],
            "failed": results["failed"],
        })


# Role & Permission ViewSets
@extend_schema_view(
    list=extend_schema(summary="List roles"),
    retrieve=extend_schema(summary="Get role"),
    create=extend_schema(summary="Create role"),
    update=extend_schema(summary="Update role"),
    partial_update=extend_schema(summary="Partial update role"),
    destroy=extend_schema(summary="Delete role"),
)
class RoleViewSet(viewsets.ModelViewSet):
    module = "roles"
    required_action = "read"  # default; override below
    queryset = Role.objects.all().order_by("permissions_tier", "name")
    serializer_class = RoleSerializer
    permission_classes = [permissions.IsAuthenticated, HasPermission]

    def get_permissions(self):
            if self.action == "create":
                self.required_action = "create"
            elif self.action in ["update", "partial_update"]:
                self.required_action = "update"
            elif self.action == "destroy":
                self.required_action = "delete"
            else:
                self.required_action = "read"
            return super().get_permissions()



@extend_schema_view(
    list=extend_schema(summary="List role assignments"),
    retrieve=extend_schema(summary="Get role assignment"),
    create=extend_schema(summary="Create role assignment"),
    update=extend_schema(summary="Update role"),
    partial_update=extend_schema(summary="Partial update role"),
    destroy=extend_schema(summary="Delete role"),
)
class UserRoleViewSet(viewsets.ModelViewSet):
    module = "user_roles"
    queryset = UserRole.objects.select_related("user", "role", "school", "assigned_by").all()
    serializer_class = UserRoleSerializer
    permission_classes = [permissions.IsAuthenticated, HasPermission]

    def get_permissions(self):
        if self.action in ["create", "assign_role", "promote_user", "transfer_user"]:
            self.required_action = "create"
        elif self.action in ["update", "partial_update"]:
            self.required_action = "update"
        elif self.action in ["destroy", "revoke_role"]:
            self.required_action = "delete"
        else:
            self.required_action = "read"
        return super().get_permissions()


    @extend_schema(responses={200: UserRoleSerializer(many=True)})
    @action(detail=False, methods=["get"])
    def my_roles(self, request):
        roles = RoleAssignmentService.get_active_roles(request.user)
        return Response(self.get_serializer(roles, many=True).data)

    @extend_schema(responses={200: UserRoleSerializer, 404: MessageSerializer})
    @action(detail=False, methods=["get"])
    def primary_role(self, request):
        role = RoleAssignmentService.get_primary_role(request.user)
        if not role:
            return Response({"detail": "No primary role found."}, status=404)
        return Response(self.get_serializer(role).data)



    @extend_schema(
            request=RoleAssignmentSerializer,
            responses={201: UserRoleSerializer},
    )
    @action(detail=False, methods=["post"])
    def assign_role(self, request):
        ser = RoleAssignmentSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        assignment = RoleAssignmentService.assign_role(
            actor=request.user,
            target_user=data["user_id"],
            role=data["role_id"],
            school=data.get("school_id"),
            is_primary=data.get("is_primary", True),
        )
        return Response(
            self.get_serializer(assignment).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        request=RoleRevocationSerializer,
        responses={200: UserRoleSerializer},
    )
    @action(detail=False, methods=["post"])
    def revoke_role(self, request):
        ser = RoleRevocationSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        assignment = RoleAssignmentService.revoke_role(
            actor=request.user,
            assignment=ser.validated_data["assignment_id"],
            reason=ser.validated_data.get("reason", "Role revoked"),
        )
        return Response(self.get_serializer(assignment).data)

    @extend_schema(
        request=PromotionSerializer,
        responses={200: UserRoleSerializer},
    )
    @action(detail=False, methods=["post"])
    def promote_user(self, request):
        ser = PromotionSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        assignment = RoleAssignmentService.promote_user(
            actor=request.user,
            target_user=data["user_id"],
            new_role=data["new_role_id"],
            school=data.get("school_id"),
        )
        return Response(self.get_serializer(assignment).data)

    @extend_schema(
        request=TransferSerializer,
        responses={200: UserRoleSerializer(many=True)},
    )
    @action(detail=False, methods=["post"])
    def transfer_user(self, request):
        ser = TransferSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        from schools.models import School
        new_school = get_object_or_404(School, id=data["new_school_id"])

        assignments = RoleAssignmentService.transfer_user(
            actor=request.user,
            target_user=data["user_id"],
            new_school=new_school,
        )
        return Response(self.get_serializer(assignments, many=True).data)


@extend_schema_view(
    list=extend_schema(summary="List roles"),
    retrieve=extend_schema(summary="Get role"),
    create=extend_schema(summary="Create role"),
    update=extend_schema(summary="Update role"),
    partial_update=extend_schema(summary="Partial update role"),
    destroy=extend_schema(summary="Delete role"),
)

class PermissionMatrixViewSet(viewsets.ModelViewSet):
    module = "permissions"
    queryset = PermissionMatrix.objects.select_related("role").all()
    serializer_class = PermissionMatrixSerializer
    permission_classes = [permissions.IsAuthenticated, HasPermission]

    def get_permissions(self):
        if self.action == "create":
            self.required_action = "create"
        elif self.action in ["update", "partial_update"]:
            self.required_action = "update"
        elif self.action == "destroy":
            self.required_action = "delete"
        else:
            self.required_action = "read"
        return super().get_permissions()


# Authentication Views
class LoginView(generics.GenericAPIView):
    serializer_class = LoginSerializer
    permission_classes = [permissions.AllowAny]


    @extend_schema(
        request=LoginSerializer,
        responses={200: LoginResponseSerializer},
        summary="Login",
    )
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data["user"]
        user.last_login = timezone.now()
        user.save(update_fields=["last_login"])

        refresh = RefreshToken.for_user(user)
        if user.school:
            refresh["school_id"] = str(user.school.id)

        primary_role = (
            user.user_roles.filter(is_active=True, is_primary_role=True)
            .select_related("role")
            .first()
        )
        create_audit_log(
            actor=user,
            action=AuditActionChoices.LOGIN,
            model_name="CustomUser",
            record_id=user.pk,
            school=user.school,
            reason="Successful login",
            new_value=user.login_id,
            request=request,
        )

        return Response(
            {
                "user": {
                    "id": str(user.id),
                    "login_id": user.login_id,
                    "full_name": user.get_full_name(),
                    "email": user.email,
                    "is_superuser": user.is_superuser,
                    "school": {
                        "id": str(user.school.id),
                        "name": user.school.school_name,
                    } if user.school else None,
                    "primary_role": primary_role.role.name if primary_role else None,
                    "must_change_password": serializer.validated_data.get(
                        "must_change_password", False
                    ),
                },
                "tokens": {
                    "refresh": str(refresh),
                    "access": str(refresh.access_token),
                },
            },
            status=status.HTTP_200_OK,
        )


class LogoutView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = LogoutSerializer


    @extend_schema(
        request=LogoutSerializer,
        responses={200: MessageSerializer},
        summary="Logout",
    )
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        RefreshToken(serializer.validated_data["refresh"]).blacklist()
        return Response({"message": "Logged out successfully."})


class PasswordResetRequestView(generics.GenericAPIView):
    serializer_class = PasswordResetRequestSerializer
    permission_classes = [permissions.AllowAny]


    @extend_schema(
        request=PasswordResetRequestSerializer,
        responses={200: MessageSerializer},
        summary="Request password reset",
    )
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={"request": request})
        try:
            serializer.is_valid(raise_exception=True)
            serializer.save()
        except Exception:
            pass
        return Response(
            {"message": "If the account exists, password reset instructions have been sent."}
        )

class PasswordResetConfirmView(generics.GenericAPIView):
    serializer_class = PasswordResetConfirmSerializer
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        request=PasswordResetConfirmSerializer,
        responses={200: MessageSerializer},
    )
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"message": "Password has been reset successfully."})


class AccountActivationView(generics.GenericAPIView):
    serializer_class = AccountActivationSerializer
    permission_classes = [permissions.AllowAny]


    @extend_schema(
        request=AccountActivationSerializer,
        responses={200: AccountActivatedResponseSerializer},
    )
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        return Response(result, status=status.HTTP_200_OK)


class ResendActivationEmailView(generics.GenericAPIView):
    serializer_class = ResendActivationSerializer
    permission_classes = [permissions.AllowAny]

    @extend_schema(summary="Resend activation email", responses={200: MessageSerializer})
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        login_id = serializer.validated_data["login_id"]
        user = CustomUser.objects.filter(login_id=login_id).first()
        if user:
            AccountActivationService.send_activation_email(user=user)
        return Response({
            "message": "If the account exists, an activation email has been sent."
        })


# Specialized Creation Endpoints
@extend_schema(
    summary="Create Teacher for a specific school",
    request=CreateTeacherSerializer,
    responses={201: UserCreatedResponseSerializer},
)
class CreateTeacherView(generics.GenericAPIView):
    serializer_class = CreateTeacherSerializer
    permission_classes = [permissions.IsAuthenticated, HasPermission]
    module = "users"
    required_action = "create"

    def post(self, request, school_id):
        school = get_object_or_404(School, id=school_id)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = UserCreationService.create_user(
            creator=request.user,
            school=school,
            user_data=serializer.validated_data,
            role_name="Teacher",
            send_email=True,
        )
        return Response(
            {
                "message": "Teacher created successfully",
                "login_id": user.login_id,
                "user": CustomUserSerializer(user).data,
            },
            status=status.HTTP_201_CREATED,
        )
    
@extend_schema(
    summary="Create Regional Admin (System Root only)",
    request=RegionalAdminCreateSerializer,
    responses={201: UserCreatedResponseSerializer},
)
class SystemRootCreateRegionalAdminView(generics.GenericAPIView):
    serializer_class = RegionalAdminCreateSerializer  # the one WITH create()
    permission_classes = [permissions.IsAuthenticated, HasPermission]
    module = "users"
    required_action = "create"

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        return Response(result, status=status.HTTP_201_CREATED)


@extend_schema(
    summary="Create and assign Principal to a school",
    request=CreatePrincipalSerializer,
    responses={201: UserCreatedResponseSerializer},
)
class SystemCreatePrincipalForSchoolView(generics.GenericAPIView):
    serializer_class = CreatePrincipalSerializer
    permission_classes = [permissions.IsAuthenticated, HasPermission]
    module = "users"
    required_action = "create"

    def post(self, request, school_id):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        school = get_object_or_404(School, id=school_id)
        user = UserCreationService.create_user(
            creator=request.user,
            school=school,
            user_data=serializer.validated_data,  # not request.data
            role_name="Principal",
            send_email=True,
        )
        if hasattr(school, "principal"):
            school.principal = user
            school.save(update_fields=["principal"])
        return Response(
            {
                "message": "Principal created and assigned",
                "login_id": user.login_id,
                "user": CustomUserSerializer(user).data,
                "school_id": str(school.id),
                "school_name": school.school_name,
            },
            status=status.HTTP_201_CREATED,
        )


# Dashboard Views
class SystemRootDashboardView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated, HasPermission]
    module = "system"
    required_action = "read"
    serializer_class = SystemRootDashboardResponseSerializer

    @extend_schema(
        summary="System root dashboard",
        responses={200: SystemRootDashboardResponseSerializer},
    )
    def get(self, request):
        total_users = CustomUser.objects.count()
        total_schools = School.objects.count()
        recent_users = CustomUser.objects.order_by("-date_joined")[:10]
        payload = {
            "summary": {
                "total_users": total_users,
                "total_schools": total_schools,
                "active_schools": (
                    School.objects.filter(is_active=True).count()
                    if hasattr(School, "is_active")
                    else total_schools
                ),
            },
            "recent_users": CustomUserSerializer(recent_users, many=True).data,
        }
        return Response(payload)

class RegionalAdminDashboardView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated, HasPermission]
    module = "regional"
    required_action = "read"
    serializer_class = RegionalAdminDashboardResponseSerializer

    @extend_schema(
        summary="Regional admin dashboard",
        responses={200: RegionalAdminDashboardResponseSerializer},
    )
    def get(self, request):
        schools = School.objects.filter(
            users__user=request.user,  # UserRole.related_name on school is "users"
            users__is_active=True,
        ).distinct()
        return Response({
            "regional_admin": request.user.get_full_name(),
            "summary": {"total_schools": schools.count()},
            "schools": list(schools.values("id", "school_name", "county")[:30]),
            "note": "Managed counties logic will be improved once RegionalAdminProfile is created.",
        })