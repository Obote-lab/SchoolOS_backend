from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.api.permissions import HasPermission
from schools.models import School

from ..models import BrandingChangeLog, SchoolBranding, SystemBranding, ThemePreset
from .serializers import (
    ApplyPresetSerializer,
    BrandingChangeLogSerializer,
    ResolvedBrandingSerializer,
    SchoolBrandingSerializer,
    SchoolBrandingUpdateSerializer,
    SystemBrandingSerializer,
    SystemBrandingUpdateSerializer,
    ThemePresetSerializer,
)
from ..services import BrandingService



# Resolved branding — the only endpoint most clients need

class ResolvedBrandingView(APIView):
    """
    GET /api/v1/branding/resolved/

    - Unauthenticated: system branding only (login page, public surfaces)
    - Authenticated + school context: system + school overlay
    - Optional ?school_id= for explicit school (Root / cross-school tools)
    """

    permission_classes = [AllowAny]
    serializer_class = ResolvedBrandingSerializer

    @extend_schema(
        summary="Resolved branding payload",
        responses={200: ResolvedBrandingSerializer},
        tags=["Branding"],
    )
    def get(self, request):
        school = getattr(request, "school", None)

        school_id = request.query_params.get("school_id")
        if school_id:
            if not request.user.is_authenticated:
                return Response(
                    {"detail": "Authentication required for school_id override."},
                    status=status.HTTP_401_UNAUTHORIZED,
                )
            school = get_object_or_404(School, pk=school_id)

        payload = BrandingService.get_resolved(school=school, request=request)
        serializer = ResolvedBrandingSerializer(payload)
        return Response(serializer.data)



# System branding (Root only)
@extend_schema_view(
    list=extend_schema(tags=["Branding – System"]),
    retrieve=extend_schema(tags=["Branding – System"]),
)
class SystemBrandingViewSet(viewsets.GenericViewSet):
    """
    Root-only management of platform branding & mode.
    """

    permission_classes = [IsAuthenticated, HasPermission]
    module = "branding"
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    queryset = SystemBranding.objects.all()

    def get_permissions(self):
        self.required_action = (
            "update" if self.action in {"update", "partial_update", "set_mode"} else "read"
        )
        return super().get_permissions()

    def get_serializer_class(self):
        if self.action in {"update", "partial_update"}:
            return SystemBrandingUpdateSerializer
        return SystemBrandingSerializer

    @extend_schema(summary="Get current system branding", tags=["Branding – System"])
    def list(self, request):
        system = SystemBranding.get_solo()
        return Response(SystemBrandingSerializer(system, context={"request": request}).data)

    @extend_schema(summary="Get system branding by id", tags=["Branding – System"])
    def retrieve(self, request, pk=None):
        system = get_object_or_404(SystemBranding, pk=pk)
        return Response(SystemBrandingSerializer(system, context={"request": request}).data)

    @extend_schema(
        summary="Update system branding",
        request=SystemBrandingUpdateSerializer,
        responses={200: SystemBrandingSerializer},
        tags=["Branding – System"],
    )
    def partial_update(self, request, pk=None):
        # pk ignored — always operate on solo active record
        serializer = SystemBrandingUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        files = {
            k: request.FILES[k]
            for k in (
                "logo_light",
                "logo_dark",
                "logo_square",
                "favicon",
                "mode_logo_light",
                "mode_logo_dark",
                "login_background",
            )
            if k in request.FILES
        }

        system = BrandingService.update_system(
            actor=request.user,
            data=serializer.validated_data,
            files=files,
            request=request,
        )
        return Response(
            SystemBrandingSerializer(system, context={"request": request}).data
        )

    @extend_schema(
        summary="Set platform mode (exam_season, maintenance, …)",
        tags=["Branding – System"],
    )
    @action(detail=False, methods=["post"], url_path="set-mode")
    def set_mode(self, request):
        mode = request.data.get("mode")
        mode_label = request.data.get("mode_label", "")
        if not mode:
            return Response({"mode": "This field is required."}, status=400)

        system = BrandingService.update_system(
            actor=request.user,
            data={"mode": mode, "mode_label": mode_label},
            request=request,
        )
        return Response(
            SystemBrandingSerializer(system, context={"request": request}).data
        )



# School branding

@extend_schema_view(
    retrieve=extend_schema(tags=["Branding – School"]),
    partial_update=extend_schema(tags=["Branding – School"]),
)
class SchoolBrandingViewSet(viewsets.GenericViewSet):
    """
    Principal / school-admin management of own school branding.
    pk = school_id.
    """

    permission_classes = [IsAuthenticated, HasPermission]
    module = "branding"
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    queryset = SchoolBranding.objects.select_related("school", "updated_by")
    serializer_class = SchoolBrandingSerializer

    def get_permissions(self):
        self.required_action = (
            "update" if self.action in {"partial_update", "apply_preset"} else "read"
        )
        return super().get_permissions()

    def get_serializer_class(self):
        if self.action in {"partial_update", "update"}:
            return SchoolBrandingUpdateSerializer
        if self.action == "apply_preset":
            return ApplyPresetSerializer
        return SchoolBrandingSerializer

    def _get_school(self, request, school_id=None):
        if school_id:
            return get_object_or_404(School, pk=school_id)
        school = getattr(request, "school", None)
        if not school:
            return Response(
                {"detail": "School context required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return school

    @extend_schema(summary="Get branding for a school", tags=["Branding – School"])
    def retrieve(self, request, pk=None):
        """pk = school_id"""
        school = get_object_or_404(School, pk=pk)
        branding, _ = SchoolBranding.objects.get_or_create(school=school)
        return Response(
            SchoolBrandingSerializer(branding, context={"request": request}).data
        )

    @extend_schema(
        summary="Update school branding",
        request=SchoolBrandingUpdateSerializer,
        responses={200: SchoolBrandingSerializer},
        tags=["Branding – School"],
    )
    def partial_update(self, request, pk=None):
        school = get_object_or_404(School, pk=pk)
        serializer = SchoolBrandingUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        files = {
            k: request.FILES[k]
            for k in ("logo_light", "logo_dark", "logo_square", "favicon")
            if k in request.FILES
        }

        branding = BrandingService.update_school(
            actor=request.user,
            school=school,
            data=serializer.validated_data,
            files=files,
            request=request,
        )
        return Response(
            SchoolBrandingSerializer(branding, context={"request": request}).data
        )

    @extend_schema(
        summary="Apply a theme preset to this school",
        request=ApplyPresetSerializer,
        tags=["Branding – School"],
    )
    @action(detail=True, methods=["post"], url_path="apply-preset")
    def apply_preset(self, request, pk=None):
        school = get_object_or_404(School, pk=pk)
        ser = ApplyPresetSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        preset = get_object_or_404(ThemePreset, pk=ser.validated_data["preset_id"])

        branding = BrandingService.apply_preset_to_school(
            actor=request.user,
            school=school,
            preset=preset,
            request=request,
        )
        return Response(
            SchoolBrandingSerializer(branding, context={"request": request}).data
        )



# Theme presets (Root manages; schools read public ones)
class ThemePresetViewSet(viewsets.ModelViewSet):
    serializer_class = ThemePresetSerializer
    permission_classes = [IsAuthenticated, HasPermission]
    module = "branding"
    lookup_field = "slug"

    def get_queryset(self):
        qs = ThemePreset.objects.filter(is_active=True)
        user = self.request.user
        if not (user.is_superuser or BrandingService._actor_is_root(user)):
            qs = qs.filter(is_public=True)
        return qs

    def get_permissions(self):
        if self.action in {"create", "update", "partial_update", "destroy"}:
            self.required_action = "update"
        else:
            self.required_action = "read"
        return super().get_permissions()



# Change log (read-only timeline)

class BrandingChangeLogViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = BrandingChangeLogSerializer
    permission_classes = [IsAuthenticated, HasPermission]
    module = "branding"
    required_action = "read"

    def get_queryset(self):
        qs = BrandingChangeLog.objects.select_related("actor", "school")
        school = getattr(self.request, "school", None)
        if school and not self.request.user.is_superuser:
            qs = qs.filter(school=school) | qs.filter(scope="system")
        return qs