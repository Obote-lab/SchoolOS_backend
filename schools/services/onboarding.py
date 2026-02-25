from django.utils import timezone
from django.db import transaction
from accounts.services.user_creation_services import UserCreationService
from schools.models import School, AcademicYear, Term, ClassRoom


class SchoolOnboardingService:
    """
    Service to handle complete school onboarding flow
    """
    
    @staticmethod
    @transaction.atomic
    def create_school_with_principal(school_data, principal_data, creator):
        """
        Create a new school and assign initial principal
        
        Args:
            school_data: Dict with school details
            principal_data: Dict with principal user details
            creator: CustomUser who is creating (must be System Root or Regional Admin)
        
        Returns:
            tuple: (school, principal_creation_result)
        """
        # Validate creator permissions
        if not creator.is_system_root and creator.user_type != "RAD":
            raise PermissionError(
                "Only System Root or Regional Admins can create schools"
            )
        
        # Validate school data has required fields
        required_fields = ['school_name', 'county', 'type']
        for field in required_fields:
            if field not in school_data:
                raise ValueError(f"Missing required field: {field}")
        
        # Set default onboarding status
        school_data['onboarding_status'] = School.OnboardingStatusChoices.PENDING
        school_data['onboarding_progress'] = 0
        school_data['created_by'] = creator
        
        # Set trial period (30 days from now)
        today = timezone.now().date()
        school_data['trial_start_date'] = today
        school_data['trial_end_date'] = today + timezone.timedelta(days=30)
        school_data['subscription_tier'] = 'FREE_TRIAL'
        
        # Create school
        school = School.objects.create(**school_data)
        
        try:
            # Create principal
            result = UserCreationService.create_user(
                creator=creator,
                school=school,
                user_type="PRN",
                user_data=principal_data
            )
            
            # Link principal to school
            school.principal = result["user"]
            school.first_principal = result["user"]
            school.onboarding_status = School.OnboardingStatusChoices.PRINCIPAL_CREATED
            school.onboarding_progress = 30
            school.save(update_fields=[
                'principal', 'first_principal', 
                'onboarding_status', 'onboarding_progress'
            ])
            
            # Create welcome email/log
            SchoolOnboardingService._send_welcome_notifications(school, result)
            
            return school, result
            
        except Exception as e:
            # Rollback school creation if principal creation fails
            school.delete()
            raise Exception(f"Failed to create principal: {str(e)}")
    
    @staticmethod
    def setup_basic_structures(school, creator):
        """
        Create basic school structures after principal is created
        
        Creates:
        - Current academic year
        - Default terms
        - Sample classrooms
        - Default departments
        """
        if not school.principal:
            raise ValueError("School must have a principal before setting up structures")
        
        with transaction.atomic():
            # 1. Create current academic year
            current_year = timezone.now().year
            next_year = current_year + 1
            
            academic_year = AcademicYear.objects.create(
                school=school,
                year=f"{current_year}-{next_year}",
                label=f"{current_year}-{next_year} Academic Year",
                start_date=timezone.datetime(current_year, 1, 10).date(),
                end_date=timezone.datetime(next_year, 11, 30).date(),
                is_current=True,
                terms_count=3,
                holidays=[
                    {"name": "April Holiday", "start": f"{current_year}-04-01", "end": f"{current_year}-04-14"},
                    {"name": "August Holiday", "start": f"{current_year}-08-01", "end": f"{current_year}-08-31"},
                ],
                important_dates={
                    "opening_day": f"{current_year}-01-10",
                    "closing_day": f"{next_year}-11-30",
                },
                created_by=creator
            )
            
            # 2. Create terms
            terms_data = [
                {
                    "name": Term.TermNameChoices.TERM_1,
                    "sequence": 1,
                    "start_date": timezone.datetime(current_year, 1, 10).date(),
                    "end_date": timezone.datetime(current_year, 4, 5).date(),
                    "midterm_break_start": timezone.datetime(current_year, 2, 20).date(),
                    "midterm_break_end": timezone.datetime(current_year, 2, 27).date(),
                    "fee_due_date": timezone.datetime(current_year, 1, 31).date(),
                    "term_status": Term.TermStatusChoices.COMPLETED if timezone.now().date() > timezone.datetime(current_year, 4, 5).date() else Term.TermStatusChoices.ACTIVE,
                },
                {
                    "name": Term.TermNameChoices.TERM_2,
                    "sequence": 2,
                    "start_date": timezone.datetime(current_year, 5, 6).date(),
                    "end_date": timezone.datetime(current_year, 8, 8).date(),
                    "midterm_break_start": timezone.datetime(current_year, 6, 24).date(),
                    "midterm_break_end": timezone.datetime(current_year, 7, 1).date(),
                    "fee_due_date": timezone.datetime(current_year, 5, 20).date(),
                    "term_status": Term.TermStatusChoices.ACTIVE if timezone.datetime(current_year, 5, 6).date() <= timezone.now().date() <= timezone.datetime(current_year, 8, 8).date() else Term.TermStatusChoices.UPCOMING,
                },
                {
                    "name": Term.TermNameChoices.TERM_3,
                    "sequence": 3,
                    "start_date": timezone.datetime(current_year, 9, 2).date(),
                    "end_date": timezone.datetime(current_year, 11, 30).date(),
                    "midterm_break_start": timezone.datetime(current_year, 10, 21).date(),
                    "midterm_break_end": timezone.datetime(current_year, 10, 28).date(),
                    "fee_due_date": timezone.datetime(current_year, 9, 15).date(),
                    "term_status": Term.TermStatusChoices.UPCOMING,
                }
            ]
            
            for term_data in terms_data:
                Term.objects.create(academic_year=academic_year, **term_data)
            
            # 3. Create sample classrooms based on school type
            classrooms = []
            if school.type == School.SchoolTypeChoices.PRIMARY:
                levels = ["Grade 1", "Grade 2", "Grade 3", "Grade 4", "Grade 5", "Grade 6", "Grade 7", "Grade 8"]
                streams = ["A", "B"]
                for level in levels:
                    for stream in streams:
                        classroom = ClassRoom.objects.create(
                            school=school,
                            level=level,
                            stream=stream,
                            classroom_name=f"{level} {stream}",
                            capacity=45,
                            current_enrollment=0
                        )
                        classrooms.append(classroom)
            
            elif school.type == School.SchoolTypeChoices.SECONDARY:
                levels = ["Form 1", "Form 2", "Form 3", "Form 4"]
                streams = ["East", "West", "North", "South"]
                for level in levels:
                    for stream in streams:
                        classroom = ClassRoom.objects.create(
                            school=school,
                            level=level,
                            stream=stream,
                            classroom_name=f"{level} {stream}",
                            capacity=40,
                            current_enrollment=0,
                            subject_specialization=ClassRoom.SubjectSpecializationChoices.GENERAL
                        )
                        classrooms.append(classroom)
            
            # 4. Update school status
            school.onboarding_status = School.OnboardingStatusChoices.STRUCTURES_SETUP
            school.onboarding_progress = 70
            school.save(update_fields=['onboarding_status', 'onboarding_progress'])
            
            return {
                'academic_year': academic_year,
                'terms_created': 3,
                'classrooms_created': len(classrooms),
                'structures_ready': True
            }
    
    @staticmethod
    def complete_onboarding(school, creator):
        """
        Mark school onboarding as complete and ready for operations
        """
        if school.onboarding_status != School.OnboardingStatusChoices.STRUCTURES_SETUP:
            raise ValueError("School structures must be setup before completing onboarding")
        
        school.onboarding_status = School.OnboardingStatusChoices.ACTIVE
        school.onboarding_progress = 100
        school.onboarded_by = creator
        school.onboarded_date = timezone.now()
        school.save(update_fields=[
            'onboarding_status', 'onboarding_progress',
            'onboarded_by', 'onboarded_date'
        ])
        
        # Log completion event
        SchoolOnboardingService._log_onboarding_completion(school, creator)
        
        return school
    
    @staticmethod
    def bulk_onboard_schools(schools_data, creator):
        """
        Bulk onboard multiple schools (for chains or regional deployment)
        
        Args:
            schools_data: List of dicts, each containing 'school_data' and 'principal_data'
            creator: System Root or Regional Admin
        
        Returns:
            dict: Results with successes and failures
        """
        results = {
            'total': len(schools_data),
            'successful': [],
            'failed': []
        }
        
        for i, data in enumerate(schools_data):
            try:
                school, principal_result = SchoolOnboardingService.create_school_with_principal(
                    school_data=data['school_data'],
                    principal_data=data['principal_data'],
                    creator=creator
                )
                
                # Optional: Auto-setup structures
                if data.get('auto_setup_structures', True):
                    SchoolOnboardingService.setup_basic_structures(school, creator)
                
                results['successful'].append({
                    'index': i,
                    'school': school.school_name,
                    'school_code': school.school_code,
                    'principal': principal_result['user'].get_full_name(),
                    'login_id': principal_result['login_id']
                })
                
            except Exception as e:
                results['failed'].append({
                    'index': i,
                    'school_data': data.get('school_data', {}).get('school_name', f"School {i}"),
                    'error': str(e)
                })
        
        return results
    
    @staticmethod
    def _send_welcome_notifications(school, principal_result):
        """
        Send welcome notifications to principal
        """
        try:
            from accounts.utils import send_welcome_email
            
            user = principal_result['user']
            temp_password = principal_result.get('temp_password')
            
            # Send welcome email
            if user.email:
                send_welcome_email(user, temp_password)
            
            # TODO: Add SMS notification for phone
            # TODO: Add WhatsApp notification
            
        except Exception as e:
            # Log but don't fail onboarding if notifications fail
            print(f"Failed to send welcome notifications: {e}")
    
    @staticmethod
    def _log_onboarding_completion(school, creator):
        """
        Log onboarding completion for audit
        """
        # TODO: Implement proper logging system
        print(f"School onboarding completed: {school.school_name} by {creator.login_id}")
    
    @staticmethod
    def get_onboarding_checklist(school):
        """
        Get onboarding checklist with completion status
        """
        checklist = [
            {
                'step': 'school_created',
                'description': 'School record created',
                'completed': True,
                'completed_at': school.created_at
            },
            {
                'step': 'principal_created',
                'description': 'Principal account created',
                'completed': school.principal is not None,
                'completed_at': school.principal.date_joined if school.principal else None
            },
            {
                'step': 'academic_structures',
                'description': 'Academic year and terms created',
                'completed': school.academic_years.exists(),
                'completed_at': school.academic_years.first().created_at if school.academic_years.exists() else None
            },
            {
                'step': 'classrooms_created',
                'description': 'Classrooms created',
                'completed': school.classrooms.exists(),
                'completed_at': school.classrooms.first().created_at if school.classrooms.exists() else None
            },
            {
                'step': 'basic_configuration',
                'description': 'Basic school configuration',
                'completed': school.onboarding_status == School.OnboardingStatusChoices.ACTIVE,
                'completed_at': school.onboarded_date
            }
        ]
        
        # Calculate overall completion
        completed_steps = sum(1 for item in checklist if item['completed'])
        total_steps = len(checklist)
        
        return {
            'checklist': checklist,
            'completed_steps': completed_steps,
            'total_steps': total_steps,
            'completion_percentage': int((completed_steps / total_steps) * 100) if total_steps > 0 else 0
        }