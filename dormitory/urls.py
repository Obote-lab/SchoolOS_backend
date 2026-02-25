# dormitory/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .api.viewsets import (
    DormitoryViewSet,
    DormitoryInspectionViewSet,
    RoomAllocationViewSet
)

# Create router and register viewsets
router = DefaultRouter()
router.register(r'dormitories', DormitoryViewSet, basename='dormitory')
router.register(r'inspections', DormitoryInspectionViewSet, basename='inspection')
router.register(r'allocations', RoomAllocationViewSet, basename='allocation')

urlpatterns = [
    path('', include(router.urls)),
]

app_name = 'dormitory'