from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from .models import ParentGuardian, Student, StudentMedicalHistory


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = (
        "admission_number",
        "full_name_link",
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
    readonly_fields = ("age", "created_at", "updated_at", "full_name")
    raw_id_fields = ("user", "school", "current_class", "boarding_house",
                     "current_academic_year", "current_term")
    list_per_page = 25

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
            )
        }),
        (_("Personal Details"), {
            "fields": (
                "date_of_birth",
                "age",
                "gender",
                "nationality",
                "county_of_origin",
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
            "fields": (
                "previous_school",
                "kcpe_index",
            ),
            "classes": ("collapse",),
        }),
        (_("Boarding"), {
            "fields": ("boarding_house",),
            "classes": ("collapse",),
        }),
        (_("Classification"), {
            "fields": ("student_category", "sponsor"),
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

    def full_name_link(self, obj):
        return format_html(
            '<a href="{}">{}</a>',
            obj.user.get_absolute_url() if hasattr(obj.user, 'get_absolute_url') else '#',
            obj.full_name
        )
    full_name_link.short_description = _("Name")
    full_name_link.admin_order_field = "user__first_name"

    def current_class_display(self, obj):
        return obj.current_class.classroom_name if obj.current_class else _("Not Assigned")
    current_class_display.short_description = _("Class")

    def student_status_colored(self, obj):
        colors = {
            Student.StudentStatusChoices.ACTIVE: "green",
            Student.StudentStatusChoices.SUSPENDED: "orange",
            Student.StudentStatusChoices.EXPELLED: "red",
            Student.StudentStatusChoices.TRANSFERRED: "purple",
            Student.StudentStatusChoices.GRADUATED: "blue",
            Student.StudentStatusChoices.WITHDRAWN: "gray",
        }
        color = colors.get(obj.student_status, "black")
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.get_student_status_display()
        )
    student_status_colored.short_description = _("Status")
    student_status_colored.admin_order_field = "student_status"


@admin.register(ParentGuardian)
class ParentGuardianAdmin(admin.ModelAdmin):
    list_display = (
        "full_name",
        "student_link",
        "relationship",
        "is_primary_badge",
        "can_pickup",
        "can_consent",
    )
    list_filter = (
        "relationship",
        "is_primary",
        "can_pickup",
        "can_consent",
        "student__school",
    )
    search_fields = (
        "user__first_name",
        "user__last_name",
        "user__phone",
        "user__email",
        "student__admission_number",
    )
    raw_id_fields = ("user", "student")
    list_per_page = 25

    fieldsets = (
        (_("Core"), {
            "fields": (
                "user",
                "student",
                "relationship",
                "is_primary",
            )
        }),
        (_("Permissions"), {
            "fields": (
                "can_pickup",
                "can_consent",
            )
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

    def full_name(self, obj):
        return obj.full_name
    full_name.short_description = _("Name")

    def student_link(self, obj):
        return format_html(
            '<a href="{}">{}</a>',
            f"/admin/students/student/{obj.student.id}/change/",
            f"{obj.student.admission_number} - {obj.student.full_name}"
        )
    student_link.short_description = _("Student")

    def is_primary_badge(self, obj):
        if obj.is_primary:
            return format_html('<span style="background:#4CAF50;color:white;padding:4px 8px;border-radius:4px;">PRIMARY</span>')
        return "-"
    is_primary_badge.short_description = _("Primary")


@admin.register(StudentMedicalHistory)
class StudentMedicalHistoryAdmin(admin.ModelAdmin):
    list_display = (
        "student_link",
        "record_type",
        "date",
        "doctor_name",
        "follow_up_status",
    )
    list_filter = (
        "record_type",
        "date",
        "follow_up_date",
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

    fieldsets = (
        (_("Record"), {
            "fields": (
                "student",
                "record_type",
                "date",
                "description",
            )
        }),
        (_("Provider"), {
            "fields": (
                "doctor_name",
                "hospital",
            )
        }),
        (_("Follow-up"), {
            "fields": ("follow_up_date", "medication"),
        }),
        (_("Audit"), {
            "fields": ("logged_by", "created_at"),
            "classes": ("collapse",),
        }),
    )

    def student_link(self, obj):
        return format_html(
            '<a href="{}">{}</a>',
            f"/admin/students/student/{obj.student.id}/change/",
            f"{obj.student.admission_number} - {obj.student.full_name}"
        )
    student_link.short_description = _("Student")

    def follow_up_status(self, obj):
        if obj.follow_up_date:
            if obj.follow_up_date >= timezone.now().date():
                return format_html(
                    '<span style="color:orange;font-weight:bold;">Pending ({})</span>',
                    obj.follow_up_date
                )
            return format_html(
                '<span style="color:gray;">Past ({})</span>',
                obj.follow_up_date
            )
        return "-"
    follow_up_status.short_description = _("Follow-up")