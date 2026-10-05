import uuid
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models, transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from core.choices.finance import (
    BursarySourceChoices,FeesCategoryChoices,
    FeesStatusChoices, InvoiceStatusChoices,
    PaymentMethodChoices,PaymentStatusChoices,
    PaymentFrequencyChoices,PaymentPlanStatusChoices,
    TransactionTypeChoices,FinanceCategoryChoices,
    FinanceTransactionStatusChoices,BursaryStatusChoices,
)

# CustomUser = get_user_model()


def _school_code(school) -> str:
    if not school:
        return "SCH"
    return (
        getattr(school, "school_code", None)
        or getattr(school, "system_school_code", None)
        or "SCH"
    )

class FeeStructure(models.Model):
    """Defines fee items per class/term/category."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey("schools.School", on_delete=models.CASCADE, related_name="fee_structures")
    class_level = models.CharField(max_length=100)  # "Form 2", "Grade 5", "PP2", etc.
    term = models.ForeignKey("schools.Term", on_delete=models.PROTECT)
    academic_year = models.ForeignKey("schools.AcademicYear", on_delete=models.PROTECT)
    fees_category = models.CharField(max_length=30, choices=FeesCategoryChoices.choices)
    description = models.CharField(max_length=255, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0"))])
    due_date = models.DateField()
    late_fee_per_day = models.DecimalField( max_digits=10, decimal_places=2, default=Decimal("0"), validators=[MinValueValidator(Decimal("0"))], )
    is_compulsory = models.BooleanField(default=True)
    is_refundable = models.BooleanField(default=False)
    gl_account = models.CharField(max_length=50, blank=True, help_text=_("General Ledger code"))
    taxable = models.BooleanField(default=False)
    tax_rate = models.DecimalField( max_digits=5,decimal_places=2,default=Decimal("0"), validators=[MinValueValidator(Decimal("0"))],)
    effective_from = models.DateField(default=timezone.now)
    expires_on = models.DateField(null=True, blank=True)
    fees_status = models.CharField(max_length=20, choices=FeesStatusChoices.choices, default=FeesStatusChoices.DRAFT)
    created_by = models.ForeignKey("accounts.CustomUser", on_delete=models.SET_NULL,null=True,related_name="fee_structures_created",)
    approved_by = models.ForeignKey("accounts.CustomUser", on_delete=models.SET_NULL, null=True, blank=True, related_name="fee_structures_approved", )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [
            ["school", "class_level", "term", "academic_year", "fees_category"]
        ]
        ordering = ["class_level", "fees_category"]
        indexes = [
            models.Index(fields=["school", "fees_status", "effective_from"]),
        ]

    def __str__(self):
        return f"{self.class_level} – {self.get_fees_category_display()} – KES {self.amount}"

    def clean(self):
        super().clean()
        if self.expires_on and self.effective_from and self.expires_on <= self.effective_from:
            raise ValidationError({"expires_on": _("Expiry must be after effective date.")})
        if self.due_date and self.effective_from and self.due_date < self.effective_from:
            raise ValidationError({"due_date": _("Due date cannot be before effective date.")})
        if self.term_id and self.academic_year_id:
            if self.term.academic_year_id != self.academic_year_id:
                raise ValidationError({"term": _("Term must belong to the academic year.")})
        if self.academic_year_id and self.school_id:
            if self.academic_year.school_id != self.school_id:
                raise ValidationError({"academic_year": _("Academic year must belong to this school.")})

    def save(self, *args, **kwargs):
        validate = kwargs.pop("validate", True)
        if validate:
            self.full_clean()
        super().save(*args, **kwargs)

class FeeInvoice(models.Model):
    """Individual student invoice per term."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice_number = models.CharField(max_length=50, unique=True, editable=False)
    school = models.ForeignKey("schools.School", on_delete=models.PROTECT)
    student = models.ForeignKey("students.StudentProfile", on_delete=models.PROTECT, related_name="invoices")
    term = models.ForeignKey("schools.Term", on_delete=models.PROTECT)
    academic_year = models.ForeignKey("schools.AcademicYear", on_delete=models.PROTECT)
    issue_date = models.DateField(default=timezone.now)
    due_date = models.DateField()
    amount_paid = models.DecimalField( max_digits=12, decimal_places=2, default=Decimal("0"))
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    previous_balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    late_fee_accrued = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    waiver_amount = models.DecimalField( max_digits=12, decimal_places=2, default=Decimal("0"))
    net_payable = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    bursary_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    invoice_status = models.CharField(max_length=20, choices=InvoiceStatusChoices.choices, default=InvoiceStatusChoices.DRAFT)
    payment_plan = models.ForeignKey("PaymentPlan", on_delete=models.SET_NULL, null=True, blank=True)
    last_reminder = models.DateTimeField(null=True, blank=True)
    reminder_count = models.PositiveSmallIntegerField(default=0)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey("accounts.CustomUser", on_delete=models.SET_NULL, null=True, related_name="invoices_created", )
    approved_by = models.ForeignKey("accounts.CustomUser",  on_delete=models.SET_NULL,  null=True,  blank=True,  related_name="invoices_approved", )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-issue_date"]
        indexes = [
            models.Index(fields=["student", "invoice_status"]),
            models.Index(fields=["due_date", "invoice_status"]),
        ]

    def __str__(self):
        return f"{self.invoice_number} – {self.student.admission_number}"

    def clean(self):
        super().clean()
        if self.due_date and self.issue_date and self.due_date < self.issue_date:
            raise ValidationError(
                {"due_date": _("Due date cannot be before issue date.")}
            )
        if self.student_id and self.school_id:
            if self.student.school_id != self.school_id:
                raise ValidationError(
                    {"student": _("Student must belong to this school.")}
                )
        if self.academic_year_id and self.school_id:
            if self.academic_year.school_id != self.school_id:
                raise ValidationError(
                    {"academic_year": _("Year must belong to this school.")}
                )
        if self.term_id and self.academic_year_id:
            if self.term.academic_year_id != self.academic_year_id:
                raise ValidationError(
                    {"term": _("Term must belong to the academic year.")}
                )

    def save(self, *args, **kwargs):
        validate = kwargs.pop("validate", True)

        if not self.invoice_number:
            with transaction.atomic():
                year = timezone.now().year
                code = _school_code(self.school)
                prefix = f"INV/{code}/{year}/"
                last = (
                    FeeInvoice.objects.select_for_update()
                    .filter(invoice_number__startswith=prefix)
                    .order_by("-invoice_number")
                    .first()
                )
                num = int(last.invoice_number.split("/")[-1]) + 1 if last else 1
                self.invoice_number = f"{prefix}{num:04d}"

        self.net_payable = (
            (self.total_amount or Decimal("0"))
            + (self.previous_balance or Decimal("0"))
            + (self.late_fee_accrued or Decimal("0"))
            - (self.waiver_amount or Decimal("0"))
            - (self.bursary_amount or Decimal("0"))
        )
        self.balance = max(Decimal("0"), self.net_payable - (self.amount_paid or Decimal("0")))

        # Status: never force out of DRAFT here
        if self.invoice_status != InvoiceStatusChoices.DRAFT:
            if self.balance <= 0 and self.net_payable >= 0:
                self.invoice_status = InvoiceStatusChoices.PAID
            elif (self.amount_paid or 0) > 0:
                self.invoice_status = InvoiceStatusChoices.PARTIALLY_PAID
            elif self.due_date and self.due_date < timezone.now().date():
                self.invoice_status = InvoiceStatusChoices.OVERDUE
            elif self.invoice_status not in (
                InvoiceStatusChoices.CANCELLED,
                InvoiceStatusChoices.VOID,
            ):
                # keep CANCELLED/VOID; otherwise ensure issued-like status stays sensible
                if self.invoice_status not in (
                    InvoiceStatusChoices.ISSUED,
                    InvoiceStatusChoices.PARTIALLY_PAID,
                    InvoiceStatusChoices.OVERDUE,
                    InvoiceStatusChoices.PAID,
                ):
                    self.invoice_status = InvoiceStatusChoices.ISSUED

        if validate:
            self.full_clean()
        super().save(*args, **kwargs)


class Payment(models.Model):
    """Records of money received."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment_reference = models.CharField(max_length=100, unique=True, editable=False)
    invoice = models.ForeignKey(FeeInvoice, on_delete=models.PROTECT, related_name="payments")
    student = models.ForeignKey("students.StudentProfile", on_delete=models.PROTECT)
    school = models.ForeignKey("schools.School", on_delete=models.PROTECT)
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0"))])
    method = models.CharField(max_length=30, choices=PaymentMethodChoices.choices)
    paid_at = models.DateTimeField(default=timezone.now)
    received_by = models.ForeignKey("accounts.CustomUser",on_delete=models.SET_NULL,null=True,related_name="payments_received",)
    verified_by = models.ForeignKey( "accounts.CustomUser",on_delete=models.SET_NULL,null=True,blank=True,related_name="payments_verified",)
    mpesa_receipt = models.CharField(max_length=50, blank=True)
    bank_ref = models.CharField(max_length=100, blank=True)
    cheque_no = models.CharField(max_length=50, blank=True)
    ledger_posted = models.BooleanField(default=False)
    payment_status = models.CharField(max_length=20, choices=PaymentStatusChoices.choices, default=PaymentStatusChoices.PENDING)
    reversal_reason = models.TextField(blank=True)
    receipt_number = models.CharField(max_length=50, blank=True)
    receipt_issued_at = models.DateTimeField(null=True, blank=True)
    parent_acknowledged = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-paid_at"]
        indexes = [
            models.Index(fields=["student", "payment_status"]),
            models.Index(fields=["payment_reference"]),
        ]

    def __str__(self):
        return f"{self.payment_reference} – KES {self.amount}"

    def save(self, *args, **kwargs):
        validate = kwargs.pop("validate", True)

        if not self.payment_reference:
            with transaction.atomic():
                year = timezone.now().year
                code = _school_code(self.school)
                prefix_map = {
                    PaymentMethodChoices.MPESA: "MP",
                    PaymentMethodChoices.CASH: "CSH",
                    PaymentMethodChoices.BANK_TRANSFER: "BT",
                }
                prefix = prefix_map.get(self.method, "PAY")
                base = f"{prefix}/{code}/{year}/"
                last = (
                    Payment.objects.select_for_update()
                    .filter(payment_reference__startswith=base)
                    .order_by("-payment_reference")
                    .first()
                )
                num = int(last.payment_reference.split("/")[-1]) + 1 if last else 1
                self.payment_reference = f"{base}{num:05d}"

        if validate:
            self.full_clean()
        super().save(*args, **kwargs)


    def clean(self):
        super().clean()
        if self.invoice_id and self.student_id:
            if self.invoice.student_id != self.student_id:
                raise ValidationError(
                    {"student": _("Must match invoice student.")}
                )
        if self.invoice_id and self.school_id:
            if self.invoice.school_id != self.school_id:
                raise ValidationError(
                    {"school": _("Must match invoice school.")}
                )


class PaymentPlan(models.Model):
    """Installment agreement for a student per term."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey("students.StudentProfile", on_delete=models.CASCADE)
    term = models.ForeignKey("schools.Term", on_delete=models.PROTECT)
    school = models.ForeignKey("schools.School", on_delete=models.PROTECT)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    installment_count = models.PositiveSmallIntegerField(default=1)
    installment_amount = models.DecimalField(max_digits=12, decimal_places=2)
    start_date = models.DateField()
    frequency = models.CharField(max_length=20, choices=PaymentFrequencyChoices.choices, default=PaymentFrequencyChoices.MONTHLY)
    next_due_date = models.DateField()
    agreement_signed = models.BooleanField(default=False)
    signed_by = models.ForeignKey("accounts.CustomUser", on_delete=models.SET_NULL, null=True, blank=True)
    plan_status = models.CharField(max_length=20, choices=PaymentPlanStatusChoices.choices, default=PaymentPlanStatusChoices.ACTIVE,)
    default_count = models.PositiveSmallIntegerField(default=0)
    last_payment_date = models.DateField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [["student", "term"]]
        ordering = ["-start_date"]

    def __str__(self):
        return f"{self.student.admission_number} – {self.term.name} Plan"

    def save(self, *args, **kwargs):
        validate = kwargs.pop("validate", True)
        if self.installment_count and self.total_amount is not None:
            if not self.installment_amount:
                self.installment_amount = (
                    self.total_amount / Decimal(self.installment_count)
                ).quantize(Decimal("0.01"))
        if not self.next_due_date and self.start_date:
            self.next_due_date = self.start_date
        if validate:
            self.full_clean()
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        if self.student_id and self.school_id:
            if self.student.school_id != self.school_id:
                raise ValidationError(
                    {"student": _("Student must belong to this school.")}
                )

        def get_status_display(self):
            """Get human-readable status"""
            return dict(PaymentPlanStatusChoices.choices).get(self.status, self.status)

        # FIXED: Add property for backward compatibility
        @property
        def payment_plan_status(self):
            return self.status

        @payment_plan_status.setter
        def payment_plan_status(self, value):
            self.status = value


class Bursary(models.Model):
    """Scholarship / bursary award record."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey("students.StudentProfile", on_delete=models.CASCADE)
    school = models.ForeignKey("schools.School", on_delete=models.PROTECT)
    source = models.CharField(max_length=30, choices=BursarySourceChoices.choices)
    amount_awarded = models.DecimalField(max_digits=12, decimal_places=2)
    term = models.ForeignKey("schools.Term", on_delete=models.PROTECT)
    academic_year = models.ForeignKey("schools.AcademicYear", on_delete=models.PROTECT)
    reason = models.TextField()
    application_date = models.DateField(default=timezone.now)
    approval_date = models.DateField(null=True, blank=True)
    approved_by = models.ForeignKey("accounts.CustomUser", on_delete=models.SET_NULL, null=True, blank=True)
    disbursement_date = models.DateField(null=True, blank=True)
    bursary_status = models.CharField(max_length=20, choices=BursaryStatusChoices.choices, default=BursaryStatusChoices.APPLIED)
    renewable = models.BooleanField(default=False)
    next_review_date = models.DateField(null=True, blank=True)
    applied_to_invoice = models.ForeignKey("FeeInvoice",on_delete=models.SET_NULL,null=True,blank=True,related_name="bursaries_applied",)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    class Meta:
        ordering = ["-application_date"]
        indexes = [
            models.Index(fields=["student", "bursary_status"]),
        ]

    def __str__(self):
        return f"{self.student.admission_number} – {self.get_source_display()} – {self.amount_awarded}"

    def clean(self):
        super().clean()
        if self.student_id and self.school_id:
            if self.student.school_id != self.school_id:
                raise ValidationError(
                    {"student": _("Student must belong to this school.")}
                )
class FinancialTransaction(models.Model):
    """General ledger transactions"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transaction_type = models.CharField(max_length=20, choices=TransactionTypeChoices.choices)
    finance_category = models.CharField(max_length=20, choices=FinanceCategoryChoices.choices)
    school = models.ForeignKey("schools.School", on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0"))])
    currency = models.CharField(max_length=3, default="KES")
    date = models.DateField(default=timezone.now)
    description = models.TextField(blank=True)
    reference_number = models.CharField(max_length=100, blank=True)
    account_debit = models.CharField(max_length=50)  # GL code
    account_credit = models.CharField(max_length=50)  # GL code
    approved_by = models.ForeignKey( "accounts.CustomUser",on_delete=models.SET_NULL,null=True,blank=True,related_name="approved_transactions",)
    verified_by = models.ForeignKey("accounts.CustomUser",on_delete=models.SET_NULL,null=True,blank=True,related_name="verified_transactions",)
    attachments = models.JSONField(default=list, blank=True)
    transaction_status = models.CharField(max_length=20,choices=FinanceTransactionStatusChoices.choices, default=FinanceTransactionStatusChoices.PENDING,)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "-created_at"]
        verbose_name = _("Financial Transaction")
        verbose_name_plural = _("Financial Transactions")

    def __str__(self):
        return f"{self.get_transaction_type_display()} - {self.amount} - {self.date}"

    def clean(self):
        """Validate transaction"""
        if self.amount <= 0:
            raise ValidationError({"amount": "Amount must be greater than zero"})


class BankReconciliation(models.Model):
    """Bank statement reconciliation"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    bank_account = models.CharField(max_length=100)
    statement_date = models.DateField()
    opening_balance = models.DecimalField(max_digits=12, decimal_places=2)
    closing_balance = models.DecimalField(max_digits=12, decimal_places=2)
    reconciled_by = models.ForeignKey("accounts.CustomUser", on_delete=models.SET_NULL, null=True)
    reconciled_at = models.DateTimeField(auto_now_add=True)
    discrepancies = models.JSONField(default=list, blank=True)

class Receipt(models.Model):
    """Official payment receipts"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    receipt_number = models.CharField(max_length=50, unique=True)
    payment = models.OneToOneField( Payment, on_delete=models.CASCADE, related_name="receipt")
    issued_at = models.DateTimeField(default=timezone.now)
    issued_by = models.ForeignKey("accounts.CustomUser", on_delete=models.SET_NULL, null=True)
    printed_count = models.PositiveIntegerField(default=0)
    voided = models.BooleanField(default=False)
    void_reason = models.TextField(blank=True)