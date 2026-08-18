from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from core.choices.students import StudentStatusChoices
from .models import ParentGuardian, StudentMedicalHistory, StudentProfile


@admin.register(StudentProfile)
class StudentAdmin(admin.ModelAdmin):
    list_display = (
        "admission_number",
        "full_name_display",
        "school",
        "current_class_display",
        "gender",
        "student_status_colored",
        "student_category",
        "admission_date",
    )
    list_filter = (
        "student_status",
        "student_category",
        "gender",
        "school",
        "current_class",
        "nationality",
        ("admission_date", admin.DateFieldListFilter),
    )
    search_fields = (
        "admission_number",
        "user__first_name",
        "user__last_name",
        "user__phone",
        "user__email",
        "kcpe_index",
    )
    date_hierarchy = "admission_date"
    readonly_fields = ("age", "created_at", "updated_at")
    raw_id_fields = (
        "user",
        "school",
        "current_class",
        "boarding_house",
        "current_academic_year",
        "current_term",
    )
    list_per_page = 25
    ordering = ("admission_number",)

    fieldsets = (
        (_("Core Information"), {
            "fields": (
                "admission_number",
                "user",
                "school",
                "current_class",
                "admission_date",
                "registration_date",
                "student_status",
                "status_reason",
                "exit_date",
                "exit_notes",
            )
        }),
        (_("Personal Details"), {
            "fields": (
                "date_of_birth",
                "age",
                "gender",
                "religion",
                "nationality",
                "county_of_origin",
                "sub_county_of_origin",
            ),
            "classes": ("collapse",),
        }),
        (_("Health"), {
            "fields": (
                "disability",
                "disability_details",
                "blood_group",
                "allergies",
                "chronic_conditions",
            ),
            "classes": ("collapse",),
        }),
        (_("Emergency Contact"), {
            "fields": (
                "emer_contact_name",
                "emer_contact_phone",
                "emer_contact_relation",
                "emer_contact_alternate_phone",
            )
        }),
        (_("Academic & Entry Info"), {
            "fields": ("previous_school", "kcpe_index"),
            "classes": ("collapse",),
        }),
        (_("Boarding"), {
            "fields": ("boarding_house",),
            "classes": ("collapse",),
        }),
        (_("Classification"), {
            "fields": ("student_category", "sponsor", "sponsor_contact"),
        }),
        (_("Current Academic Context"), {
            "fields": ("current_academic_year", "current_term"),
            "classes": ("collapse",),
        }),
        (_("Metadata"), {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )

    def full_name_display(self, obj):
        return obj.full_name

    full_name_display.short_description = _("Name")
    full_name_display.admin_order_field = "user__first_name"

    def current_class_display(self, obj):
        return obj.current_class.classroom_name if obj.current_class else _("Not Assigned")

    current_class_display.short_description = _("Class")

    def student_status_colored(self, obj):
        colors = {
            StudentStatusChoices.ACTIVE: "green",
            StudentStatusChoices.SUSPENDED: "orange",
            StudentStatusChoices.EXPELLED: "red",
            StudentStatusChoices.TRANSFERRED: "purple",
            StudentStatusChoices.GRADUATED: "blue",
            StudentStatusChoices.WITHDRAWN: "gray",
            StudentStatusChoices.DECEASED: "black",
        }
        color = colors.get(obj.student_status, "black")
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_student_status_display(),
        )

    student_status_colored.short_description = _("Status")
    student_status_colored.admin_order_field = "student_status"


@admin.register(ParentGuardian)
class ParentGuardianAdmin(admin.ModelAdmin):
    list_display = (
        "full_name_display",
        "relationship",
        "is_primary_badge",
        "can_pickup",
        "can_consent",
        "students_count",
    )
    list_filter = (
        "relationship",
        "is_primary",
        "can_pickup",
        "can_consent",
    )
    search_fields = (
        "user__first_name",
        "user__last_name",
        "user__phone",
        "user__email",
        "students__admission_number",
    )
    raw_id_fields = ("user",)
    filter_horizontal = ("students",)   # because it is ManyToMany
    list_per_page = 25
    readonly_fields = ("created_at", "updated_at")

    fieldsets = (
        (_("Core"), {
            "fields": (
                "user",
                "students",
                "relationship",
                "is_primary",
            )
        }),
        (_("Permissions"), {
            "fields": ("can_pickup", "can_consent"),
        }),
        (_("Extra Contact"), {
            "fields": ("alternate_phone",),
            "classes": ("collapse",),
        }),
        (_("Metadata"), {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )

    def full_name_display(self, obj):
        return obj.user.get_full_name()

    full_name_display.short_description = _("Name")
    full_name_display.admin_order_field = "user__first_name"

    def is_primary_badge(self, obj):
        if obj.is_primary:
            return format_html(
                '<span style="background:#4CAF50;color:white;padding:3px 8px;border-radius:4px;font-size:11px;">PRIMARY</span>'
            )
        return "—"

    is_primary_badge.short_description = _("Primary")

    def students_count(self, obj):
        return obj.students.count()

    students_count.short_description = _("Students")


@admin.register(StudentMedicalHistory)
class StudentMedicalHistoryAdmin(admin.ModelAdmin):
    list_display = (
        "student_display",
        "record_type",
        "date",
        "doctor_name",
        "follow_up_status",
    )
    list_filter = (
        "record_type",
        ("date", admin.DateFieldListFilter),
        "student__school",
    )
    search_fields = (
        "student__admission_number",
        "student__user__first_name",
        "student__user__last_name",
        "doctor_name",
        "hospital",
        "description",
    )
    date_hierarchy = "date"
    readonly_fields = ("created_at",)
    raw_id_fields = ("student", "logged_by")
    list_per_page = 20
    ordering = ("-date",)

    fieldsets = (
        (_("Record"), {
            "fields": ("student", "record_type", "date", "description"),
        }),
        (_("Provider"), {
            "fields": ("doctor_name", "hospital"),
        }),
        (_("Follow-up"), {
            "fields": ("follow_up_date", "medication"),
        }),
        (_("Audit"), {
            "fields": ("logged_by", "created_at"),
            "classes": ("collapse",),
        }),
    )

    def student_display(self, obj):
        return f"{obj.student.admission_number} – {obj.student.full_name}"

    student_display.short_description = _("Student")
    student_display.admin_order_field = "student__admission_number"

    def follow_up_status(self, obj):
        if not obj.follow_up_date:
            return "—"
        if obj.follow_up_date >= timezone.now().date():
            return format_html(
                '<span style="color:orange;font-weight:bold;">Pending ({})</span>',
                obj.follow_up_date,
            )
        return format_html(
            '<span style="color:gray;">Past ({})</span>',
            obj.follow_up_date,
        )

    follow_up_status.short_description = _("Follow-up")