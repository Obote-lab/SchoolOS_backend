import logging
from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from core.audit import create_audit_log
from core.choices.identity import AuditActionChoices
from core.choices.finance import (
    BursaryStatusChoices,
    FinanceCategoryChoices,
    FinanceTransactionStatusChoices,
    InvoiceStatusChoices,
    PaymentStatusChoices,
    TransactionTypeChoices,
)

from .models import Bursary, FeeInvoice, FinancialTransaction, Payment

logger = logging.getLogger(__name__)


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


@receiver(post_save, sender=Payment)
def update_invoice_and_ledger_on_payment(sender, instance: Payment, created: bool, **kwargs):
    """
    Post to invoice + GL only when payment is COMPLETED and not yet ledger_posted.
    Works for create-as-COMPLETED and later transition to COMPLETED (if you save again).
    """
    if instance.payment_status != PaymentStatusChoices.COMPLETED:
        return

    # Idempotency (requires Payment.ledger_posted field)
    if getattr(instance, "ledger_posted", False):
        return

    try:
        with transaction.atomic():
            # Re-fetch under lock
            payment = (Payment.objects.select_for_update().filter(pk=instance.pk).first())
            if not payment or payment.ledger_posted:
                return
            if payment.payment_status != PaymentStatusChoices.COMPLETED:
                return

            invoice = (
                FeeInvoice.objects.select_for_update()
                .filter(pk=payment.invoice_id)
                .first()
            )
            if not invoice:
                logger.error("Payment %s has no invoice", payment.pk)
                return

            old_balance = invoice.balance
            invoice.amount_paid = (invoice.amount_paid or 0) + payment.amount
            invoice.save()  # recalculates balance/status (DRAFT left alone if still draft)

            FinancialTransaction.objects.create(
                school=payment.school,
                transaction_type=TransactionTypeChoices.INCOME,
                finance_category=FinanceCategoryChoices.FEES,
                amount=payment.amount,
                description=(
                    f"Payment {payment.payment_reference} "
                    f"for invoice {invoice.invoice_number}"
                ),
                reference_number=payment.payment_reference,
                account_debit="1100",
                account_credit="4100",
                approved_by=payment.verified_by or payment.received_by,
                transaction_status=FinanceTransactionStatusChoices.POSTED,
            )

            Payment.objects.filter(pk=payment.pk).update(ledger_posted=True)

            create_audit_log(
                actor=payment.received_by,
                action=AuditActionChoices.CREATE,
                model_name="Payment",
                record_id=payment.id,
                school=payment.school,
                reason=(
                    f"Payment of {payment.amount} received – "
                    f"invoice balance {old_balance} → {invoice.balance}"
                ),
                new_value=payment.payment_reference,
            )
    except Exception:
        logger.exception("Failed payment→invoice/ledger update for %s", instance.pk)


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
    Apply bursary to open invoice only on transition → APPROVED,
    and only once (applied_to_invoice is null).
    """
    if instance.bursary_status != BursaryStatusChoices.APPROVED:
        return

    prev = getattr(instance, "_previous_bursary_status", None)
    # Allow first save already APPROVED (created as approved)
    if prev is not None and prev == BursaryStatusChoices.APPROVED:
        return

    if not instance.amount_awarded or instance.amount_awarded <= 0:
        return

    # Idempotency (requires Bursary.applied_to_invoice field)
    if getattr(instance, "applied_to_invoice_id", None):
        return

    try:
        with transaction.atomic():
            bursary = Bursary.objects.select_for_update().filter(pk=instance.pk).first()
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

            invoice.bursary_amount = (invoice.bursary_amount or 0) + bursary.amount_awarded
            invoice.save()

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