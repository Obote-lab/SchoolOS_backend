from django.db import models
from django.utils.translation import gettext_lazy as _


class RoleCategoryChoices(models.TextChoices):
    ACADEMIC = "academic", _("Academic")
    ADMINISTRATIVE = "administrative", _("Administrative")
    SUPPORT = "support", _("Support")
    EXTERNAL = "external", _("External")


class AccessLevelChoices(models.TextChoices):
    SCHOOL = "school", _("School Level")
    COUNTY = "county", _("County Level")
    NATIONAL = "national", _("National Level")


class ModuleChoices(models.TextChoices):
    FINANCE = "finance", _("Finance")
    ACADEMIC = "academic", _("Academic")
    HEALTH = "health", _("Health")
    ATTENDANCE = "attendance", _("Attendance")
    DISCIPLINE = "discipline", _("Discipline")
    ACTIVITIES = "activities", _("Activities")
    COMMUNICATION = "communication", _("Communication")
    STAFF = "staff", _("Staff Management")
    STUDENTS = "students", _("Student Management")
    SETTINGS = "settings", _("System Settings")
    REPORTS = "reports", _("Reports & Analytics")
    ORGANIZATION = "organization", _("Organization")
    IDENTITY = "identity", _("Identity & Access")


class ActionChoices(models.TextChoices):
    CREATE = "create", _("Create")
    READ = "read", _("Read")
    UPDATE = "update", _("Update")
    DELETE = "delete", _("Delete")
    APPROVE = "approve", _("Approve")
    EXPORT = "export", _("Export")
    IMPORT = "import", _("Import")
    NOTIFY = "notify", _("Send Notifications")
    ASSIGN = "assign", _("Assign")
    REVOKE = "revoke", _("Revoke")


class ResourceScopeChoices(models.TextChoices):
    OWN = "own", _("Own Resources")
    DEPARTMENT = "department", _("Department Resources")
    SCHOOL = "school", _("School Resources")
    COUNTY = "county", _("County Resources")
    NATIONAL = "national", _("National Resources")


class AuditActionChoices(models.TextChoices):
    CREATE = "CREATE", _("Create")
    READ = "READ", _("Read")
    UPDATE = "UPDATE", _("Update")
    DELETE = "DELETE", _("Delete")
    LOGIN = "LOGIN", _("Login")
    LOGIN_FAILED = "LOGIN_FAILED", _("Login Failed")
    LOGOUT = "LOGOUT", _("Logout")
    PASSWORD_RESET = "PASSWORD_RESET", _("Password Reset")
    REQUEST_RESET = "REQUEST_RESET", _("Password Reset Request")
    EXPORT = "EXPORT", _("Export")
    IMPORT = "IMPORT", _("Import")
    PRINT = "PRINT", _("Print")
    APPROVE = "APPROVE", _("Approve")
    NOTIFY = "NOTIFY", _("Notification")
    ROLE_ASSIGNED = "ROLE_ASSIGNED", _("Role Assigned")
    ROLE_REVOKED = "ROLE_REVOKED", _("Role Revoked")
    ACCOUNT_ACTIVATED = "ACCOUNT_ACTIVATED", _("Account Activated")
    ACCOUNT_BLOCKED = "ACCOUNT_BLOCKED", _("Account Blocked")
    ACCOUNT_UNLOCKED = "ACCOUNT_UNLOCKED", _("Account Unlocked")