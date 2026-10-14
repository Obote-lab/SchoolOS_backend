from decimal import Decimal
from django.db import models, transaction
from django.utils import timezone
from rest_framework import serializers
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from core.choices.finance import (
    BursaryStatusChoices,
    FeesStatusChoices,
    InvoiceStatusChoices,
    PaymentMethodChoices,
    PaymentPlanStatusChoices,
    PaymentStatusChoices,
)
from schools.models import AcademicYear, Term
from students.models import StudentProfile

from ..models import (
    Bursary,
    FeeInvoice,
    FeeStructure,
    FinancialTransaction,
    InvoiceItem,
    Payment,
    PaymentAllocation,
    PaymentPlan,
)


# Helpers
def get_related_display(obj, field_name, attr="name", fallback=None):
    related = getattr(obj, field_name, None)
    if not related:
        return fallback
    try:
        return getattr(related, attr, str(related))
    except Exception:
        return fallback


# InvoiceItem
class InvoiceItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceItem
        fields = [
            "id",
            "fee_structure",
            "description",
            "fees_category",
            "quantity",
            "unit_amount",
            "amount",
            "is_compulsory",
        ]
        read_only_fields = ["id", "amount"]


class InvoiceItemCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceItem
        fields = [
            "fee_structure",
            "description",
            "fees_category",
            "quantity",
            "unit_amount",
            "is_compulsory",
        ]


# PaymentAllocation
class PaymentAllocationSerializer(serializers.ModelSerializer):
    invoice_number = serializers.CharField(source="invoice.invoice_number", read_only=True)

    class Meta:
        model = PaymentAllocation
        fields = [
            "id",
            "payment",
            "invoice",
            "invoice_number",
            "amount",
            "allocated_at",
            "notes",
        ]
        read_only_fields = ["id", "allocated_at"]


# FeeStructure
class FeeStructureListSerializer(serializers.ModelSerializer):
    category_display = serializers.CharField(source="get_fees_category_display", read_only=True)
    status_display = serializers.CharField(source="get_fees_status_display", read_only=True)
    approved_by_name = serializers.CharField(source="approved_by.get_full_name", read_only=True, allow_null=True)
    level_name = serializers.CharField(source="level.name", read_only=True, allow_null=True)

    class Meta:
        model = FeeStructure
        fields = [
            "id",
            "class_level",
            "level",
            "level_name",
            "fees_category",
            "category_display",
            "description",
            "amount",
            "due_date",
            "fees_status",
            "status_display",
            "approved_by",
            "approved_by_name",
            "is_compulsory",
        ]


class FeeStructureDetailSerializer(serializers.ModelSerializer):
    category_display = serializers.CharField(source="get_fees_category_display", read_only=True)
    status_display = serializers.CharField(source="get_fees_status_display", read_only=True)
    approved_by_name = serializers.CharField(source="approved_by.get_full_name", read_only=True, allow_null=True)
    school_name = serializers.CharField(source="school.school_name", read_only=True)
    term_name = serializers.CharField(source="term.name", read_only=True)
    academic_year_name = serializers.CharField(source="academic_year.year", read_only=True)
    level_name = serializers.CharField(source="level.name", read_only=True, allow_null=True)

    class Meta:
        model = FeeStructure
        fields = "__all__"
        read_only_fields = ["id", "created_at", "updated_at"]


class FeeStructureCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeeStructure
        fields = [
            "school",
            "class_level",
            "level",
            "term",
            "academic_year",
            "fees_category",
            "description",
            "amount",
            "due_date",
            "late_fee_per_day",
            "is_compulsory",
            "is_refundable",
            "gl_account",
            "taxable",
            "tax_rate",
        ]

    def create(self, validated_data):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            validated_data["created_by"] = request.user
        return super().create(validated_data)



# FeeInvoice
class FeeInvoiceListSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.user.get_full_name", read_only=True)
    student_admission = serializers.CharField(source="student.admission_number", read_only=True)
    status_display = serializers.CharField(source="get_invoice_status_display", read_only=True)

    class Meta:
        model = FeeInvoice
        fields = [
            "id",
            "invoice_number",
            "student",
            "student_name",
            "student_admission",
            "total_amount",
            "amount_paid",
            "balance",
            "net_payable",
            "due_date",
            "invoice_status",
            "status_display",
        ]



# Payment
class PaymentListSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.user.get_full_name", read_only=True)
    method_display = serializers.CharField(source="get_method_display", read_only=True)
    status_display = serializers.CharField(source="get_payment_status_display", read_only=True)
    invoice_number = serializers.CharField( source="invoice.invoice_number", read_only=True, allow_null=True)

    class Meta:
        model = Payment
        fields = [
            "id",
            "payment_reference",
            "student",
            "student_name",
            "invoice",
            "invoice_number",
            "amount",
            "method",
            "method_display",
            "payment_status",
            "status_display",
            "mpesa_receipt",
            "paid_at",
        ]


class FeeInvoiceDetailSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.user.get_full_name", read_only=True)
    student_admission = serializers.CharField(source="student.admission_number", read_only=True)
    status_display = serializers.CharField(source="get_invoice_status_display", read_only=True)
    term_name = serializers.CharField(source="term.name", read_only=True)
    academic_year_name = serializers.CharField(source="academic_year.year", read_only=True)
    created_by_name = serializers.CharField(source="created_by.get_full_name", read_only=True, allow_null=True)
    items = InvoiceItemSerializer(many=True, read_only=True)
    payments = serializers.SerializerMethodField()
    allocations = PaymentAllocationSerializer(many=True, read_only=True)

    class Meta:
        model = FeeInvoice
        fields = "__all__"
        read_only_fields = [
            "id",
            "invoice_number",
            "created_at",
            "updated_at",
            "items",
            "payments",
            "allocations",
        ]

    @extend_schema_field(PaymentListSerializer(many=True))
    def get_payments(self, obj):
        return PaymentListSerializer(obj.payments.all(), many=True).data


class FeeInvoiceCreateSerializer(serializers.ModelSerializer):
    items = InvoiceItemCreateSerializer(many=True, required=False)

    class Meta:
        model = FeeInvoice
        fields = [
            "student",
            "term",
            "academic_year",
            "due_date",
            "previous_balance",
            "late_fee_accrued",
            "waiver_amount",
            "payment_plan",
            "notes",
            "items",
        ]

    @transaction.atomic
    def create(self, validated_data):
        items_data = validated_data.pop("items", [])
        request = self.context.get("request")

        validated_data["created_by"] = request.user
        validated_data["issue_date"] = timezone.now().date()
        validated_data["school"] = validated_data["student"].school

        invoice = super().create(validated_data)

        for item in items_data:
            InvoiceItem.objects.create(invoice=invoice, **item)

        invoice.recalculate_totals(save=True)
        return invoice


class PaymentDetailSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.user.get_full_name", read_only=True)
    student_admission = serializers.CharField(source="student.admission_number", read_only=True)
    method_display = serializers.CharField(source="get_method_display", read_only=True)
    status_display = serializers.CharField(source="get_payment_status_display", read_only=True)
    received_by_name = serializers.CharField(source="received_by.get_full_name", read_only=True, allow_null=True)
    verified_by_name = serializers.CharField(source="verified_by.get_full_name", read_only=True, allow_null=True)
    invoice_number = serializers.CharField(source="invoice.invoice_number", read_only=True, allow_null=True)
    allocations = PaymentAllocationSerializer(many=True, read_only=True)

    class Meta:
        model = Payment
        fields = "__all__"
        read_only_fields = ["id", "payment_reference", "created_at", "updated_at"]


class PaymentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = [
            "invoice",
            "student",
            "amount",
            "method",
            "mpesa_receipt",
            "bank_ref",
            "cheque_no",
            "mpesa_phone",
        ]

    def create(self, validated_data):
        request = self.context.get("request")
        validated_data["received_by"] = request.user
        validated_data["paid_at"] = timezone.now()
        validated_data["school"] = validated_data["student"].school
        return super().create(validated_data)


class RecordPaymentSerializer(serializers.Serializer):
    """Record a manual payment against an invoice (cash / bank / mpesa code)."""

    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    method = serializers.ChoiceField(choices=PaymentMethodChoices.choices)
    mpesa_code = serializers.CharField(required=False, allow_blank=True)
    bank_transaction_ref = serializers.CharField(required=False, allow_blank=True)
    narration = serializers.CharField(required=False, allow_blank=True)
    mark_completed = serializers.BooleanField(default=True,help_text="If true, payment is immediately marked COMPLETED (triggers ledger + allocation).",)

    @transaction.atomic
    def create(self, validated_data):
        invoice = self.context["invoice"]
        request = self.context["request"]

        status = (
            PaymentStatusChoices.COMPLETED
            if validated_data.get("mark_completed", True)
            else PaymentStatusChoices.PENDING
        )

        payment = Payment.objects.create(
            invoice=invoice,
            student=invoice.student,
            school=invoice.school,
            amount=validated_data["amount"],
            method=validated_data["method"],
            mpesa_receipt=validated_data.get("mpesa_code", ""),
            bank_ref=validated_data.get("bank_transaction_ref", ""),
            received_by=request.user,
            paid_at=timezone.now(),
            payment_status=status,
        )
        # Signals will auto-create PaymentAllocation + post to ledger when COMPLETED
        return payment



# Generate Invoice (creates line items)
class GenerateInvoiceSerializer(serializers.Serializer):
    student_id = serializers.UUIDField(required=True)
    term_id = serializers.UUIDField(required=True)
    academic_year_id = serializers.UUIDField(required=True)

    @transaction.atomic
    def create(self, validated_data):
        request = self.context["request"]
        school = getattr(request, "school", None)

        student = StudentProfile.objects.get(id=validated_data["student_id"])
        if school and student.school_id != school.id:
            raise serializers.ValidationError("Student not in this school.")

        term = Term.objects.get(id=validated_data["term_id"])
        academic_year = AcademicYear.objects.get(id=validated_data["academic_year_id"])

        class_level = (
            student.current_class.level
            if student.current_class_id
            else "General"
        )

        fee_structures = FeeStructure.objects.filter(
            school=student.school,
            class_level=class_level,
            term=term,
            academic_year=academic_year,
            fees_status=FeesStatusChoices.APPROVED,
            is_compulsory=True,
        )

        invoice, created = FeeInvoice.objects.get_or_create(
            student=student,
            term=term,
            academic_year=academic_year,
            defaults={
                "school": student.school,
                "due_date": term.end_date,
                "created_by": request.user,
                "invoice_status": InvoiceStatusChoices.DRAFT,
            },
        )

        if created or invoice.invoice_status == InvoiceStatusChoices.DRAFT:
            # Clear old items and rebuild
            invoice.items.all().delete()
            for fs in fee_structures:
                InvoiceItem.objects.create(
                    invoice=invoice,
                    fee_structure=fs,
                    description=fs.description or fs.get_fees_category_display(),
                    fees_category=fs.fees_category,
                    quantity=1,
                    unit_amount=fs.amount,
                    is_compulsory=fs.is_compulsory,
                )
            invoice.recalculate_totals(save=True)

        return invoice



# Bursary
class BursaryDetailSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.user.get_full_name", read_only=True)
    student_admission = serializers.CharField(source="student.admission_number", read_only=True)
    source_display = serializers.CharField(source="get_source_display", read_only=True)
    status_display = serializers.CharField(source="get_bursary_status_display", read_only=True)
    approved_by_name = serializers.CharField(source="approved_by.get_full_name", read_only=True, allow_null=True)

    class Meta:
        model = Bursary
        fields = "__all__"
        read_only_fields = ["id", "created_at", "updated_at"]


class ApproveBursarySerializer(serializers.Serializer):
    approval_date = serializers.DateField(required=False)

    def update(self, instance, validated_data):
        instance.bursary_status = BursaryStatusChoices.APPROVED
        instance.approval_date = validated_data.get(
            "approval_date", timezone.now().date()
        )
        instance.approved_by = self.context["request"].user
        instance.save(
            update_fields=["bursary_status", "approval_date", "approved_by", "updated_at"]
        )
        return instance


# PaymentPlan
class PaymentPlanDetailSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.user.get_full_name", read_only=True)
    student_admission = serializers.CharField(source="student.admission_number", read_only=True)
    frequency_display = serializers.CharField(source="get_frequency_display", read_only=True)
    status_display = serializers.CharField(source="get_plan_status_display", read_only=True)
    signed_by_name = serializers.CharField(source="signed_by.get_full_name", read_only=True, allow_null=True)

    class Meta:
        model = PaymentPlan
        fields = "__all__"
        read_only_fields = ["id", "created_at", "updated_at"]


# FinancialTransaction
class FinancialTransactionListSerializer(serializers.ModelSerializer):
    transaction_type_display = serializers.CharField(source="get_transaction_type_display", read_only=True)
    category_display = serializers.CharField( source="get_finance_category_display", read_only=True)
    status_display = serializers.CharField(source="get_transaction_status_display", read_only=True)
    approved_by_name = serializers.CharField(source="approved_by.get_full_name", read_only=True, allow_null=True)

    class Meta:
        model = FinancialTransaction
        fields = [
            "id",
            "transaction_type",
            "transaction_type_display",
            "finance_category",
            "category_display",
            "amount",
            "date",
            "description",
            "reference_number",
            "transaction_status",
            "status_display",
            "approved_by_name",
        ]


class FinancialTransactionDetailSerializer(serializers.ModelSerializer):
    transaction_type_display = serializers.CharField(source="get_transaction_type_display", read_only=True)
    category_display = serializers.CharField(source="get_finance_category_display", read_only=True)
    status_display = serializers.CharField(source="get_transaction_status_display", read_only=True)
    approved_by_name = serializers.CharField(source="approved_by.get_full_name", read_only=True, allow_null=True)
    verified_by_name = serializers.CharField(source="verified_by.get_full_name", read_only=True, allow_null=True)

    class Meta:
        model = FinancialTransaction
        fields = "__all__"
        read_only_fields = ["id", "created_at", "updated_at"]


class FinancialTransactionCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = FinancialTransaction
        fields = [
            "transaction_type",
            "finance_category",
            "amount",
            "currency",
            "date",
            "description",
            "reference_number",
            "account_debit",
            "account_credit",
            "attachments",
        ]

    def create(self, validated_data):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            validated_data["approved_by"] = request.user
            validated_data["school"] = getattr(request, "school", None) or request.user.school
        return super().create(validated_data)



# Student Finance Summary
class StudentFinanceSummarySerializer(serializers.Serializer):
    student_id = serializers.UUIDField(required=True)

    def get_summary(self, student_id):
        try:
            student = StudentProfile.objects.get(id=student_id)
        except StudentProfile.DoesNotExist:
            raise serializers.ValidationError("Student not found")

        invoices = FeeInvoice.objects.filter(student=student)
        payments = Payment.objects.filter(
            student=student, payment_status=PaymentStatusChoices.COMPLETED
        )

        summary = {
            "student": {
                "name": student.user.get_full_name(),
                "admission_number": student.admission_number,
                "class": student.current_class.name if student.current_class else "N/A",
            },
            "total_invoiced": invoices.aggregate(models.Sum("total_amount"))[
                "total_amount__sum"
            ]
            or 0,
            "total_paid": payments.aggregate(models.Sum("amount"))["amount__sum"] or 0,
            "total_balance": invoices.aggregate(models.Sum("balance"))["balance__sum"]
            or 0,
            "active_invoices": invoices.filter(
                invoice_status__in=[
                    InvoiceStatusChoices.ISSUED,
                    InvoiceStatusChoices.PARTIALLY_PAID,
                    InvoiceStatusChoices.OVERDUE,
                ]
            ).count(),
            "paid_invoices": invoices.filter(
                invoice_status=InvoiceStatusChoices.PAID
            ).count(),
            "payment_plan": None,
            "bursaries": list(
                Bursary.objects.filter(
                    student=student, bursary_status=BursaryStatusChoices.APPROVED
                ).values("source", "amount_awarded", "term__name")
            ),
            "recent_payments": PaymentListSerializer(
                payments.order_by("-paid_at")[:5], many=True
            ).data,
        }

        active_plan = PaymentPlan.objects.filter(
            student=student, plan_status=PaymentPlanStatusChoices.ACTIVE
        ).first()
        if active_plan:
            summary["payment_plan"] = {
                "total_amount": active_plan.total_amount,
                "installment_amount": active_plan.installment_amount,
                "next_due_date": active_plan.next_due_date,
                "default_count": active_plan.default_count,
            }

        return summary


# Dashboard / Report / M-Pesa stubs (kept simple)

class FinanceTodayStatsSerializer(serializers.Serializer):
    date = serializers.DateField()
    total_collected = serializers.DecimalField(max_digits=12, decimal_places=2)
    payments_count = serializers.IntegerField()
    invoices_issued = serializers.IntegerField()
    invoices_amount = serializers.DecimalField(max_digits=12, decimal_places=2)


class MonthlySummarySerializer(serializers.Serializer):
    month = serializers.CharField()
    total_revenue = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_invoiced = serializers.DecimalField(max_digits=12, decimal_places=2)
    outstanding_balance = serializers.DecimalField(max_digits=12, decimal_places=2)
    payment_methods = serializers.ListField(child=serializers.DictField())


class FinanceDashboardSerializer(serializers.Serializer):
    today_stats = FinanceTodayStatsSerializer()
    monthly_summary = MonthlySummarySerializer()
    recent_payments = serializers.ListField(child=serializers.DictField())
    overdue_invoices = serializers.ListField(child=serializers.DictField())
    pending_bursaries = serializers.ListField(child=serializers.DictField())


class FinanceReportSerializer(serializers.Serializer):
    type = serializers.ChoiceField(
        choices=[
            ("revenue", "Revenue Report"),
            ("invoices", "Invoice Report"),
            ("payments", "Payment Report"),
            ("students", "Student Finance Report"),
        ]
    )
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    format = serializers.ChoiceField(
        choices=[("json", "JSON"), ("pdf", "PDF"), ("excel", "Excel")], default="json"
    )

    def validate(self, data):
        if data["start_date"] > data["end_date"]:
            raise serializers.ValidationError("Start date cannot be after end date")
        return data


class MpesaCallbackSerializer(serializers.Serializer):
    """Raw Safaricom STK / C2B callback payload (flexible)."""

    Body = serializers.DictField(required=False)
    # Also accept flat style for convenience
    MpesaReceiptNumber = serializers.CharField(required=False)
    PhoneNumber = serializers.CharField(required=False)
    Amount = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)
    TransactionDate = serializers.CharField(required=False)
    ResultCode = serializers.IntegerField(required=False)
    ResultDesc = serializers.CharField(required=False)
    CheckoutRequestID = serializers.CharField(required=False)
    MerchantRequestID = serializers.CharField(required=False)




class StkPushSerializer(serializers.Serializer):
    """Initiate Lipa Na M-Pesa STK Push against an invoice."""

    phone = serializers.CharField(max_length=15,help_text="Phone number that will receive the STK prompt (07... or 2547...)")
    amount = serializers.DecimalField( max_digits=12, decimal_places=2,min_value=Decimal("1"),required=False,
        help_text="Amount to charge. Defaults to the invoice outstanding balance." )

    def validate_phone(self, value):
        # Basic sanity – full normalization happens in the service
        cleaned = value.replace(" ", "").replace("-", "").replace("+", "")
        if not cleaned.isdigit() or len(cleaned) < 9:
            raise serializers.ValidationError("Enter a valid Kenyan phone number.")
        return value