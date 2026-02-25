from rest_framework import serializers
from ..models import Dormitory, DormitoryInspection, RoomAllocation


class DormitorySerializer(serializers.ModelSerializer):
    """Serializer for Dormitory model."""
    
    school_name = serializers.CharField(source='school.name', read_only=True)
    school_code = serializers.CharField(source='school.code', read_only=True)
    prefect_name = serializers.CharField(source='prefect.user.get_full_name', read_only=True, allow_null=True)
    matron_name = serializers.CharField(source='matron.user.get_full_name', read_only=True, allow_null=True)
    occupancy_percentage = serializers.SerializerMethodField()
    
    class Meta:
        model = Dormitory
        fields = [
            'id',
            'school', 'school_name', 'school_code',
            'name',
            'dormitory_type',
            'capacity',
            'current_occupancy',
            'occupancy_percentage',
            'prefect', 'prefect_name',
            'matron', 'matron_name',
            'building',
            'floor',
            'rooms',
            'facilities',
            'rules',
            'curfew_time',
            'lights_out_time',
            'dormitory_status',
            'created_at'
        ]
        read_only_fields = ['current_occupancy', 'created_at']
    
    def get_occupancy_percentage(self, obj) -> float:
        """Calculate occupancy percentage."""
        if obj.capacity > 0:
            return round((obj.current_occupancy / obj.capacity) * 100, 1)
        return 0
    
    def validate(self, data):
        """Validate dormitory data."""
        
        # Check capacity vs occupancy
        capacity = data.get('capacity') or getattr(self.instance, 'capacity', 0)
        current_occupancy = getattr(self.instance, 'current_occupancy', 0) if self.instance else 0
        
        if capacity < current_occupancy:
            raise serializers.ValidationError(
                {"capacity": f"Capacity cannot be less than current occupancy ({current_occupancy})."}
            )
        
        # Validate prefect gender matches dormitory type
        prefect = data.get('prefect') or getattr(self.instance, 'prefect', None)
        dormitory_type = data.get('dormitory_type') or getattr(self.instance, 'dormitory_type', None)
        
        if prefect and dormitory_type:
            if dormitory_type == Dormitory.BOYS and prefect.gender != 'Male':
                raise serializers.ValidationError(
                    {"prefect": "Boys dormitory prefect must be a male student."}
                )
            elif dormitory_type == Dormitory.GIRLS and prefect.gender != 'Female':
                raise serializers.ValidationError(
                    {"prefect": "Girls dormitory prefect must be a female student."}
                )
        
        return data


class SimpleDormitorySerializer(serializers.ModelSerializer):
    """Simplified serializer for dormitory list."""
    
    occupancy_percentage = serializers.SerializerMethodField()
    
    class Meta:
        model = Dormitory
        fields = ['id', 'name', 'dormitory_type', 'capacity', 'current_occupancy', 'occupancy_percentage', 'dormitory_status']
    
    def get_occupancy_percentage(self, obj) -> float:
        if obj.capacity > 0:
            return round((obj.current_occupancy / obj.capacity) * 100, 1)
        return 0


class DormitoryInspectionSerializer(serializers.ModelSerializer):
    """Serializer for DormitoryInspection model."""
    
    dormitory_name = serializers.CharField(source='dormitory.name', read_only=True)
    inspected_by_name = serializers.CharField(source='inspected_by.get_full_name', read_only=True)
    average_score = serializers.SerializerMethodField()
    
    class Meta:
        model = DormitoryInspection
        fields = [
            'id',
            'dormitory', 'dormitory_name',
            'inspected_by', 'inspected_by_name',
            'inspection_date',
            'cleanliness_score',
            'orderliness_score',
            'safety_score',
            'average_score',
            'issues_found',
            'actions_taken',
            'follow_up_required',
            'follow_up_date',
            'next_inspection_date',
            'attachments',
            'created_at'
        ]
        read_only_fields = ['created_at']
    
    def validate(self, data):
        """Validate inspection data."""
        
        # Validate scores
        for field in ['cleanliness_score', 'orderliness_score', 'safety_score']:
            if field in data:
                score = data[field]
                if score < 1 or score > 10:
                    raise serializers.ValidationError(
                        {field: "Score must be between 1 and 10."}
                    )
        
        # Validate dates
        inspection_date = data.get('inspection_date')
        follow_up_date = data.get('follow_up_date')
        next_inspection_date = data.get('next_inspection_date')
        
        if follow_up_date and inspection_date and follow_up_date < inspection_date.date():
            raise serializers.ValidationError(
                {"follow_up_date": "Follow-up date cannot be before inspection date."}
            )
        
        if next_inspection_date and inspection_date and next_inspection_date <= inspection_date:
            raise serializers.ValidationError(
                {"next_inspection_date": "Next inspection date must be after inspection date."}
            )
        
        return data


class RoomAllocationSerializer(serializers.ModelSerializer):
    """Serializer for RoomAllocation model."""
    
    student_name = serializers.CharField(source='student.user.get_full_name', read_only=True)
    student_admission = serializers.CharField(source='student.admission_number', read_only=True)
    dormitory_name = serializers.CharField(source='dormitory.name', read_only=True)
    
    class Meta:
        model = RoomAllocation
        fields = [
            'id',
            'student', 'student_name', 'student_admission',
            'dormitory', 'dormitory_name',
            'room_number',
            'bed_number',
            'locker_number',
            'start_date',
            'end_date',
            'is_active',
            'notes',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']
    
    def validate(self, data):
        """Validate room allocation data."""
        
        student = data.get('student') or getattr(self.instance, 'student', None)
        dormitory = data.get('dormitory') or getattr(self.instance, 'dormitory', None)
        
        if student and dormitory:
            # Check if student gender matches dormitory type
            if dormitory.dormitory_type == Dormitory.BOYS and student.gender != 'Male':
                raise serializers.ValidationError(
                    {"student": "Male students can only be allocated to boys dormitories."}
                )
            elif dormitory.dormitory_type == Dormitory.GIRLS and student.gender != 'Female':
                raise serializers.ValidationError(
                    {"student": "Female students can only be allocated to girls dormitories."}
                )
            
            # Check if student belongs to dormitory's school
            if student.school != dormitory.school:
                raise serializers.ValidationError(
                    {"student": "Student must belong to the same school as the dormitory."}
                )
            
            # Check dormitory capacity
            if dormitory.current_occupancy >= dormitory.capacity:
                raise serializers.ValidationError(
                    {"dormitory": f"Dormitory '{dormitory.name}' is at full capacity."}
                )
        
        # Check if bed is already occupied
        dormitory = data.get('dormitory') or getattr(self.instance, 'dormitory', None)
        room_number = data.get('room_number') or getattr(self.instance, 'room_number', None)
        bed_number = data.get('bed_number') or getattr(self.instance, 'bed_number', None)
        
        if dormitory and room_number and bed_number:
            existing_allocation = RoomAllocation.objects.filter(
                dormitory=dormitory,
                room_number=room_number,
                bed_number=bed_number,
                is_active=True
            ).exclude(pk=getattr(self.instance, 'pk', None))
            
            if existing_allocation.exists():
                raise serializers.ValidationError(
                    {"bed_number": "This bed is already occupied."}
                )
        
        # Validate dates
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        
        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError(
                {"end_date": "End date must be after start date."}
            )
        
        return data


class DormitoryStatsSerializer(serializers.Serializer):
    """Serializer for dormitory statistics."""
    
    total_dormitories = serializers.IntegerField()
    total_capacity = serializers.IntegerField()
    total_occupied = serializers.IntegerField()
    occupancy_rate = serializers.FloatField()
    by_type = serializers.DictField()


class InspectionStatsSerializer(serializers.Serializer):
    """Serializer for inspection statistics."""
    
    total_inspections = serializers.IntegerField()
    avg_cleanliness_score = serializers.FloatField()
    avg_safety_score = serializers.FloatField()
    pending_follow_ups = serializers.IntegerField()
    inspections_by_month = serializers.DictField()