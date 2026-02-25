from rest_framework import viewsets, status, filters, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Count, Avg,Sum
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.conf import settings
from django.db.models import F  
from students.models import Student 

from ..models import Dormitory, DormitoryInspection, RoomAllocation
from .serializers import (
    DormitorySerializer,
    SimpleDormitorySerializer,
    DormitoryInspectionSerializer,
    RoomAllocationSerializer,
    DormitoryStatsSerializer,
    InspectionStatsSerializer
)
from students.models import Student


class DormitoryViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing Dormitories.
    
    Supports:
    - CRUD operations for dormitories
    - Filter by school, type, status
    - Get occupancy statistics
    - Allocate/deallocate students
    """
    queryset = Dormitory.objects.all()
    serializer_class = DormitorySerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['school', 'dormitory_type', 'dormitory_status']
    search_fields = ['name', 'building', 'rules']
    ordering_fields = ['name', 'capacity', 'current_occupancy']
    ordering = ['name']
    
    def get_queryset(self):
        """
        Users can see dormitories from their school.
        """
        user = self.request.user
        
        if user.is_superuser:
            return Dormitory.objects.all()
        
        if hasattr(user, 'staffprofile'):
            school = user.staffprofile.school
            return Dormitory.objects.filter(school=school)
        
        if hasattr(user, 'student'):
            school = user.student.school
            return Dormitory.objects.filter(school=school)
        
        return Dormitory.objects.none()
    
    @action(detail=True, methods=['get'])
    def occupants(self, request, pk=None):
        """Get all active occupants of a dormitory."""
        dormitory = self.get_object()
        occupants = RoomAllocation.objects.filter(
            dormitory=dormitory,
            is_active=True
        ).select_related('student')
        
        page = self.paginate_queryset(occupants)
        if page is not None:
            serializer = RoomAllocationSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = RoomAllocationSerializer(occupants, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def inspections(self, request, pk=None):
        """Get all inspections for a dormitory."""
        dormitory = self.get_object()
        inspections = DormitoryInspection.objects.filter(
            dormitory=dormitory
        ).order_by('-inspection_date')
        
        page = self.paginate_queryset(inspections)
        if page is not None:
            serializer = DormitoryInspectionSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = DormitoryInspectionSerializer(inspections, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def allocate_student(self, request, pk=None):
        """Allocate a student to this dormitory."""
        dormitory = self.get_object()
        student_id = request.data.get('student_id')
        room_number = request.data.get('room_number')
        bed_number = request.data.get('bed_number', '')
        
        if not student_id or not room_number:
            return Response(
                {"error": "student_id and room_number are required."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            student = Student.objects.get(id=student_id)
        except Student.DoesNotExist:
            return Response(
                {"error": "Student not found."},
                status=status.HTTP_404_NOT_FOUND
            )    
        # Check if student already has active allocation
        existing_allocation = RoomAllocation.objects.filter(
            student=student,
            is_active=True
        ).first()
        
        if existing_allocation:
            return Response(
                {"error": f"Student already allocated to {existing_allocation.dormitory.name} Room {existing_allocation.room_number}."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if bed is available
        if bed_number:
            bed_taken = RoomAllocation.objects.filter(
                dormitory=dormitory,
                room_number=room_number,
                bed_number=bed_number,
                is_active=True
            ).exists()
            
            if bed_taken:
                return Response(
                    {"error": f"Bed {bed_number} in Room {room_number} is already occupied."},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Create allocation
        allocation = RoomAllocation.objects.create(
            student=student,
            dormitory=dormitory,
            room_number=room_number,
            bed_number=bed_number,
            start_date=request.data.get('start_date') or timezone.now().date(),
            locker_number=request.data.get('locker_number', ''),
            notes=request.data.get('notes', '')
        )
        serializer = RoomAllocationSerializer(allocation)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=False, methods=['get'])
    def available_beds(self, request):
        """Get dormitories with available beds."""
        school_id = request.query_params.get('school_id')
        dormitory_type = request.query_params.get('dormitory_type')
        
        queryset = self.get_queryset().filter(
            dormitory_status=Dormitory.OPEN,
            current_occupancy__lt=F('capacity')  # Use F object
        )
        if school_id:
            queryset = queryset.filter(school_id=school_id)
        
        if dormitory_type:
            queryset = queryset.filter(dormitory_type=dormitory_type)
        results = []
        for dorm in queryset:
            available_beds = dorm.capacity - dorm.current_occupancy
            results.append({
                'id': dorm.id,
                'name': dorm.name,
                'type': dorm.dormitory_type,
                'capacity': dorm.capacity,
                'occupied': dorm.current_occupancy,
                'available': available_beds,
                'rooms': dorm.rooms
            })
        
        return Response(results)
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get dormitory statistics."""
        queryset = self.get_queryset()
        
        total_capacity = queryset.aggregate(total=Sum('capacity'))['total'] or 0
        total_occupied = queryset.aggregate(total=Sum('current_occupancy'))['total'] or 0
        occupancy_rate = (total_occupied / total_capacity * 100) if total_capacity > 0 else 0
        
        stats = {
            'total_dormitories': queryset.count(),
            'total_capacity': total_capacity,
            'total_occupied': total_occupied,
            'occupancy_rate': round(occupancy_rate, 1),
            'by_type': dict(
                queryset.values('dormitory_type').annotate(
                    count=Count('id'),
                    capacity=Sum('capacity'),
                    occupied=Sum('current_occupancy')
                ).values_list('dormitory_type', 'count')
            )
        }
        
        serializer = DormitoryStatsSerializer(stats)
        return Response(serializer.data)
    
    @action(detail=True, methods=['patch'])
    def update_capacity(self, request, pk=None):
        """Update dormitory capacity."""
        dormitory = self.get_object()
        new_capacity = request.data.get('capacity')
        
        if new_capacity is None:
            return Response(
                {"error": "capacity is required."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            new_capacity = int(new_capacity)
            if new_capacity < dormitory.current_occupancy:
                return Response(
                    {"error": f"Capacity cannot be less than current occupancy ({dormitory.current_occupancy})."},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except (ValueError, TypeError):
            return Response(
                {"error": "capacity must be a valid integer."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        dormitory.capacity = new_capacity
        dormitory.save()
        
        serializer = self.get_serializer(dormitory)
        return Response(serializer.data)


class DormitoryInspectionViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing Dormitory Inspections.
    
    Supports:
    - CRUD operations for inspections
    - Record inspection scores and issues
    - Schedule follow-ups
    - Generate inspection reports
    """
    queryset = DormitoryInspection.objects.all()
    serializer_class = DormitoryInspectionSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['dormitory', 'follow_up_required', 'inspected_by']
    search_fields = ['actions_taken', 'issues_found']
    ordering_fields = ['inspection_date', 'cleanliness_score']
    ordering = ['-inspection_date']
    
    def get_queryset(self):
        """
        Users can see inspections for their school's dormitories.
        """
        user = self.request.user
        
        if user.is_superuser:
            return DormitoryInspection.objects.all()
        
        if hasattr(user, 'staffprofile'):
            school = user.staffprofile.school
            return DormitoryInspection.objects.filter(
                dormitory__school=school
            )
        
        # If user is a student, they shouldn't see inspections
        # Staff can see inspections they conducted
        if hasattr(user, 'student'):
            return DormitoryInspection.objects.none()
        
        # Default: only inspections conducted by user
        return DormitoryInspection.objects.filter(inspected_by=user)
    
    def perform_create(self, serializer):
        """Set inspected_by to current user."""
        serializer.save(inspected_by=self.request.user)
    
    @action(detail=True, methods=['post'])
    def add_issue(self, request, pk=None):
        """Add an issue to inspection."""
        inspection = self.get_object()
        issue = request.data.get('issue')
        
        if not issue:
            return Response(
                {"error": "issue is required."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if inspection.issues_found is None:
            inspection.issues_found = []
        
        inspection.issues_found.append({
            'issue': issue,
            'added_by': str(request.user.id),
            'added_at': timezone.now().isoformat()
        })
        
        inspection.follow_up_required = True
        inspection.save()
        
        serializer = self.get_serializer(inspection)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def add_attachment(self, request, pk=None):
        """Add attachment (photo) to inspection."""
        inspection = self.get_object()
        attachment = request.data.get('attachment')
        
        if not attachment:
            return Response(
                {"error": "attachment is required."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if inspection.attachments is None:
            inspection.attachments = []
        
        inspection.attachments.append({
            'url': attachment,
            'caption': request.data.get('caption', ''),
            'uploaded_by': str(request.user.id),
            'uploaded_at': timezone.now().isoformat()
        })
        
        inspection.save()
        
        serializer = self.get_serializer(inspection)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def pending_followups(self, request):
        """Get inspections requiring follow-up."""
        queryset = self.get_queryset().filter(
            follow_up_required=True
        ).order_by('follow_up_date', 'inspection_date')
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def overdue_followups(self, request):
        """Get overdue follow-up inspections."""
        today = timezone.now().date()
        queryset = self.get_queryset().filter(
            follow_up_required=True,
            follow_up_date__lt=today
        ).order_by('follow_up_date')
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get inspection statistics."""
        queryset = self.get_queryset()
        
        # Group by month for chart data
        from django.db.models.functions import TruncMonth
        inspections_by_month = queryset.annotate(
            month=TruncMonth('inspection_date')
        ).values('month').annotate(
            count=Count('id')
        ).order_by('month')
        
        # Convert to dictionary
        monthly_data = {}
        for item in inspections_by_month:
            month_str = item['month'].strftime('%Y-%m')
            monthly_data[month_str] = item['count']
        
        stats = {
            'total_inspections': queryset.count(),
            'avg_cleanliness_score': queryset.aggregate(
                avg=Avg('cleanliness_score')
            )['avg'] or 0,
            'avg_safety_score': queryset.aggregate(
                avg=Avg('safety_score')
            )['avg'] or 0,
            'pending_follow_ups': queryset.filter(follow_up_required=True).count(),
            'inspections_by_month': monthly_data
        }
        
        serializer = InspectionStatsSerializer(stats)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def complete_followup(self, request, pk=None):
        """Mark follow-up as completed."""
        inspection = self.get_object()
        actions_taken = request.data.get('actions_taken', '')
        
        if not inspection.follow_up_required:
            return Response(
                {"detail": "This inspection does not require follow-up."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        inspection.follow_up_required = False
        if actions_taken:
            inspection.actions_taken = actions_taken
        inspection.save()
        
        serializer = self.get_serializer(inspection)
        return Response(serializer.data)


class RoomAllocationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing Room Allocations.
    
    Supports:
    - CRUD operations for room allocations
    - Move students between rooms/dormitories
    - Check-in/check-out students
    - Generate occupancy reports
    """
    queryset = RoomAllocation.objects.all()
    serializer_class = RoomAllocationSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['dormitory', 'is_active', 'student']
    search_fields = ['room_number', 'bed_number', 'student__admission_number']
    
    def get_queryset(self):
        """
        Users can see allocations:
        - For their school's dormitories
        - For their own allocation (if student)
        """
        user = self.request.user
        
        if user.is_superuser:
            return RoomAllocation.objects.all()
        
        queryset = RoomAllocation.objects.none()
        
        # If user is staff, show allocations from their school
        if hasattr(user, 'staffprofile'):
            school = user.staffprofile.school
            queryset = RoomAllocation.objects.filter(
                dormitory__school=school
            )
        
        # If user is student, show their own allocation
        if hasattr(user, 'student'):
            queryset = queryset | RoomAllocation.objects.filter(
                student=user.student
            )
        
        return queryset.distinct()
    
    @action(detail=True, methods=['post'])
    def check_out(self, request, pk=None):
        """Check out a student from dormitory (end allocation)."""
        allocation = self.get_object()
        
        if not allocation.is_active:
            return Response(
                {"detail": "Allocation is already inactive."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        allocation.is_active = False
        allocation.end_date = timezone.now().date()
        allocation.save()
        
        serializer = self.get_serializer(allocation)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def move_room(self, request, pk=None):
        """Move student to a different room/bed."""
        allocation = self.get_object()
        new_room = request.data.get('room_number')
        new_bed = request.data.get('bed_number', '')
        
        if not new_room:
            return Response(
                {"error": "room_number is required."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # End current allocation
        allocation.is_active = False
        allocation.end_date = timezone.now().date()
        allocation.save()
        
        # Create new allocation
        new_allocation = RoomAllocation.objects.create(
            student=allocation.student,
            dormitory=allocation.dormitory,
            room_number=new_room,
            bed_number=new_bed,
            start_date=timezone.now().date(),
            locker_number=request.data.get('locker_number', allocation.locker_number),
            notes=f"Moved from Room {allocation.room_number} Bed {allocation.bed_number}. {request.data.get('notes', '')}"
        )
        
        serializer = RoomAllocationSerializer(new_allocation)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def available_rooms(self, request):
        """Get available rooms in a dormitory."""
        dormitory_id = request.query_params.get('dormitory_id')
        
        if not dormitory_id:
            return Response(
                {"error": "dormitory_id is required."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            dormitory = Dormitory.objects.get(id=dormitory_id)
        except Dormitory.DoesNotExist:
            return Response(
                {"error": "Dormitory not found."},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get occupied beds
        occupied = RoomAllocation.objects.filter(
            dormitory=dormitory,
            is_active=True
        ).values_list('room_number', 'bed_number')
        
        # Parse rooms data from JSON
        available_rooms = []
        if dormitory.rooms:
            for room in dormitory.rooms:
                room_number = room.get('number', '')
                beds = room.get('beds', [])
                
                for bed in beds:
                    bed_number = bed.get('number', '')
                    
                    # Check if bed is occupied
                    is_occupied = any(
                        occ[0] == room_number and occ[1] == bed_number 
                        for occ in occupied
                    )
                    
                    if not is_occupied:
                        available_rooms.append({
                            'room_number': room_number,
                            'bed_number': bed_number,
                            'bed_type': bed.get('type', ''),
                            'room_type': room.get('type', '')
                        })
        
        return Response(available_rooms)
    
    @action(detail=False, methods=['get'])
    def student_history(self, request):
        """Get room allocation history for a student."""
        student_id = request.query_params.get('student_id')
        
        if not student_id:
            return Response(
                {"error": "student_id is required."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        allocations = RoomAllocation.objects.filter(
            student_id=student_id
        ).order_by('-start_date')
        
        page = self.paginate_queryset(allocations)
        if page is not None:
            serializer = RoomAllocationSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = RoomAllocationSerializer(allocations, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def room_occupancy(self, request):
        """Get room occupancy report."""
        dormitory_id = request.query_params.get('dormitory_id')
        
        queryset = self.get_queryset().filter(is_active=True)
        
        if dormitory_id:
            queryset = queryset.filter(dormitory_id=dormitory_id)
        
        # Group by room
        from collections import defaultdict
        room_data = defaultdict(list)
        
        for allocation in queryset.select_related('student'):
            room_data[allocation.room_number].append({
                'student': allocation.student.user.get_full_name(),
                'admission_number': allocation.student.admission_number,
                'bed': allocation.bed_number,
                'locker': allocation.locker_number,
                'start_date': allocation.start_date
            })
        
        return Response(room_data)