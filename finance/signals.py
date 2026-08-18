import logging
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from accounts.models import AuditLog
from core.choices.finance import (
    BursaryStatusChoices,
    FinanceCategoryChoices,
    FinanceTransactionStatusChoices,
    InvoiceStatusChoices,
    PaymentStatusChoices,
    TransactionTypeChoices,
)

# If you have this in core:
try:
    from core.choices import AuditActionChoices
except ImportError:
    AuditActionChoices = None

from .models import Bursary, FeeInvoice, FinancialTransaction, Payment

logger = logging.getLogger(__name__)


def _audit(
    *,
    user,
    action_type,
    model_name: str,
    record_id,
    reason: str,
    school=None,
    new_value: str = "",
):
    payload = {
        "user": user,
        "action_type": action_type,
        "model_name": model_name,
        "record_id": record_id,
        "reason": reason,
        "school": school,
        "new_value": new_value,
    }
    # Drop keys your AuditLog may not have
    try:
        AuditLog.objects.create(**{k: v for k, v in payload.items() if v is not None})
    except Exception as e:
        logger.warning("AuditLog failed: %s", e)


@receiver(post_save, sender=FeeInvoice)
def log_invoice_creation(sender, instance: FeeInvoice, created: bool, **kwargs):
    if not created:
        return
    action = getattr(AuditActionChoices, "CREATE", "CREATE")
    _audit(
        user=instance.created_by,
        action_type=action,
        model_name="FeeInvoice",
        record_id=instance.id,
        reason=f"Fee invoice {instance.invoice_number} created for {instance.student.admission_number}",
        school=instance.school,
        new_value=instance.invoice_number,
    )


@receiver(post_save, sender=Payment)
def update_invoice_and_ledger_on_payment(
    sender, instance: Payment, created: bool, **kwargs
):
    if not created or instance.payment_status != PaymentStatusChoices.COMPLETED:
        return

    try:
        with transaction.atomic():
            invoice = (
                FeeInvoice.objects.select_for_update()
                .filter(pk=instance.invoice_id)
                .first()
            )
            if not invoice:
                return

            old_balance = invoice.balance
            invoice.amount_paid = (invoice.amount_paid or 0) + instance.amount
            # Model.save() recalculates net_payable, balance, invoice_status
            invoice.save()

            FinancialTransaction.objects.create(
                school=instance.school,
                transaction_type=TransactionTypeChoices.INCOME,
                finance_category=FinanceCategoryChoices.FEES,
                amount=instance.amount,
                description=(
                    f"Payment {instance.payment_reference} "
                    f"for invoice {invoice.invoice_number}"
                ),
                reference_number=instance.payment_reference,
                account_debit="1100",  # Cash/Bank
                account_credit="4100",  # Fee Income
                approved_by=instance.verified_by or instance.received_by,
                transaction_status=FinanceTransactionStatusChoices.POSTED,
            )

            action = getattr(AuditActionChoices, "CREATE", "CREATE")
            _audit(
                user=instance.received_by,
                action_type=action,
                model_name="Payment",
                record_id=instance.id,
                reason=(
                    f"Payment of {instance.amount} received – "
                    f"invoice balance {old_balance} → {invoice.balance}"
                ),
                school=instance.school,
                new_value=instance.payment_reference,
            )
    except Exception as e:
        logger.exception("Failed payment→invoice/ledger update: %s", e)


@receiver(post_save, sender=Bursary)
def apply_bursary_on_approval(sender, instance: Bursary, **kwargs):
    if instance.bursary_status != BursaryStatusChoices.APPROVED:
        return
    if not instance.amount_awarded or instance.amount_awarded <= 0:
        return

    try:
        with transaction.atomic():
            invoice = (
                FeeInvoice.objects.select_for_update()
                .filter(
                    student=instance.student,
                    term=instance.term,
                    academic_year=instance.academic_year,
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
                    instance.id,
                    instance.student_id,
                )
                return

            invoice.bursary_amount = (
                (invoice.bursary_amount or 0) + instance.amount_awarded
            )
            invoice.save()  # recalculates net_payable / balance / status

            FinancialTransaction.objects.create(
                school=instance.school,
                transaction_type=TransactionTypeChoices.EXPENSE,
                finance_category=FinanceCategoryChoices.OTHER,  # or add BURSARY to choices
                amount=instance.amount_awarded,
                description=(
                    f"Bursary {instance.get_source_display()} for "
                    f"{instance.student.admission_number}"
                ),
                reference_number=f"BUR-{instance.id}",
                account_debit="5100",
                account_credit="1101",
                approved_by=instance.approved_by,
                transaction_status=FinanceTransactionStatusChoices.POSTED,
            )
    except Exception as e:
        logger.exception("Failed bursary application: %s", e)