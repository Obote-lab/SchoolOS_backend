from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from ..models import Dormitory, DormitoryInspection, RoomAllocation
from  core.choices.dormitory import DormTypeChoices
from core.choices.common import GenderChoices

class DormitoryListSerializer(serializers.ModelSerializer):
    occupancy_percentage = serializers.SerializerMethodField()
    prefect_name = serializers.CharField(source="prefect.user.get_full_name", read_only=True, allow_null=True)
    matron_name = serializers.CharField(source="matron.user.get_full_name", read_only=True, allow_null=True)

    class Meta:
        model = Dormitory
        fields = [
            "id", "name", "dorm_type", "capacity", "current_occupancy",
            "occupancy_percentage", "dorm_status", "prefect_name", "matron_name",
        ]

    @extend_schema_field(serializers.FloatField)
    def get_occupancy_percentage(self, obj) -> float:
        return round(obj.current_occupancy / obj.capacity * 100, 1) if obj.capacity else 0


class DormitoryDetailSerializer(serializers.ModelSerializer):
    prefect_name = serializers.CharField(source="prefect.user.get_full_name",read_only=True,allow_null=True,)
    matron_name = serializers.CharField(source="matron.user.get_full_name",read_only=True,allow_null=True,)
    occupancy_percentage = serializers.SerializerMethodField()

    class Meta:
        model = Dormitory
        fields = "__all__"
        read_only_fields = [
            "current_occupancy",
            "created_at",
            "updated_at",
        ]

    @extend_schema_field(serializers.FloatField)
    def get_occupancy_percentage(self, obj) -> float:
        if not obj.capacity:
            return 0

        return round((obj.current_occupancy / obj.capacity) * 100,2,)

class DormitoryInspectionSerializer(serializers.ModelSerializer):
    dormitory_name = serializers.CharField(source="dormitory.name", read_only=True)
    inspected_by_name = serializers.CharField(source="inspected_by.get_full_name", read_only=True, allow_null=True)

    # FIXED: Use FloatField instead of ReadOnlyField
    average_score = serializers.FloatField(read_only=True)

    class Meta:
        model = DormitoryInspection
        fields = "__all__"
        read_only_fields = ["created_at", "average_score"]

    def create(self, validated_data):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            validated_data["inspected_by"] = request.user
        return super().create(validated_data)


class RoomAllocationSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.user.get_full_name", read_only=True)
    student_admission = serializers.CharField(source="student.admission_number", read_only=True)
    dormitory_name = serializers.CharField(source="dormitory.name", read_only=True)

    class Meta:
        model = RoomAllocation
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at"]

    def validate(self, data):
        student = data.get("student") or getattr(self.instance, "student", None)
        dorm = data.get("dormitory") or getattr(self.instance, "dormitory", None)

        if student and dorm:
            # if student.school != dorm.school:
            if student.school_id != dorm.school_id:
                raise serializers.ValidationError("Student must belong to the dormitory's school.")
            if dorm.dorm_type == DormTypeChoices.BOYS and student.gender not in GenderChoices.MALE:
                raise serializers.ValidationError("Boys dormitory only for male students.")
            if dorm.dorm_type == DormTypeChoices.GIRLS and student.gender not in GenderChoices.FEMALE:
                raise serializers.ValidationError("Girls dormitory only for female students.")


            if dorm and (data.get("is_active", True)):
                if dorm.current_occupancy >= dorm.capacity:
                    # if updating existing active row, skip or recount excluding self
                    raise serializers.ValidationError(
                        {"dormitory": "Dormitory is at capacity."}
                    )

        return data
