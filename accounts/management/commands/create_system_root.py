import sys
from django.core.management.base import BaseCommand
from django.utils.crypto import get_random_string
from accounts.models import CustomUser
from accounts.services.login_id_generator import LoginIDGenerator

class Command(BaseCommand):
    help = 'Create system root user using the proper manager method'

    def add_arguments(self, parser):
        parser.add_argument('--email', type=str, required=True)
        parser.add_argument('--phone', type=str, required=True)
        parser.add_argument('--first-name', type=str, default='System')
        parser.add_argument('--last-name', type=str, default='Administrator')
        parser.add_argument('--password', type=str)

    def handle(self, *args, **options):
        password = options['password'] or get_random_string(12)
        
        # Generate login ID
        login_id = LoginIDGenerator.generate_login_id(
            school=None,
            user_type="SYS",
            gender="M"
        )
        
        try:
            # Use the manager's create_user method instead of direct create()
            user = CustomUser.objects.create_user(
                login_id=login_id,
                first_name=options['first_name'],
                last_name=options['last_name'],
                user_type="SYS",
                email=options['email'],
                phone=options['phone'],
                national_id="00000000",  # 
                is_staff=True,
                is_superuser=True,
                is_active=True,
                is_verified=True,
                is_system_root=True,
                password=password  
            )
            
            self.stdout.write(self.style.SUCCESS(
                f'System root user created successfully!\n'
                f'Login ID: {login_id}\n'
                f'Password: {password}\n'
                f'Email: {options["email"]}'
            ))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Error creating user: {e}'))
            sys.exit(1)