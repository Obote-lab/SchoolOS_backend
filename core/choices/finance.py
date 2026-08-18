from django.db import models
from django.utils.translation import gettext_lazy as _


class FeesCategoryChoices(models.TextChoices):
    TUITION = "tuition", _("Tuition")
    BOARDING = "boarding", _("Boarding")
    ACTIVITY = "activity", _("Activity / Co-curriculum")
    EXAMINATION = "exam", _("Examination")
    DEVELOPMENT = "development", _("Development / Infrastructure")
    UNIFORM = "uniform", _("Uniform")
    MEDICAL = "medical", _("Medical")
    CUSTOM = "custom", _("Custom / Other")
    OTHER = "other", _("Other")



class FeesStatusChoices(models.TextChoices):
    DRAFT = "draft", _("Draft")
    APPROVED = "approved", _("Approved")
    ACTIVE = "active", _("Active")
    ARCHIVED = "archived", _("Archived")


class InvoiceStatusChoices(models.TextChoices):
    DRAFT = "draft", _("Draft")
    ISSUED = "issued", _("Issued")
    PARTIALLY_PAID = "partially_paid", _("Partially Paid")
    PAID = "paid", _("Paid")
    OVERDUE = "overdue", _("Overdue")
    WRITTEN_OFF = "written_off", _("Written Off")


class PaymentMethodChoices(models.TextChoices):
    CASH = "cash", _("Cash")
    MPESA = "mpesa", _("M-Pesa")
    BANK_TRANSFER = "bank_transfer", _("Bank Transfer")
    CHEQUE = "cheque", _("Cheque")
    CARD = "card", _("Card")
    SACCO = "sacco", _("SACCO")
    BURSARY = "bursary", _("Bursary Disbursement")
    CUSTOM = "custom", _("Custom / Other")


class PaymentStatusChoices(models.TextChoices):
    PENDING = "pending", _("Pending")
    COMPLETED = "completed", _("Completed")
    FAILED = "failed", _("Failed")
    REVERSED = "reversed", _("Reversed")
    PAID = "paid", _("Paid")
    PARTIALLY_PAID = "partially_paid", _("Partially Paid")
    OVERDUE = "overdue", _("Overdue")



class PaymentFrequencyChoices(models.TextChoices):
    WEEKLY = "weekly", _("Weekly")
    BIWEEKLY = "biweekly", _("Bi-weekly")
    MONTHLY = "monthly", _("Monthly")
    TERMLY = "termly", _("Termly")
    QUARTERLY = "quarterly", _("Quarterly")
    ANNUALLY = "annually", _("Annually")
    CUSTOM = "custom", _("Custom")


class PaymentPlanStatusChoices(models.TextChoices):
    ACTIVE = "active", _("Active")
    COMPLETED = "completed", _("Completed")
    DEFAULTED = "defaulted", _("Defaulted")
    CANCELLED = "cancelled", _("Cancelled")


class BursarySourceChoices(models.TextChoices):
    COUNTY = "county", _("County")
    NATIONAL = "national", _("National / CDF / HELB")
    NGO = "ngo", _("NGO / Sponsor")
    SCHOOL = "school", _("School Internal")
    INDIVIDUAL = "individual", _("Individual Donor")


class BursaryStatusChoices(models.TextChoices):
    APPLIED = "applied", _("Applied")
    APPROVED = "approved", _("Approved")
    DISBURSED = "disbursed", _("Disbursed")
    REJECTED = "rejected", _("Rejected")
    WITHDRAWN = "withdrawn", _("Withdrawn")


class TransactionTypeChoices(models.TextChoices):
    INCOME = "income", _("Income")
    EXPENSE = "expense", _("Expense")
    TRANSFER = "transfer", _("Transfer")
    ADJUSTMENT = "adjustment", _("Adjustment")


class FinanceCategoryChoices(models.TextChoices):
    FEES = "fees", _("Fees")
    SALARY = "salary", _("Salary")
    SUPPLIES = "supplies", _("Supplies")
    UTILITIES = "utilities", _("Utilities")
    MAINTENANCE = "maintenance", _("Maintenance")
    OTHER = "other", _("Other")


class FinanceTransactionStatusChoices(models.TextChoices):
    PENDING = "pending", _("Pending")
    APPROVED = "approved", _("Approved")
    POSTED = "posted", _("Posted")
    REJECTED = "rejected", _("Rejected")
    