import uuid
from django.db import models
from decimal import Decimal
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.contrib.auth import get_user_model

CustomUser = get_user_model()


class FeeStructure(models.Model):
    """Fee structure for classes/terms"""
    
    class FeesCategoryChoices(models.TextChoices):
        TUITION = 'tuition', _('Tuition')
        BOARDING = 'boarding', _('Boarding')
        ACTIVITY = 'activity', _('Activity')
        EXAM = 'exam', _('Exam')
        DEVELOPMENT = 'development', _('Development')
        OTHER = 'other', _('Other')
    
    class FeesStatusChoices(models.TextChoices):
        DRAFT = 'draft', _('Draft')
        APPROVED = 'approved', _('Approved')
        ACTIVE = 'active', _('Active')
        ARCHIVED = 'archived', _('Archived')
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey('schools.School', on_delete=models.CASCADE)
    class_level = models.CharField(max_length=50)  # e.g., "Form 2", "Grade 5"
    term = models.ForeignKey('schools.Term', on_delete=models.CASCADE)
    academic_year = models.ForeignKey('schools.AcademicYear', on_delete=models.CASCADE)

    fees_category = models.CharField(max_length=20, choices=FeesCategoryChoices.choices)
    description = models.TextField(blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0'))])
    
    due_date = models.DateField()
    late_fee_per_day = models.DecimalField(max_digits=10, decimal_places=2, default=0, validators=[MinValueValidator(Decimal('0'))])

    is_compulsory = models.BooleanField(default=True)
    is_refundable = models.BooleanField(default=False)
    
    account_code = models.CharField(max_length=50, blank=True)
    gl_account = models.CharField(max_length=50, blank=True)
    taxable = models.BooleanField(default=False)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0, validators=[MinValueValidator(Decimal('0'))])
    created_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, related_name='created_fees')
    approved_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_fees')
    
    effective_date = models.DateField(default=timezone.now)
    expiry_date = models.DateField(null=True, blank=True)
    fees_status = models.CharField(max_length=20, choices=FeesStatusChoices.choices, default=FeesStatusChoices.DRAFT)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = [['school', 'class_level', 'term', 'academic_year', 'fees_category']]
        ordering = ['class_level', 'fees_category']
        verbose_name = _('Fee Structure')
        verbose_name_plural = _('Fee Structures')
    
    def __str__(self):
        return f"{self.class_level} - {self.get_fees_category_display()} - {self.amount}"
    
    def clean(self):
        """Validate fee structure"""
        if self.expiry_date and self.expiry_date < self.effective_date:
            raise ValidationError({'expiry_date': 'Expiry date cannot be before effective date'})
        
        if self.due_date < self.effective_date:
            raise ValidationError({'due_date': 'Due date cannot be before effective date'})


class PaymentPlan(models.Model):
    """Payment plan for installments"""
    
    class FrequencyChoices(models.TextChoices):
        WEEKLY = 'weekly', _('Weekly')
        BIWEEKLY = 'biweekly', _('Biweekly')
        MONTHLY = 'monthly', _('Monthly')
        CUSTOM = 'custom', _('Custom')
    
    class PaymentPlanStatusChoices(models.TextChoices):
        ACTIVE = 'active', _('Active')
        COMPLETED = 'completed', _('Completed')
        DEFAULTED = 'defaulted', _('Defaulted')
        CANCELLED = 'cancelled', _('Cancelled')
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey('students.Student', on_delete=models.CASCADE)
    term = models.ForeignKey('schools.Term', on_delete=models.CASCADE)
    school = models.ForeignKey('schools.School', on_delete=models.CASCADE)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0'))])
    installment_count = models.PositiveIntegerField(default=1)
    installment_amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0'))])
    
    start_date = models.DateField()
    frequency = models.CharField(max_length=20, choices=FrequencyChoices.choices, default=FrequencyChoices.MONTHLY)
    
    agreement_signed = models.BooleanField(default=False)
    signed_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True)
    signature_date = models.DateField(null=True, blank=True)
    
    payment_plan_status = models.CharField(max_length=20, choices=PaymentPlanStatusChoices.choices, default=PaymentPlanStatusChoices.ACTIVE)
    default_count = models.PositiveIntegerField(default=0)
    last_payment_date = models.DateField(null=True, blank=True)
    next_due_date = models.DateField()
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = [['student', 'term']]
        verbose_name = _('Payment Plan')
        verbose_name_plural = _('Payment Plans')
    
    def __str__(self):
        return f"{self.student.admission_number} - {self.term.name}"
    
    def clean(self):
        """Validate payment plan"""
        if self.installment_amount * self.installment_count != self.total_amount:
            raise ValidationError('Total amount must equal installment amount × count')
        
        if self.next_due_date < self.start_date:
            raise ValidationError({'next_due_date': 'Next due date cannot be before start date'})


class FeeInvoice(models.Model):
    """Fee invoice for students"""
    
    class FeeInvoiceStatusChoices(models.TextChoices):
        DRAFT = 'draft', _('Draft')
        ISSUED = 'issued', _('Issued')
        PARTIALLY_PAID = 'partially_paid', _('Partially Paid')
        PAID = 'paid', _('Paid')
        OVERDUE = 'overdue', _('Overdue')
        WRITTEN_OFF = 'written_off', _('Written Off')
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice_number = models.CharField(max_length=50, unique=True, editable=False)
    school = models.ForeignKey('schools.School', on_delete=models.CASCADE)
    student = models.ForeignKey('students.Student', on_delete=models.CASCADE)
    term = models.ForeignKey('schools.Term', on_delete=models.CASCADE)
    academic_year = models.ForeignKey('schools.AcademicYear', on_delete=models.CASCADE)
    
    issue_date = models.DateField(default=timezone.now)
    due_date = models.DateField()
    
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0'))])
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(Decimal('0'))])
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    previous_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    late_fee = models.DecimalField(max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(Decimal('0'))])
    waiver_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(Decimal('0'))])
    scholarship_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(Decimal('0'))])
    net_payable = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0'))])
    
    invoice_status = models.CharField(max_length=20, choices=FeeInvoiceStatusChoices.choices, default=FeeInvoiceStatusChoices.DRAFT)
    payment_plan = models.ForeignKey(PaymentPlan, on_delete=models.SET_NULL, null=True, blank=True)
    
    last_reminder_sent = models.DateTimeField(null=True, blank=True)
    reminder_count = models.PositiveIntegerField(default=0)
    notes = models.TextField(blank=True)
    
    created_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, related_name='created_invoices')
    approved_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_invoices')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-issue_date', 'student']
        verbose_name = _('Fee Invoice')
        verbose_name_plural = _('Fee Invoices')
        indexes = [
            models.Index(fields=['student', 'term']),
            models.Index(fields=['invoice_status']),
            models.Index(fields=['due_date']),
        ]
    
    def __str__(self):
        return f"{self.invoice_number} - {self.student.admission_number}"
    
    def clean(self):
        """Validate invoice"""
        if self.due_date < self.issue_date:
            raise ValidationError({'due_date': 'Due date cannot be before issue date'})
        
        # Calculate net payable
        self.net_payable = self.total_amount + self.previous_balance + self.late_fee - self.waiver_amount - self.scholarship_amount
        
        # Calculate balance
        self.balance = max(0, self.net_payable - self.amount_paid)
        
        # Auto-update status
        if self.net_payable > 0:
            if self.amount_paid >= self.net_payable:
                self.invoice_status = self.FeeInvoiceStatusChoices.PAID
            elif self.amount_paid > 0:
                self.invoice_status = self.FeeInvoiceStatusChoices.PARTIALLY_PAID
            elif self.due_date < timezone.now().date():
                self.invoice_status = self.FeeInvoiceStatusChoices.OVERDUE
            else:
                self.invoice_status = self.FeeInvoiceStatusChoices.ISSUED
    
    def save(self, *args, **kwargs):
        # Generate invoice number if new
        if not self.invoice_number:
            from datetime import datetime
            year = datetime.now().year
            last_invoice = FeeInvoice.objects.filter(
                invoice_number__startswith=f"SCH/INV/{year}/"
            ).order_by('invoice_number').last()
            
            if last_invoice:
                last_number = int(last_invoice.invoice_number.split('/')[-1])
                new_number = last_number + 1
            else:
                new_number = 1
            
            self.invoice_number = f"SCH/INV/{year}/{new_number:03d}"
        
        self.clean()
        super().save(*args, **kwargs)


class Payment(models.Model):
    """Payment records"""
    
    class MethodChoices(models.TextChoices):
        CASH = 'cash', _('Cash')
        MPESA = 'mpesa', _('Mpesa')
        BANK_TRANSFER = 'bank_transfer', _('Bank Transfer')
        CHEQUE = 'cheque', _('Cheque')
        CARD = 'card', _('Card')
        SACCO = 'sacco', _('SACCO')
    
    class ChannelChoices(models.TextChoices):
        COUNTER = 'counter', _('Counter')
        PAYBILL = 'paybill', _('Paybill')
        TILL = 'till', _('Till')
        AGENT = 'agent', _('Agent')
        ONLINE = 'online', _('Online')
    
    class PaymentStatusChoices(models.TextChoices):
        PENDING = 'pending', _('Pending')
        COMPLETED = 'completed', _('Completed')
        FAILED = 'failed', _('Failed')
        REVERSED = 'reversed', _('Reversed')
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment_reference = models.CharField(max_length=100, unique=True, editable=False)
    
    invoice = models.ForeignKey(FeeInvoice, on_delete=models.CASCADE, related_name='payments')
    student = models.ForeignKey('students.Student', on_delete=models.CASCADE)  # Denormalized for speed
    school = models.ForeignKey('schools.School', on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0'))])
    method = models.CharField(max_length=20, choices=MethodChoices.choices)
    channel = models.CharField(max_length=20, choices=ChannelChoices.choices)
    
    mpesa_code = models.CharField(max_length=50, blank=True)
    bank_transaction_ref = models.CharField(max_length=100, blank=True)
    cheque_number = models.CharField(max_length=50, blank=True)
    card_last4 = models.CharField(max_length=4, blank=True)
    
    paid_at = models.DateTimeField(default=timezone.now)
    received_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, related_name='received_payments')
    verified_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='verified_payments')
    
    payment_status = models.CharField(max_length=20, choices=PaymentStatusChoices.choices, default=PaymentStatusChoices.PENDING)
    reversal_reason = models.TextField(blank=True)
    
    receipt_issued = models.BooleanField(default=False)
    receipt_number = models.CharField(max_length=50, blank=True)
    parent_acknowledged = models.BooleanField(default=False)
    narration = models.TextField(blank=True)
    attachments = models.JSONField(default=list, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-paid_at']
        verbose_name = _('Payment')
        verbose_name_plural = _('Payments')
        indexes = [
            models.Index(fields=['student', 'paid_at']),
            models.Index(fields=['method', 'payment_status']),
            models.Index(fields=['payment_reference']),
        ]
    
    def __str__(self):
        return f"{self.payment_reference} - {self.amount}"
    
    def clean(self):
        """Validate payment"""
        if self.amount <= 0:
            raise ValidationError({'amount': 'Payment amount must be greater than zero'})
    
    def save(self, *args, **kwargs):
        # Generate payment reference if new
        if not self.payment_reference:
            from datetime import datetime
            year = datetime.now().year
            
            method_prefix = {
                'cash': 'CASH',
                'mpesa': 'MPESA',
                'bank_transfer': 'BNK',
                'cheque': 'CHQ',
                'card': 'CARD',
                'sacco': 'SACCO',
            }.get(self.method, 'PAY')
            
            last_payment = Payment.objects.filter(
                payment_reference__startswith=f"{method_prefix}/{year}/"
            ).order_by('payment_reference').last()
            
            if last_payment:
                last_number = int(last_payment.payment_reference.split('/')[-1])
                new_number = last_number + 1
            else:
                new_number = 1
            self.payment_reference = f"{method_prefix}/{year}/{new_number:03d}"
        super().save(*args, **kwargs)
    
       



class FinancialTransaction(models.Model):
    """General ledger transactions"""
    
    class TransactionTypeChoices(models.TextChoices):
        INCOME = 'income', _('Income')
        EXPENSE = 'expense', _('Expense')
        TRANSFER = 'transfer', _('Transfer')
        ADJUSTMENT = 'adjustment', _('Adjustment')
    
    class FinanceCategoryChoices(models.TextChoices):
        FEES = 'fees', _('Fees')
        SALARY = 'salary', _('Salary')
        SUPPLIES = 'supplies', _('Supplies')
        UTILITIES = 'utilities', _('Utilities')
        MAINTENANCE = 'maintenance', _('Maintenance')
        OTHER = 'other', _('Other')
    
    class FinanceTransactionStatusChoices(models.TextChoices):
        PENDING = 'pending', _('Pending')
        APPROVED = 'approved', _('Approved')
        POSTED = 'posted', _('Posted')
        REJECTED = 'rejected', _('Rejected')
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    transaction_type = models.CharField(max_length=20, choices=TransactionTypeChoices.choices)
    finance_category = models.CharField(max_length=20, choices=FinanceCategoryChoices.choices)
    school = models.ForeignKey('schools.School', on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0'))])
    currency = models.CharField(max_length=3, default='KES')
    date = models.DateField(default=timezone.now)
    description = models.TextField(blank=True)
    reference_number = models.CharField(max_length=100, blank=True)
    
    account_debit = models.CharField(max_length=50)  # GL code
    account_credit = models.CharField(max_length=50)  # GL code
    
    approved_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_transactions')
    verified_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='verified_transactions')
    
    attachments = models.JSONField(default=list, blank=True)
    transaction_status = models.CharField(max_length=20, choices=FinanceTransactionStatusChoices.choices, default=FinanceTransactionStatusChoices.PENDING)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-date', '-created_at']
        verbose_name = _('Financial Transaction')
        verbose_name_plural = _('Financial Transactions')
    
    def __str__(self):
        return f"{self.get_transaction_type_display()} - {self.amount} - {self.date}"
    
    def clean(self):
        """Validate transaction"""
        if self.amount <= 0:
            raise ValidationError({'amount': 'Amount must be greater than zero'})


class Bursary(models.Model):
    """Bursary/Scholarship awards"""
    
    class BursaryTypeChoices(models.TextChoices):
        COUNTY = 'county', _('County')
        CDF = 'cdf', _('CDF')
        NGO = 'ngo', _('NGO')
        SCHOOL = 'school', _('School')
        INDIVIDUAL = 'individual', _('Individual')
    
    class BursaryStatusChoices(models.TextChoices):
        APPLIED = 'applied', _('Applied')
        APPROVED = 'approved', _('Approved')
        DISBURSED = 'disbursed', _('Disbursed')
        REJECTED = 'rejected', _('Rejected')
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey('students.Student', on_delete=models.CASCADE)
    school = models.ForeignKey('schools.School', on_delete=models.CASCADE)
    type = models.CharField(max_length=20, choices=BursaryTypeChoices.choices)
    amount_awarded = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0'))])
    
    term = models.ForeignKey('schools.Term', on_delete=models.CASCADE)
    academic_year = models.ForeignKey('schools.AcademicYear', on_delete=models.CASCADE)
    
    reason = models.TextField()
    application_date = models.DateField(default=timezone.now)
    approval_date = models.DateField(null=True, blank=True)
    approved_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True)
    disbursement_date = models.DateField(null=True, blank=True)
    
    bursary_status = models.CharField(max_length=20, choices=BursaryStatusChoices.choices, default=BursaryStatusChoices.APPLIED)
    conditions = models.TextField(blank=True)
    performance_requirement = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True,
                                                validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))])
    renewable = models.BooleanField(default=False)
    next_review_date = models.DateField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('Bursary')
        verbose_name_plural = _('Bursaries')
        indexes = [
            models.Index(fields=['student', 'academic_year']),
            models.Index(fields=['bursary_status']),
        ]
    
    def __str__(self):
        return f"{self.student.admission_number} - {self.get_type_display()} - {self.amount_awarded}"
    
    def clean(self):
        """Validate bursary"""
        if self.approval_date and self.approval_date < self.application_date:
            raise ValidationError({'approval_date': 'Approval date cannot be before application date'})
        
        if self.disbursement_date and self.approval_date and self.disbursement_date < self.approval_date:
            raise ValidationError({'disbursement_date': 'Disbursement date cannot be before approval date'})
        


class BankReconciliation(models.Model):
    """Bank statement reconciliation"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    bank_account = models.CharField(max_length=100)
    statement_date = models.DateField()
    opening_balance = models.DecimalField(max_digits=12, decimal_places=2)
    closing_balance = models.DecimalField(max_digits=12, decimal_places=2)
    reconciled_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True)
    reconciled_at = models.DateTimeField(auto_now_add=True)
    discrepancies = models.JSONField(default=list, blank=True)


class Receipt(models.Model):
    """Official payment receipts"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    receipt_number = models.CharField(max_length=50, unique=True)
    payment = models.OneToOneField(Payment, on_delete=models.CASCADE, related_name='receipt')
    issued_at = models.DateTimeField(default=timezone.now)
    issued_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True)
    printed_count = models.PositiveIntegerField(default=0)
    voided = models.BooleanField(default=False)
    void_reason = models.TextField(blank=True)