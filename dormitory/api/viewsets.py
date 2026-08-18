from django.db.models import F, Q
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from ..models import Dormitory, DormitoryInspection, RoomAllocation
from .serializers import (
    DormitoryDetailSerializer,
    DormitoryInspectionSerializer,
    DormitoryListSerializer,
    RoomAllocationSerializer,
)


class DormitoryViewSet(viewsets.ModelViewSet):
    queryset = Dormitory.objects.select_related("school", "prefect", "matron")
    permission_classes = [IsAuthenticated]

    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["dorm_type", "dorm_status"]

    def get_serializer_class(self):
        if self.action == "list":
            return DormitoryListSerializer
        return DormitoryDetailSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Dormitory.objects.none()

        user = self.request.user
        if hasattr(user, "school") and user.school:
            return Dormitory.objects.filter(school=user.school)

        return Dormitory.objects.none()

    @action(detail=True, methods=["get"])
    def occupants(self, request, pk=None):
        allocs = RoomAllocation.objects.filter(dormitory=self.get_object(), is_active=True)
        return Response(RoomAllocationSerializer(allocs, many=True).data)

    @action(detail=True, methods=["post"])
    def allocate(self, request, pk=None):
        dorm = self.get_object()
        student_id = request.data.get("student_id")
        room = request.data.get("room_number")
        bed = request.data.get("bed_number", "")

        if not student_id or not room:
            return Response(
                {"error": "student_id and room_number required"}, status=400
            )

        student = get_object_or_404(StudentProfile, id=student_id, school=dorm.school)
        if RoomAllocation.objects.filter(student=student, is_active=True).exists():
            return Response({"error": "Student already allocated"}, status=400)

        if dorm.current_occupancy >= dorm.capacity:
            return Response({"error": "Dormitory full"}, status=400)

        allocation = RoomAllocation.objects.create(student=student,
            dormitory=dorm,room_number=room,bed_number=bed,
            start_date=timezone.now().date(),
            **{
                k: v for k, v in request.data.items() if k in ["locker_number", "notes"]
            },
        )

        return Response(RoomAllocationSerializer(allocation).data, status=201)


class DormitoryInspectionViewSet(viewsets.ModelViewSet):
    queryset = DormitoryInspection.objects.select_related("dormitory", "inspected_by")
    serializer_class = DormitoryInspectionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return DormitoryInspection.objects.filter(dormitory__school=self.request.school)

    def perform_create(self, serializer):
        serializer.save(inspected_by=self.request.user)


class RoomAllocationViewSet(viewsets.ModelViewSet):
    queryset = RoomAllocation.objects.select_related("student", "dormitory")
    serializer_class = RoomAllocationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return RoomAllocation.objects.filter(dormitory__school=self.request.school)

    @action(detail=True, methods=["post"])
    def checkout(self, request, pk=None):
        alloc = self.get_object()
        if not alloc.is_active:
            return Response({"detail": "Already checked out"}, status=400)

        alloc.is_active = False
        alloc.end_date = timezone.now().date()
        alloc.save()
        return Response(self.get_serializer(alloc).data)
