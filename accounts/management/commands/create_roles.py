from django.core.management.base import BaseCommand
from accounts.models import CustomUser, Role


class Command(BaseCommand):
    help = "Create default roles and permissions for the system"

    def handle(self, *args, **options):
        self.stdout.write("Creating default roles...")
        # Get or create superuser for created_by field
        superuser = CustomUser.objects.filter(is_superuser=True).first()
        # Default roles
        default_roles = [
            {
                "name": "System Root", 
                "role_category": "administrative", 
                "permissions_tier": 0, 
                "access_level": "national", 
                "default_dashboard": "/system/dashboard/"},

            {
                "name": "Principal",
                "role_category": "administrative",
                "permissions_tier": 1,
                "description": "School Principal with full administrative access",
                "access_level": "school",
                "default_dashboard": "/principal/dashboard/",
            },
            {
                "name": "Deputy Principal",
                "role_category": "administrative",
                "permissions_tier": 2,
                "description": "Deputy Principal with administrative access",
                "access_level": "school",
                "default_dashboard": "/deputy/dashboard/",
            },
            {
                "name": "Head of Department",
                "role_category": "academic",
                "permissions_tier": 3,
                "description": "Head of Academic Department",
                "access_level": "school",
                "default_dashboard": "/hod/dashboard/",
            },
            {
                "name": "Teacher",
                "role_category": "academic",
                "permissions_tier": 4,
                "description": "Classroom teacher",
                "access_level": "school",
                "default_dashboard": "/teacher/dashboard/",
            },
            {
                "name": "Student",
                "role_category": "academic",
                "permissions_tier": 9,
                "description": "Student account",
                "access_level": "school",
                "default_dashboard": "/student/dashboard/",
            },
            {
                "name": "Parent",
                "role_category": "external",
                "permissions_tier": 10,
                "description": "Parent/Guardian account",
                "access_level": "school",
                "default_dashboard": "/parent/dashboard/",
            },
            {
                "name": "Administrator",
                "role_category": "administrative",
                "permissions_tier": 3,
                "description": "ICT/System Administrator",
                "access_level": "school",
                "default_dashboard": "/admin/dashboard/",
            },
            {
                "name": "Matron",
                "role_category": "support",
                "permissions_tier": 6,
                "description": "School Matron/Health Officer",
                "access_level": "school",
                "default_dashboard": "/matron/dashboard/",
            },
        ]

        created_count = 0
        for role_data in default_roles:
            role, created = Role.objects.get_or_create(
                name=role_data["name"],
                defaults={
                    "role_category": role_data["role_category"],
                    "permissions_tier": role_data["permissions_tier"],
                    "description": role_data["description"],
                    "default_dashboard": role_data["default_dashboard"],
                    "access_level": role_data["access_level"],
                    "created_by": superuser,
                },
            )

            if created:
                created_count += 1
                self.stdout.write(f"Created role: {role.name}")

        self.stdout.write(
            self.style.SUCCESS(f"Successfully created {created_count} roles")
        )
