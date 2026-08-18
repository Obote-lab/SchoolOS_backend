from decimal import Decimal
from django.contrib import admin
from django.utils.html import format_html
from .models import (
    Bursary, FeeInvoice,
    FeeStructure,FinancialTransaction,
    Payment,PaymentPlan,
)

@admin.register(FeeStructure)
class FeeStructureAdmin(admin.ModelAdmin):
    list_display = (
        "class_level",
        "fees_category",
        "amount",
        "due_date",
        "fees_status",
        "school",
        "is_compulsory",
    )
    list_filter = ("fees_category", "fees_status", "is_compulsory", "school", "term")
    search_fields = ("description", "class_level", "school__school_name")
    readonly_fields = ("created_at", "updated_at")

    fieldsets = (
        (
            "Fee Details",
            {
                "fields": (
                    "school",
                    "class_level",
                    "term",
                    "academic_year",
                    "fees_category",
                    "description",
                    "amount",
                )
            },
        ),
        (
            "Payment Terms",
            {
                "fields": (
                    "due_date",
                    "late_fee_per_day",
                    "is_compulsory",
                    "is_refundable",
                )
            },
        ),
        ("Accounting", {"fields": ("gl_account", "taxable", "tax_rate")}),
        (
            "Approval",
            {
                "fields": (
                    "fees_status",
                    "created_by",
                    "approved_by",
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )


@admin.register(FeeInvoice)
class FeeInvoiceAdmin(admin.ModelAdmin):
    list_display = (
        "invoice_number",
        "student",
        "total_amount",
        "amount_paid",
        "balance_display",
        "due_date",
        "invoice_status",
    )
    list_filter = ("invoice_status", "school", "term", "academic_year")
    search_fields = (
        "invoice_number",
        "student__admission_number",
        "student__user__first_name",
    )
    readonly_fields = ("created_at", "updated_at", "net_payable")

    def balance_display(self, obj):
        if obj.balance <= 0:
            color = "green"
        elif obj.balance > obj.total_amount * Decimal("0.5"):
            color = "red"
        else:
            color = "orange"
        return format_html('<span style="color: {};">KES {}</span>', color, obj.balance)

    balance_display.short_description = "Balance"


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "payment_reference",
        "student",
        "amount",
        "method",
        "paid_at",
        "payment_status",
        "received_by",
    )
    list_filter = ("payment_status", "method", "school", "paid_at")
    search_fields = ("payment_reference", "student__admission_number", "mpesa_receipt")
    readonly_fields = ("created_at", "updated_at")

    fieldsets = (
        (
            "Payment Info",
            {"fields": ("payment_reference", "invoice", "student", "amount", "method")},
        ),
        (
            "Transaction Details",
            {
                "fields": (
                    "mpesa_receipt",
                    "bank_ref",
                    "cheque_no",
                    "paid_at",
                    "received_by",
                    "verified_by",
                )
            },
        ),
        ("Status", {"fields": ("payment_status", "reversal_reason")}),
    )


@admin.register(PaymentPlan)
class PaymentPlanAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "term",
        "total_amount",
        "installment_amount",
        "start_date",
        "next_due_date",
        "plan_status",
    )
    list_filter = ("plan_status", "frequency", "school")
    search_fields = ("student__admission_number", "student__user__first_name")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Bursary)
class BursaryAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "source",
        "amount_awarded",
        "term",
        "bursary_status",
        "application_date",
    )
    list_filter = ("bursary_status", "source", "school", "renewable")
    search_fields = ("student__admission_number", "reason")
    readonly_fields = ("created_at", "updated_at")


@admin.register(FinancialTransaction)
class FinancialTransactionAdmin(admin.ModelAdmin):
    list_display = (
        "transaction_type",
        "finance_category",
        "amount",
        "date",
        "description",
        "transaction_status",
        "school",
    )
    list_filter = (
        "transaction_type",
        "finance_category",
        "transaction_status",
        "school",
    )
    search_fields = ("description", "reference_number")
    readonly_fields = ("created_at", "updated_at")
