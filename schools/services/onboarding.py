import logging
from datetime import datetime, timedelta
from django.db import transaction
from django.utils import timezone
from accounts.services.user_creation_services import UserCreationService
from core.choices.schools import OnboardingStatusChoices, SchoolTypeChoices
from schools.models import AcademicYear, ClassRoom, School

logger = logging.getLogger(__name__)


class SchoolOnboardingService:
    """
    Complete School Onboarding Service.
    """

    @staticmethod
    def _can_create_school(creator) -> bool:
        """
        Only superusers or users with Regional Admin / System-level roles
        can create schools.
        """
        if creator.is_superuser:
            return True

        return creator.user_roles.filter(
            is_active=True,
            role__name__in=["Regional Admin", "System Root", "County Admin"],
        ).exists()

    @staticmethod
    @transaction.atomic
    def create_school_with_principal(school_data: dict, principal_data: dict, creator):
        """
        Create a new school + principal in one atomic operation.
        """
        if not SchoolOnboardingService._can_create_school(creator):
            raise PermissionError(
                "Only System Root, Regional Admins or County Admins can create schools."
            )

        # Required fields
        required = ["school_name", "county", "school_type"]
        for field in required:
            if not school_data.get(field):
                raise ValueError(f"Missing required field: {field}")

        # Defaults
        school_data.setdefault("onboarding_status", OnboardingStatusChoices.PENDING)
        school_data.setdefault("onboarding_progress", 0)
        school_data["created_by"] = creator

        today = timezone.now().date()
        school_data.setdefault("trial_start_date", today)
        school_data.setdefault("trial_end_date", today + timedelta(days=30))
        school_data.setdefault("subscription_tier", "FREE_TRIAL")

        school = School.objects.create(**school_data)

        try:
            principal = UserCreationService.create_user(
                creator=creator,
                school=school,
                user_data=principal_data,
                role_name="Principal",
                send_email=True,
            )

            # Link principal
            school.principal = principal
            school.first_principal = principal
            school.onboarding_status = OnboardingStatusChoices.PRINCIPAL_CREATED
            school.onboarding_progress = 30
            school.save(
                update_fields=[
                    "principal",
                    "first_principal",
                    "onboarding_status",
                    "onboarding_progress",
                ]
            )

            SchoolOnboardingService._send_welcome_notifications(school, principal)

            logger.info(
                "School onboarded successfully: %s (ID: %s)",
                school.school_name,
                school.id,
            )
            return school, principal

        except Exception as e:
            logger.error(
                "Principal creation failed for %s. Rolling back school.",
                school.school_name,
            )
            # school.delete()
            raise Exception(f"Failed to create principal: {str(e)}") from e

    @staticmethod
    def setup_basic_structures(school: School, creator):
        """Create academic year (terms via signal) and sample classrooms."""
        if not school.principal:
            raise ValueError("School must have a principal before setting up structures.")

        with transaction.atomic():
            current_year = timezone.now().year
            next_year = current_year + 1

            academic_year = AcademicYear.objects.create(
                school=school,
                year=f"{current_year}-{next_year}",
                label=f"{current_year}-{next_year} Academic Year",
                start_date=datetime(current_year, 1, 15).date(),
                end_date=datetime(next_year, 12, 20).date(),
                is_current=True,
                terms_count=3,
                created_by=creator,
            )
            # Terms are created by academic_year_post_save signal

            classrooms = []
            if school.school_type == SchoolTypeChoices.PRIMARY:
                levels = [f"Grade {i}" for i in range(1, 9)]
                streams = ["A", "B"]
                capacity = 45
            else:
                levels = [f"Form {i}" for i in range(1, 5)]
                streams = ["East", "West", "North", "South"]
                capacity = 40

            for level in levels:
                for stream in streams:
                    cr = ClassRoom.objects.create(
                        school=school,
                        level=level,
                        stream=stream,
                        classroom_name=f"{level} {stream}",
                        capacity=capacity,
                    )
                    classrooms.append(cr)

            school.onboarding_status = OnboardingStatusChoices.STRUCTURES_SETUP
            school.onboarding_progress = 70
            school.current_academic_year = academic_year
            # Optional: point at first active/upcoming term
            first_term = academic_year.terms.order_by("sequence").first()
            if first_term:
                school.current_term = first_term

            school.save(
                update_fields=[
                    "onboarding_status",
                    "onboarding_progress",
                    "current_academic_year",
                    "current_term",
                ]
            )

            return {
                "academic_year": academic_year,
                "terms_created": academic_year.terms.count(),
                "classrooms_created": len(classrooms),
            }
    @staticmethod
    def complete_onboarding(school: School, creator):
        """Mark onboarding as fully complete."""
        if school.onboarding_status != OnboardingStatusChoices.STRUCTURES_SETUP:
            raise ValueError(
                "Basic structures must be set up before completing onboarding."
            )

        school.onboarding_status = OnboardingStatusChoices.ACTIVE
        school.onboarding_progress = 100
        school.onboarded_by = creator
        school.onboarded_date = timezone.now()
        school.save(
            update_fields=[
                "onboarding_status",
                "onboarding_progress",
                "onboarded_by",
                "onboarded_date",
            ]
        )

        logger.info(
            "Onboarding completed for %s by %s",
            school.school_name,
            creator.login_id,
        )
        return school

    @staticmethod
    def _send_welcome_notifications(school: School, principal):
        """Send welcome email to the principal."""
        try:
            from accounts.services.email_service import EmailService

            if principal.email or principal.recovery_email:
                EmailService.send_welcome_email(principal)
        except Exception as e:
            logger.warning(
                "Welcome email failed for principal of %s: %s",
                school.school_name,
                e,
            )


    # in onboarding service
    @staticmethod
    def bulk_onboard_schools(*, schools_data: list, creator):
        successful, failed = [], []
        for i, item in enumerate(schools_data):
            try:
                school, principal = SchoolOnboardingService.create_school_with_principal(
                    school_data=item.get("school_data", item),
                    principal_data=item["principal_data"],
                    creator=creator,
                )
                if item.get("auto_setup_structures", True):
                    SchoolOnboardingService.setup_basic_structures(school, creator)
                successful.append({"index": i, "school_id": str(school.id), "login_id": principal.login_id})
            except Exception as e:
                failed.append({"index": i, "error": str(e)})
        return {"successful": successful, "failed": failed}