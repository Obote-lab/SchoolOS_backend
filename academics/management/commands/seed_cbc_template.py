"""
Seed an Official CBC (KICD-aligned) Academic Framework for schools.

Usage:
    # Seed for ALL schools that don't already have a CBC framework
    python manage.py seed_cbc_template

    # Seed for a specific school
    python manage.py seed_cbc_template --school-id <uuid>

    # Force re-seed (updates existing CBC framework)
    python manage.py seed_cbc_template --force
"""

from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from schools.models import School
from academics.models import (
    AcademicFramework,
    Pathway,
    Level,
    GradingScheme,
    GradingSchemeVersion,
    AssessmentScheme,
    AssessmentSchemeVersion,
    LearningArea,
    Strand,
    SubStrand,
)
from core.choices.academic import (
    TemplateType,
    TermModel,
)


class Command(BaseCommand):
    help = "Seed Official CBC (KICD-aligned) Academic Framework + Pathways + Levels + Schemes"

    def add_arguments(self, parser):
        parser.add_argument(
            "--school-id",
            type=str,
            help="UUID of a specific school. If omitted, seeds all schools.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Update existing CBC framework instead of skipping.",
        )

    def handle(self, *args, **options):
        school_id = options.get("school_id")
        force = options.get("force", False)

        if school_id:
            try:
                schools = School.objects.filter(id=school_id)
                if not schools.exists():
                    raise CommandError(f"School with id={school_id} not found.")
            except Exception as e:
                raise CommandError(str(e))
        else:
            schools = School.objects.filter(is_active=True)

        total = schools.count()
        self.stdout.write(self.style.NOTICE(f"Found {total} school(s) to process…"))

        created_count = 0
        updated_count = 0
        skipped_count = 0

        for school in schools.iterator():
            result = self._seed_school(school, force=force)
            if result == "created":
                created_count += 1
            elif result == "updated":
                updated_count += 1
            else:
                skipped_count += 1

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("── Seed Summary ──────────────────────"))
        self.stdout.write(f"  Created : {created_count}")
        self.stdout.write(f"  Updated : {updated_count}")
        self.stdout.write(f"  Skipped : {skipped_count}")
        self.stdout.write(self.style.SUCCESS("──────────────────────────────────────"))

    @transaction.atomic
    def _seed_school(self, school: School, force: bool = False) -> str:
        existing = AcademicFramework.objects.filter(
            school=school,
            template_type=AcademicFramework.TemplateType.CBC,
            code="CBC-KICD",
        ).first()

        if existing and not force:
            self.stdout.write(
                self.style.WARNING(f"  ↷  {school.school_name}: CBC framework already exists – skipped")
            )
            return "skipped"

        if existing and force:
            framework = existing
            action = "updated"
            self.stdout.write(
                self.style.WARNING(f"  ↻  {school.school_name}: Updating existing CBC framework…")
            )
        else:
            framework = AcademicFramework(
                school=school,
                name="Competency Based Curriculum (CBC)",
                code="CBC-KICD",
                template_type=AcademicFramework.TemplateType.CBC,
                term_model=AcademicFramework.TermModel.TERM_BASED,
                supports_competencies=True,
                supports_pathways=True,
                description=(
                    "Official KICD-aligned Competency Based Curriculum. "
                    "Includes PP1–PP2, Grades 1–6 (Primary), Grades 7–9 (Junior Secondary) "
                    "and Grades 10–12 (Senior Secondary) with the three pathways."
                ),
                is_active=True,
                is_template_seeded=True,
                effective_from=date(2024, 1, 1),
            )
            framework.save()
            action = "created"
            self.stdout.write(
                self.style.SUCCESS(f"  ✓  {school.school_name}: CBC framework created")
            )

        # Pathways (Senior Secondary)
        pathways_data = [
            {
                "name": "STEM",
                "code": "STEM",
                "sequence": 1,
                "is_default": True,
                "description": "Science, Technology, Engineering & Mathematics pathway",
            },
            {
                "name": "Social Sciences",
                "code": "SOC",
                "sequence": 2,
                "is_default": False,
                "description": "Humanities, Business and Social Sciences pathway",
            },
            {
                "name": "Arts & Sports Science",
                "code": "ARTS",
                "sequence": 3,
                "is_default": False,
                "description": "Creative Arts, Performing Arts and Sports Science pathway",
            },
        ]

        pathway_map = {}
        for p in pathways_data:
            pathway, _ = Pathway.objects.update_or_create(
                framework=framework,
                code=p["code"],
                defaults={
                    "name": p["name"],
                    "sequence": p["sequence"],
                    "is_default": p["is_default"],
                    "description": p["description"],
                    "supports_competencies": True,
                    "is_active": True,
                },
            )
            pathway_map[p["code"]] = pathway

        # Levels (shared across pathways)
        levels_data = [
            # Pre-Primary
            {"name": "PP1", "code": "PP1", "sequence": 1, "age_from": 4, "age_to": 5},
            {"name": "PP2", "code": "PP2", "sequence": 2, "age_from": 5, "age_to": 6},
            # Primary
            {"name": "Grade 1", "code": "G1", "sequence": 3, "age_from": 6, "age_to": 7},
            {"name": "Grade 2", "code": "G2", "sequence": 4, "age_from": 7, "age_to": 8},
            {"name": "Grade 3", "code": "G3", "sequence": 5, "age_from": 8, "age_to": 9},
            {"name": "Grade 4", "code": "G4", "sequence": 6, "age_from": 9, "age_to": 10},
            {"name": "Grade 5", "code": "G5", "sequence": 7, "age_from": 10, "age_to": 11},
            {"name": "Grade 6", "code": "G6", "sequence": 8, "age_from": 11, "age_to": 12},
            # Junior Secondary
            {"name": "Grade 7", "code": "G7", "sequence": 9, "age_from": 12, "age_to": 13},
            {"name": "Grade 8", "code": "G8", "sequence": 10, "age_from": 13, "age_to": 14},
            {"name": "Grade 9", "code": "G9", "sequence": 11, "age_from": 14, "age_to": 15},
            # Senior Secondary
            {"name": "Grade 10", "code": "G10", "sequence": 12, "age_from": 15, "age_to": 16},
            {"name": "Grade 11", "code": "G11", "sequence": 13, "age_from": 16, "age_to": 17},
            {
                "name": "Grade 12",
                "code": "G12",
                "sequence": 14,
                "age_from": 17,
                "age_to": 18,
                "is_graduation_level": True,
            },
        ]

        for lvl in levels_data:
            Level.objects.update_or_create(
                framework=framework,
                code=lvl["code"],
                defaults={
                    "name": lvl["name"],
                    "sequence": lvl["sequence"],
                    "age_from": lvl.get("age_from"),
                    "age_to": lvl.get("age_to"),
                    "is_graduation_level": lvl.get("is_graduation_level", False),
                    "pathway": None,  # shared across pathways
                    "is_active": True,
                },
            )

        # Default Grading Scheme (CBC competency levels + traditional scale)
        grading_scheme, _ = GradingScheme.objects.update_or_create(
            school=school,
            code="CBC-DEFAULT",
            defaults={
                "framework": framework,
                "name": "CBC Standard Grading",
                "description": "Official CBC competency levels + traditional letter grades",
                "is_default": True,
                "is_active": True,
            },
        )

        # Only create version 1 if none exists
        if not grading_scheme.versions.exists():
            GradingSchemeVersion.objects.create(
                scheme=grading_scheme,
                version_number=1,
                grade_scale=[
                    {"grade": "A", "min": 80, "max": 100, "points": 12, "label": "Excellent"},
                    {"grade": "A-", "min": 75, "max": 79.99, "points": 11, "label": "Very Good"},
                    {"grade": "B+", "min": 70, "max": 74.99, "points": 10, "label": "Good"},
                    {"grade": "B", "min": 65, "max": 69.99, "points": 9, "label": "Good"},
                    {"grade": "B-", "min": 60, "max": 64.99, "points": 8, "label": "Fair"},
                    {"grade": "C+", "min": 55, "max": 59.99, "points": 7, "label": "Fair"},
                    {"grade": "C", "min": 50, "max": 54.99, "points": 6, "label": "Satisfactory"},
                    {"grade": "C-", "min": 45, "max": 49.99, "points": 5, "label": "Satisfactory"},
                    {"grade": "D+", "min": 40, "max": 44.99, "points": 4, "label": "Weak"},
                    {"grade": "D", "min": 35, "max": 39.99, "points": 3, "label": "Weak"},
                    {"grade": "D-", "min": 30, "max": 34.99, "points": 2, "label": "Very Weak"},
                    {"grade": "E", "min": 0, "max": 29.99, "points": 1, "label": "Poor"},
                ],
                competency_levels=[
                    {"code": "EE", "label": "Exceeding Expectations", "min": 4, "max": 4},
                    {"code": "ME", "label": "Meeting Expectations", "min": 3, "max": 3},
                    {"code": "AE", "label": "Approaching Expectations", "min": 2, "max": 2},
                    {"code": "BE", "label": "Below Expectations", "min": 1, "max": 1},
                ],
                effective_from=date(2024, 1, 1),
                is_current=True,
                change_reason="Initial CBC seed",
            )

        # Default Assessment Scheme
        assessment_scheme, _ = AssessmentScheme.objects.update_or_create(
            school=school,
            code="CBC-DEFAULT",
            defaults={
                "framework": framework,
                "name": "CBC Standard Assessment",
                "description": "Typical CBC balance of formative + summative assessment",
                "is_default": True,
                "is_active": True,
            },
        )

        if not assessment_scheme.versions.exists():
            AssessmentSchemeVersion.objects.create(
                scheme=assessment_scheme,
                version_number=1,
                assessment_types=[
                    {
                        "type": "exam",
                        "label": "Summative / End of Term Exam",
                        "weight": 40,
                        "is_summative": True,
                    },
                    {
                        "type": "ca",
                        "label": "Continuous Assessment (CAT)",
                        "weight": 30,
                        "is_summative": False,
                    },
                    {
                        "type": "project",
                        "label": "Project / Practical",
                        "weight": 20,
                        "is_summative": False,
                    },
                    {
                        "type": "participation",
                        "label": "Participation & Portfolio",
                        "weight": 10,
                        "is_summative": False,
                    },
                ],
                effective_from=date(2024, 1, 1),
                is_current=True,
                change_reason="Initial CBC seed",
            )

        
        # Sample Learning Areas (high-level only – schools can expand)
        sample_areas = [
            {"name": "Mathematics", "code": "MATH", "sequence": 1},
            {"name": "Languages", "code": "LANG", "sequence": 2},
            {"name": "Science & Technology", "code": "SCI", "sequence": 3},
            {"name": "Social Studies", "code": "SST", "sequence": 4},
            {"name": "Creative Arts", "code": "ART", "sequence": 5},
            {"name": "Physical Health Education", "code": "PHE", "sequence": 6},
            {"name": "Religious Education", "code": "RE", "sequence": 7},
        ]

        for area in sample_areas:
            LearningArea.objects.update_or_create(
                framework=framework,
                code=area["code"],
                defaults={
                    "name": area["name"],
                    "sequence": area["sequence"],
                    "pathway": None,
                    "is_active": True,
                    "description": f"CBC Learning Area – {area['name']}",
                },
            )

        return action