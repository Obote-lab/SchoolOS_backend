import logging
from decimal import Decimal

from django.db import transaction
from django.db.models import F, Sum
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from core.audit import create_audit_log
from core.choices.finance import (
    BursaryStatusChoices,
    FinanceCategoryChoices,
    FinanceTransactionStatusChoices,
    InvoiceStatusChoices,
    PaymentStatusChoices,
    TransactionTypeChoices,
)
from core.choices.identity import AuditActionChoices

from .models import (
    Bursary,
    FeeInvoice,
    FinancialTransaction,
    InvoiceItem,
    Payment,
    PaymentAllocation,
)

logger = logging.getLogger(__name__)


# Helpers

def _recalculate_invoice_from_allocations(invoice: FeeInvoice) -> None:
    """
    Recompute amount_paid from PaymentAllocation records that belong to
    COMPLETED payments, then let the invoice recalculate balance/status.
    """
    total_allocated = (
        PaymentAllocation.objects.filter(
            invoice=invoice,
            payment__payment_status=PaymentStatusChoices.COMPLETED,
        ).aggregate(total=Sum("amount"))["total"]
        or Decimal("0")
    )
    invoice.amount_paid = total_allocated
    invoice.recalculate_totals(save=True)


# FeeInvoice
@receiver(post_save, sender=FeeInvoice)
def log_invoice_creation(sender, instance: FeeInvoice, created: bool, **kwargs):
    if not created:
        return
    create_audit_log(
        actor=instance.created_by,
        action=AuditActionChoices.CREATE,
        model_name="FeeInvoice",
        record_id=instance.id,
        school=instance.school,
        reason=(
            f"Fee invoice {instance.invoice_number} created for "
            f"{instance.student.admission_number}"
        ),
        new_value=instance.invoice_number,
    )


# InvoiceItem → keep invoice totals in sync
@receiver(post_save, sender=InvoiceItem)
@receiver(post_delete, sender=InvoiceItem)
def sync_invoice_totals_on_item_change(sender, instance: InvoiceItem, **kwargs):
    """Whenever a line item is added/changed/deleted, recalculate the parent invoice."""
    invoice = instance.invoice
    if invoice:
        invoice.recalculate_totals(save=True)


# PaymentAllocation → keep invoice amount_paid in sync

@receiver(post_save, sender=PaymentAllocation)
@receiver(post_delete, sender=PaymentAllocation)
def sync_invoice_on_allocation_change(sender, instance: PaymentAllocation, **kwargs):
    """Recalculate the target invoice whenever an allocation is created or removed."""
    if instance.invoice_id:
        try:
            invoice = FeeInvoice.objects.get(pk=instance.invoice_id)
            _recalculate_invoice_from_allocations(invoice)
        except FeeInvoice.DoesNotExist:
            pass


# Payment → ledger + invoice update (idempotent)

@receiver(post_save, sender=Payment)
def update_invoice_and_ledger_on_payment(sender, instance: Payment, created: bool, **kwargs):
    """
    When a payment becomes COMPLETED:

    1. If it has allocations → rely on PaymentAllocation signals to update invoices.
    2. If it has a direct invoice link and no allocations yet → create a default
       allocation (backward-compatible behaviour).
    3. Post to the General Ledger once (ledger_posted flag).
    4. Write an audit log.
    """
    if instance.payment_status != PaymentStatusChoices.COMPLETED:
        return

    # Already processed
    if getattr(instance, "ledger_posted", False):
        return

    try:
        with transaction.atomic():
            payment = (
                Payment.objects.select_for_update()
                .filter(pk=instance.pk)
                .first()
            )
            if not payment or payment.ledger_posted:
                return
            if payment.payment_status != PaymentStatusChoices.COMPLETED:
                return

            # 1. Ensure at least one allocation exists (legacy path)
            has_allocations = payment.allocations.exists()

            if not has_allocations and payment.invoice_id:
                # Auto-create a full allocation to the linked invoice
                PaymentAllocation.objects.create(
                    payment=payment,
                    invoice_id=payment.invoice_id,
                    amount=payment.amount,
                    notes="Auto-allocated on completion",
                )
                # The PaymentAllocation post_save will update the invoice

            # 2. Post to General Ledger (once)
            FinancialTransaction.objects.create(
                school=payment.school,
                transaction_type=TransactionTypeChoices.INCOME,
                finance_category=FinanceCategoryChoices.FEES,
                amount=payment.amount,
                description=(
                    f"Payment {payment.payment_reference}"
                    + (
                        f" for invoice {payment.invoice.invoice_number}"
                        if payment.invoice_id
                        else ""
                    )
                ),
                reference_number=payment.payment_reference,
                account_debit="1100",   # Cash / Bank / M-Pesa
                account_credit="4100",  # Fee Income
                approved_by=payment.verified_by or payment.received_by,
                transaction_status=FinanceTransactionStatusChoices.POSTED,
            )

            Payment.objects.filter(pk=payment.pk).update(ledger_posted=True)

            # 3. Audit
            create_audit_log(
                actor=payment.received_by,
                action=AuditActionChoices.CREATE if created else AuditActionChoices.UPDATE,
                model_name="Payment",
                record_id=payment.id,
                school=payment.school,
                reason=(
                    f"Payment of KES {payment.amount} marked COMPLETED "
                    f"({payment.get_method_display()})"
                    + (
                        f" – M-Pesa receipt {payment.mpesa_receipt}"
                        if payment.mpesa_receipt
                        else ""
                    )
                ),
                new_value=payment.payment_reference,
            )

    except Exception:
        logger.exception(
            "Failed payment→invoice/ledger update for Payment %s", instance.pk
        )


# Bursary → apply to open invoice on approval
@receiver(pre_save, sender=Bursary)
def bursary_store_previous_status(sender, instance: Bursary, **kwargs):
    if not instance.pk:
        instance._previous_bursary_status = None
        return
    try:
        old = Bursary.objects.only("bursary_status").get(pk=instance.pk)
        instance._previous_bursary_status = old.bursary_status
    except Bursary.DoesNotExist:
        instance._previous_bursary_status = None


@receiver(post_save, sender=Bursary)
def apply_bursary_on_approval(sender, instance: Bursary, **kwargs):
    """
    Apply bursary amount to an open invoice only on transition → APPROVED,
    and only once (applied_to_invoice is still null).
    """
    if instance.bursary_status != BursaryStatusChoices.APPROVED:
        return

    prev = getattr(instance, "_previous_bursary_status", None)
    # Skip if it was already APPROVED
    if prev is not None and prev == BursaryStatusChoices.APPROVED:
        return

    if not instance.amount_awarded or instance.amount_awarded <= 0:
        return

    if getattr(instance, "applied_to_invoice_id", None):
        return

    try:
        with transaction.atomic():
            bursary = (
                Bursary.objects.select_for_update()
                .filter(pk=instance.pk)
                .first()
            )
            if not bursary or bursary.applied_to_invoice_id:
                return

            invoice = (
                FeeInvoice.objects.select_for_update()
                .filter(
                    student=bursary.student,
                    term=bursary.term,
                    academic_year=bursary.academic_year,
                    invoice_status__in=[
                        InvoiceStatusChoices.ISSUED,
                        InvoiceStatusChoices.PARTIALLY_PAID,
                        InvoiceStatusChoices.OVERDUE,
                    ],
                )
                .first()
            )
            if not invoice:
                logger.info(
                    "No open invoice for bursary %s (student %s)",
                    bursary.id,
                    bursary.student_id,
                )
                return

            invoice.bursary_amount = (
                (invoice.bursary_amount or Decimal("0")) + bursary.amount_awarded
            )
            invoice.recalculate_totals(save=True)

            FinancialTransaction.objects.create(
                school=bursary.school,
                transaction_type=TransactionTypeChoices.EXPENSE,
                finance_category=FinanceCategoryChoices.OTHER,
                amount=bursary.amount_awarded,
                description=(
                    f"Bursary {bursary.get_source_display()} for "
                    f"{bursary.student.admission_number}"
                ),
                reference_number=f"BUR-{bursary.id}",
                account_debit="5100",
                account_credit="1101",
                approved_by=bursary.approved_by,
                transaction_status=FinanceTransactionStatusChoices.POSTED,
            )

            Bursary.objects.filter(pk=bursary.pk).update(applied_to_invoice=invoice)

            create_audit_log(
                actor=bursary.approved_by,
                action=AuditActionChoices.UPDATE,
                model_name="Bursary",
                record_id=bursary.id,
                school=bursary.school,
                reason=f"Bursary applied to invoice {invoice.invoice_number}",
                new_value=str(bursary.amount_awarded),
            )
    except Exception:
        logger.exception("Failed bursary application for %s", instance.pk)