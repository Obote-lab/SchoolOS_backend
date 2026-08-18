from django.conf import settings
from rest_framework import serializers
from ..models import Announcement, Feedback, Notification, ParentTeacherMeeting
from core.choices.communications import FeedbackTypeChoices

class NotificationSerializer(serializers.ModelSerializer):
    """Serializer for Notification model."""

    user_name = serializers.CharField(source="user.get_full_name", read_only=True)
    sender_name = serializers.CharField(
        source="sender.get_full_name", read_only=True, allow_null=True
    )

    class Meta:
        model = Notification
        fields = [
            "id",
            "notification_id",
            "user",
            "user_name",
            "sender",
            "sender_name",
            "notification_category",
            "priority",
            "title",
            "message",
            "action_url",
            "channels",
            "delivery_status",
            "read_at",
            "acknowledged_at",
            "acknowledgement_action",
            "expires_at",
            "created_at",
        ]
        read_only_fields = ["notification_id", "created_at"]

    def validate(self, data):
        """Custom validation for Notification."""

        # Validate that user and sender belong to same school if both provided
        user = data.get("user") or getattr(self.instance, "user", None)
        sender = data.get("sender") or getattr(self.instance, "sender", None)

        if user and sender:
            if hasattr(user, "student_profile") and hasattr(sender, "staff_profile"):
                if user.student_profile.school != sender.staff_profile.school:
                    raise serializers.ValidationError(
                        "User and sender must belong to the same school."
                    )

        return data

    def update(self, instance, validated_data):
        from django.utils import timezone

        if "acknowledgement_action" in validated_data:
            now = timezone.now()
            validated_data.setdefault("read_at", now)
            validated_data.setdefault("acknowledged_at", now)

        return super().update(instance, validated_data)

class SimpleNotificationSerializer(serializers.ModelSerializer):
    """Simplified serializer for notifications list."""

    class Meta:
        model = Notification
        fields = [
            "id",
            "notification_id",
            "title",
            "notification_category",
            "priority",
            "read_at",
            "created_at",
        ]


class FeedbackSerializer(serializers.ModelSerializer):
    """Serializer for Feedback model."""

    submitted_by_name = serializers.CharField(source="submitted_by.get_full_name", read_only=True)
    assigned_to_name = serializers.CharField( source="assigned_to.get_full_name", read_only=True, allow_null=True)
    resolved_by_name = serializers.CharField(source="resolved_by.get_full_name", read_only=True, allow_null=True)
    student_name = serializers.CharField(source="related_to_student.user.get_full_name", read_only=True, allow_null=True)
    staff_name = serializers.CharField(source="related_to_staff.user.get_full_name", read_only=True, allow_null=True)

    class Meta:
        model = Feedback
        fields = [
            "id","resolved_by","resolved_at",
            "feedback_type","user_followup_feedback",
            "submitted_by_name","escalation_path",
            "submitted_by","created_at","updated_at",
            "assigned_to_name",
            "assigned_to",
            "resolved_by_name",
            "resolved_by",
            "related_to_student",
            "student_name",
            "related_to_staff",
            "staff_name",
            "user_rating",
            "title",
            "message",
            "attachments",
            "anonymous",
            "contact_allowed",
            "priority",
            "feedback_status",
            "resolution",]
        read_only_fields = ["created_at", "updated_at"]

    def validate(self, data):
        """Custom validation for Feedback."""

        # Validate that at least one related entity is provided for complaints/reports
        feedback_type = data.get("feedback_type") or getattr(
            self.instance, "feedback_type", None
        )

        if feedback_type in [FeedbackTypeChoices.COMPLAINT, FeedbackTypeChoices.REPORT]:
            related_student = data.get("related_to_student") or getattr(
                self.instance, "related_to_student", None
            )
            related_staff = data.get("related_to_staff") or getattr(
                self.instance, "related_to_staff", None
            )

            if not related_student and not related_staff:
                raise serializers.ValidationError(
                    "Complaints and reports must be related to a student or staff member."
                )

        # Validate user_rating range
        user_rating = data.get("user_rating")
        if user_rating is not None and (user_rating < 1 or user_rating > 5):
            raise serializers.ValidationError(
                {"user_rating": "Rating must be between 1 and 5."}
            )

        return data

    def create(self, validated_data):
        """Set submitted_by to current user if not provided."""

        if "submitted_by" not in validated_data:
            validated_data["submitted_by"] = self.context["request"].user

        return super().create(validated_data)


class AnnouncementSerializer(serializers.ModelSerializer):
    """Serializer for Announcement model."""

    school_name = serializers.CharField(source="school.school_name", read_only=True)
    created_by_name = serializers.CharField(
        source="created_by.get_full_name", read_only=True
    )
    approved_by_name = serializers.CharField(
        source="approved_by.get_full_name", read_only=True, allow_null=True
    )

    class Meta:
        model = Announcement
        fields = [
            "id",
            "school",
            "school_name",
            "title",
            "content",
            "announcement_category",
            "priority",
            "target_audience",
            "publish_date",
            "expiry_date",
            "requires_acknowledgment",
            "acknowledgment_count",
            "created_by",
            "created_by_name",
            "approved_by",
            "approved_by_name",
            "attachments",
            "channels",
            "announcement_status",
            "created_at",
        ]
        read_only_fields = ["acknowledgment_count", "created_at"]

    def validate(self, data):
        """Custom validation for Announcement."""

        # Validate dates
        publish_date = data.get("publish_date")
        expiry_date = data.get("expiry_date")

        if publish_date and expiry_date and expiry_date <= publish_date:
            raise serializers.ValidationError(
                {"expiry_date": "Expiry date must be after publish date."}
            )

        # Validate that creator belongs to the school
        school = data.get("school") or getattr(self.instance, "school", None)
        created_by = data.get("created_by") or getattr(
            self.instance, "created_by", None
        )

        if school and created_by:
            if hasattr(created_by, "staff_profile"):
                if created_by.staff_profile.school != school:
                    raise serializers.ValidationError(
                        "Announcement creator must belong to the announcement's school."
                    )
            elif hasattr(created_by, "student_profile"):
                if created_by.student_profile.school != school:
                    raise serializers.ValidationError(
                        "Announcement creator must belong to the announcement's school."
                    )

        return data

    def create(self, validated_data):
        """Set created_by to current user if not provided."""

        if "created_by" not in validated_data:
            validated_data["created_by"] = self.context["request"].user

        return super().create(validated_data)


class ParentTeacherMeetingSerializer(serializers.ModelSerializer):
    """Serializer for ParentTeacherMeeting model."""

    school_name = serializers.CharField(source="school.school_name", read_only=True)
    organizer_name = serializers.CharField(
        source="organizer.get_full_name", read_only=True
    )

    class Meta:
        model = ParentTeacherMeeting
        fields = [
            "id",
            "school",
            "school_name",
            "title",
            "purpose",
            "date",
            "start_time",
            "end_time",
            "venue",
            "organizer",
            "organizer_name",
            "invitees",
            "agenda",
            "minutes",
            "decisions",
            "action_items",
            "follow_up_date",
            "meeting_status",
            "attendance",
            "created_at",
        ]
        read_only_fields = ["created_at"]

    def validate(self, data):
        """Custom validation for ParentTeacherMeeting."""

        # Validate time
        start_time = data.get("start_time")
        end_time = data.get("end_time")

        if start_time and end_time and end_time <= start_time:
            raise serializers.ValidationError(
                {"end_time": "End time must be after start time."}
            )

        # Validate follow_up_date is after meeting date
        date = data.get("date")
        follow_up_date = data.get("follow_up_date")

        if date and follow_up_date and follow_up_date < date:
            raise serializers.ValidationError(
                {"follow_up_date": "Follow-up date cannot be before meeting date."}
            )

        # Validate that organizer belongs to the school
        school = data.get("school") or getattr(self.instance, "school", None)
        organizer = data.get("organizer") or getattr(self.instance, "organizer", None)

        if school and organizer:
            if hasattr(organizer, "staff_profile"):
                if organizer.staff_profile.school != school:
                    raise serializers.ValidationError(
                        "Meeting organizer must belong to the meeting's school."
                    )

        return data

    def create(self, validated_data):
        """Set organizer to current user if not provided."""

        if "organizer" not in validated_data:
            validated_data["organizer"] = self.context["request"].user

        return super().create(validated_data)


class UnreadNotificationCountSerializer(serializers.Serializer):
    """Serializer for unread notification count."""

    count = serializers.IntegerField()
    high_priority = serializers.IntegerField()
    categories = serializers.DictField()


class FeedbackStatsSerializer(serializers.Serializer):
    """Serializer for feedback statistics."""

    total = serializers.IntegerField()
    resolved = serializers.IntegerField()
    pending = serializers.IntegerField()
    avg_resolution_time_hours = serializers.FloatField()
    avg_rating = serializers.FloatField()
    by_category = serializers.DictField()
    by_type = serializers.DictField()
