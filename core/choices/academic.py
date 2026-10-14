from django.db import models

class TermNameChoices(models.TextChoices):
        TERM_1 = "term_1", "Term 1"
        TERM_2 = "term_2", "Term 2"
        TERM_3 = "term_3", "Term 3"
        TERM_4 = "term_4", "Term 4"  # For some schools

class TermStatusChoices(models.TextChoices):
        UPCOMING = "upcoming", "Upcoming"
        ACTIVE = "active", "Active"
        COMPLETED = "completed", "Completed"
        ARCHIVED = "archived", "Archived"


class SubjectSpecializationChoices(models.TextChoices):
        SCIENCE = "science", "Science"
        ARTS = "arts", "Arts"
        GENERAL = "general", "General"
        TECHNICAL = "technical", "Technical"
        BUSINESS = "business", "Business"
        AGRICULTURE = "agriculture", "Agriculture"


class SubjectCategoryChoices(models.TextChoices):
        CORE = "core", "Core"
        ELECTIVE = "elective", "Elective"
        COMPULSORY = "compulsory", "Compulsory"
        OPTIONAL = "optional", "Optional"


class SubjectLevelChoices(models.TextChoices):
        PRIMARY = "primary", "Primary"
        LOWER_SECONDARY = "lower_secondary", "Lower Secondary"
        UPPER_SECONDARY = "upper_secondary", "Upper Secondary"


class LessonPlanStatusChoices(models.TextChoices):
        PLANNED = "planned", "Planned"
        TAUGHT = "taught", "Taught"
        POSTPONED = "postponed", "Postponed"
        CANCELLED = "cancelled", "Cancelled"


class UnderstandingLevelChoices(models.TextChoices):
        POOR = "poor", "Poor"
        FAIR = "fair", "Fair"
        GOOD = "good", "Good"
        EXCELLENT = "excellent", "Excellent"


class ExamStatusChoices(models.TextChoices):
        DRAFT = "draft", "Draft"
        SCHEDULED = "scheduled", "Scheduled"
        IN_PROGRESS = "in_progress", "In Progress"
        MARKING = "marking", "Marking"
        COMPLETED = "completed", "Completed"
        PUBLISHED = "published", "Published"


class AssessmentTypeChoices(models.TextChoices):
        HOMEWORK = "homework", "Homework"
        CLASSWORK = "classwork", "Classwork"
        PROJECT = "project", "Project"
        PRESENTATION = "presentation", "Presentation"
        PARTICIPATION = "participation", "Participation"


class AppealStatusChoices(models.TextChoices):
        NONE = "none", "None"
        REQUESTED = "requested", "Requested"
        REVIEWED = "reviewed", "Reviewed"
        ADJUSTED = "adjusted", "Adjusted"



class TemplateType(models.TextChoices):
        CBC = "cbc", "Official CBC (KICD)"
        INTERNATIONAL = "international", "Generic International"
        TRADITIONAL = "traditional", "Lightweight Traditional"
        CUSTOM = "custom", "Blank / Custom"

class TermModel(models.TextChoices):
        TERM_BASED = "term_based", "Term-based"
        SEMESTER = "semester", "Semester"
        CONTINUOUS = "continuous", "Continuous Year"
