from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .api.viewsets import (
    DormitoryInspectionViewSet,
    DormitoryViewSet,
    RoomAllocationViewSet,
)

router = DefaultRouter()
router.register(r"dormitories", DormitoryViewSet, basename="dormitory")
router.register(r"inspections", DormitoryInspectionViewSet, basename="inspection")
router.register(r"allocations", RoomAllocationViewSet, basename="allocation")

urlpatterns = [
    path("", include(router.urls)),
]
