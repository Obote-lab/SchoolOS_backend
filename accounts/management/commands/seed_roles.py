from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import Role, PermissionMatrix
from core.choices.identity import (
    ModuleChoices,
    ActionChoices,
    ResourceScopeChoices,
    RoleCategoryChoices,
    AccessLevelChoices,
)


class Command(BaseCommand):
    help = "Seed core Roles and PermissionMatrix (including branding)"

    def handle(self, *args, **options):
        with transaction.atomic():
            self.stdout.write("Seeding Roles …")
            self.seed_roles()

            self.stdout.write("Seeding Branding permissions …")
            self.seed_branding_permissions()

        self.stdout.write(self.style.SUCCESS("Roles + Branding permissions seeded successfully."))


    # 1. Core Roles
    def seed_roles(self):
        """
        Idempotent Role seeding.
        Adjust names / tiers / categories only if your product vocabulary changes.
        """
        roles_data = [
            # Platform / National
            {
                "name": "System Root",
                "role_category": RoleCategoryChoices.ADMINISTRATIVE,
                "permissions_tier": 1,
                "access_level": AccessLevelChoices.NATIONAL,
                "description": "Platform super-admin. Full system control.",
                "default_dashboard": "/system/dashboard/",
            },
            {
                "name": "Platform Admin",
                "role_category": RoleCategoryChoices.ADMINISTRATIVE,
                "permissions_tier": 2,
                "access_level": AccessLevelChoices.NATIONAL,
                "description": "Platform-level administrator.",
                "default_dashboard": "/system/dashboard/",
            },
            {
                "name": "Super Admin",
                "role_category": RoleCategoryChoices.ADMINISTRATIVE,
                "permissions_tier": 2,
                "access_level": AccessLevelChoices.NATIONAL,
                "description": "Legacy / alternate platform admin name.",
                "default_dashboard": "/system/dashboard/",
            },
            # County / Regional
            {
                "name": "Regional Admin",
                "role_category": RoleCategoryChoices.ADMINISTRATIVE,
                "permissions_tier": 3,
                "access_level": AccessLevelChoices.COUNTY,
                "description": "Manages one or more counties.",
                "default_dashboard": "/regional/dashboard/",
            },
            # School-level leadership
            {
                "name": "Principal",
                "role_category": RoleCategoryChoices.ADMINISTRATIVE,
                "permissions_tier": 4,
                "access_level": AccessLevelChoices.SCHOOL,
                "description": "Head of School / Principal. Highest school-level authority.",
                "default_dashboard": "/school/dashboard/",
            },
            {
                "name": "Deputy Principal",
                "role_category": RoleCategoryChoices.ADMINISTRATIVE,
                "permissions_tier": 5,
                "access_level": AccessLevelChoices.SCHOOL,
                "description": "Deputy Head of School.",
                "default_dashboard": "/school/dashboard/",
            },
            # Academic
            {
                "name": "HOD",
                "role_category": RoleCategoryChoices.ACADEMIC,
                "permissions_tier": 6,
                "access_level": AccessLevelChoices.SCHOOL,
                "description": "Head of Department.",
                "default_dashboard": "/academic/dashboard/",
            },
            {
                "name": "Teacher",
                "role_category": RoleCategoryChoices.ACADEMIC,
                "permissions_tier": 7,
                "access_level": AccessLevelChoices.SCHOOL,
                "description": "Classroom teacher.",
                "default_dashboard": "/teacher/dashboard/",
            },
            # Support / non-teaching (examples)
            {
                "name": "Bursar",
                "role_category": RoleCategoryChoices.SUPPORT,
                "permissions_tier": 6,
                "access_level": AccessLevelChoices.SCHOOL,
                "description": "School finance officer.",
                "default_dashboard": "/finance/dashboard/",
            },
            {
                "name": "Matron",
                "role_category": RoleCategoryChoices.SUPPORT,
                "permissions_tier": 8,
                "access_level": AccessLevelChoices.SCHOOL,
                "description": "Boarding / welfare matron.",
                "default_dashboard": "/welfare/dashboard/",
            },
            # External
            {
                "name": "Parent",
                "role_category": RoleCategoryChoices.EXTERNAL,
                "permissions_tier": 9,
                "access_level": AccessLevelChoices.SCHOOL,
                "description": "Parent / Guardian.",
                "default_dashboard": "/parent/dashboard/",
            },
            {
                "name": "Student",
                "role_category": RoleCategoryChoices.EXTERNAL,
                "permissions_tier": 10,
                "access_level": AccessLevelChoices.SCHOOL,
                "description": "Learner.",
                "default_dashboard": "/student/dashboard/",
            },
        ]

        for data in roles_data:
            role, created = Role.objects.update_or_create(
                name=data["name"],
                defaults={
                    "role_category": data["role_category"],
                    "permissions_tier": data["permissions_tier"],
                    "access_level": data["access_level"],
                    "description": data["description"],
                    "default_dashboard": data["default_dashboard"],
                },
            )
            status = "created" if created else "updated"
            self.stdout.write(f"  Role '{role.name}' {status}")

    
    # 2. Branding permissions (Root + Principal only)
    def seed_branding_permissions(self):
        root_roles = Role.objects.filter(
            name__in=["System Root", "Platform Admin", "Super Admin"]
        )
        principal_role = Role.objects.filter(name="Principal").first()

        # Root / platform (national scope)
        for role in root_roles:
            # UPDATE (maps to required_action="update" / manage in viewsets)
            PermissionMatrix.objects.update_or_create(
                role=role,
                module=ModuleChoices.BRANDING,
                action=ActionChoices.UPDATE,
                resource_scope=ResourceScopeChoices.NATIONAL,
                defaults={
                    "is_allowed": True,
                    "priority": 10,
                },
            )
            # READ
            PermissionMatrix.objects.update_or_create(
                role=role,
                module=ModuleChoices.BRANDING,
                action=ActionChoices.READ,
                resource_scope=ResourceScopeChoices.NATIONAL,
                defaults={
                    "is_allowed": True,
                    "priority": 10,
                },
            )
            self.stdout.write(f"  Branding permissions granted to '{role.name}' (national)")

        #Principal (school scope only)
        if principal_role:
            PermissionMatrix.objects.update_or_create(
                role=principal_role,
                module=ModuleChoices.BRANDING,
                action=ActionChoices.UPDATE,
                resource_scope=ResourceScopeChoices.SCHOOL,
                defaults={
                    "is_allowed": True,
                    "priority": 5,
                },
            )
            PermissionMatrix.objects.update_or_create(
                role=principal_role,
                module=ModuleChoices.BRANDING,
                action=ActionChoices.READ,
                resource_scope=ResourceScopeChoices.SCHOOL,
                defaults={
                    "is_allowed": True,
                    "priority": 5,
                },
            )
            self.stdout.write(f"  Branding permissions granted to 'Principal' (school)")
        else:
            self.stdout.write(self.style.WARNING("  Principal role not found – branding school permissions skipped"))