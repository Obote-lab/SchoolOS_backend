from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
from django.db import transaction
from .models import FeeInvoice, Payment, PaymentPlan, Bursary
import logging
from django.db import models

logger = logging.getLogger(__name__)


@receiver(post_save, sender=FeeInvoice)
def create_financial_transaction(sender, instance, created, **kwargs):
    """Create financial transaction when invoice is issued"""
    try:
        if instance.invoice_status == FeeInvoice.FeeInvoiceStatusChoices.ISSUED:  
            from .models import FinancialTransaction
            
            FinancialTransaction.objects.create(
                school=instance.school, 
                transaction_type='income',
                finance_category='fees',
                amount=instance.total_amount,
                description=f"Fee invoice: {instance.invoice_number}",
                reference_number=instance.invoice_number,
                account_debit='1100',  # Cash/Bank account
                account_credit='4100',  # Fee income account
                transaction_status='posted',
                date=instance.issue_date,
            )
            logger.info(f"Created transaction for invoice {instance.invoice_number}")
            
    except Exception as e:
        logger.error(f"Error creating financial transaction: {e}")


#  PAYMENT SIGNALS 
@receiver(pre_save, sender=Payment)
def validate_payment_status(sender, instance, **kwargs):
    """Validate payment before saving"""
    try:
        if instance.payment_status == 'completed' and not instance.verified_by:
            # Auto-verify if not already verified
            instance.verified_by = instance.received_by
            
        if instance.payment_status == 'completed' and not instance.receipt_issued:
            # Auto-generate receipt number
            if not instance.receipt_number:
                from datetime import datetime
                year = datetime.now().year
                last_payment = Payment.objects.filter(
                    receipt_number__startswith=f"RCPT/{year}/"
                ).order_by('receipt_number').last()
                
                if last_payment:
                    last_number = int(last_payment.receipt_number.split('/')[-1])
                    new_number = last_number + 1
                else:
                    new_number = 1
                
                instance.receipt_number = f"RCPT/{year}/{new_number:03d}"
                instance.receipt_issued = True
                
    except Exception as e:
        logger.error(f"Error validating payment: {e}")


@receiver(post_save, sender=Payment)
@transaction.atomic
def update_invoice_on_payment(sender, instance, created, **kwargs):
    """Update invoice when payment is made"""
    try:
        if instance.payment_status == 'completed' and instance.amount > 0:
            invoice = instance.invoice
            
            # Update invoice amounts
            invoice.amount_paid += instance.amount
            invoice.save()  # This will trigger invoice totals calculation
            
            # Create financial transaction
            from .models import FinancialTransaction
            
            FinancialTransaction.objects.create(
                transaction_type='income',
                finance_category='fees',
                amount=instance.amount,
                description=f"Payment received: {instance.payment_reference} for {invoice.invoice_number}",
                reference_number=instance.payment_reference,
                account_debit='1100',  # Cash/Bank account
                account_credit='1101',  # Accounts Receivable
                transaction_status='posted',
                date=instance.paid_at.date(),
            )
            
            logger.info(f"Updated invoice {invoice.invoice_number} with payment {instance.amount}")
            
            # Update payment plan if exists
            if invoice.payment_plan:
                plan = invoice.payment_plan
                plan.last_payment_date = instance.paid_at.date()
                
                # Calculate next due date
                if plan.frequency == 'weekly':
                    plan.next_due_date = plan.last_payment_date + timezone.timedelta(days=7)
                elif plan.frequency == 'biweekly':
                    plan.next_due_date = plan.last_payment_date + timezone.timedelta(days=14)
                elif plan.frequency == 'monthly':
                    from dateutil.relativedelta import relativedelta
                    plan.next_due_date = plan.last_payment_date + relativedelta(months=1)
                
                # Check if plan is completed
                total_paid = Payment.objects.filter(
                        invoice__payment_plan=plan,
                        payment_status='completed'
                ).aggregate(models.Sum('amount'))['amount__sum'] or 0
                
                if total_paid >= plan.total_amount:
                    # plan.payment_status = 'completed'
                    plan.payment_plan_status = PaymentPlan.PaymentPlanStatusChoices.COMPLETED

                
                plan.save()
                
    except Exception as e:
        logger.error(f"Error updating invoice on payment: {e}")


@receiver(post_delete, sender=Payment)
def revert_invoice_on_payment_delete(sender, instance, **kwargs):
    """Revert invoice amounts when payment is deleted"""
    try:
        if instance.invoice and instance.amount > 0:
            invoice = instance.invoice
            invoice.amount_paid -= instance.amount
            invoice.save()
            logger.info(f"Reverted invoice {invoice.invoice_number} after payment deletion")
    except Exception as e:
        logger.error(f"Error reverting invoice: {e}")


#  PAYMENT PLAN SIGNALS 
@receiver(pre_save, sender=PaymentPlan)
def calculate_installment_amount(sender, instance, **kwargs):
    """Calculate installment amount if not provided"""
    try:
        if instance.total_amount > 0 and instance.installment_count > 0:
            if not instance.installment_amount or instance.installment_amount <= 0:
                instance.installment_amount = instance.total_amount / instance.installment_count
                
        if not instance.next_due_date:
            instance.next_due_date = instance.start_date
            
    except Exception as e:
        logger.error(f"Error calculating installment amount: {e}")


@receiver(post_save, sender=PaymentPlan)
def check_payment_plan_defaults(sender, instance, **kwargs):
    """Check for payment plan defaults"""
    try:
        if instance.next_due_date and instance.next_due_date < timezone.now().date():
            # Check if payment is overdue
            last_payment = Payment.objects.filter(
                    invoice__payment_plan=instance,
                    payment_status='completed'
            ).order_by('-paid_at').first()
            
            if not last_payment or last_payment.paid_at.date() < instance.next_due_date:
                instance.default_count += 1
                
                if instance.default_count >= 3:
                    instance.payment_plan_status = 'defaulted'
                    
                instance.save()
                logger.warning(f"Payment plan {instance.id} has defaulted {instance.default_count} times")
                
    except Exception as e:
        logger.error(f"Error checking payment plan defaults: {e}")


#  BURSARY SIGNALS 
@receiver(post_save, sender=Bursary)
def apply_bursary_to_invoice(sender, instance, **kwargs):
    """Apply bursary to student's invoice"""
    try:
        if instance.bursary_status == 'approved'and instance.amount_awarded > 0:
            # Find student's invoice for the term
            invoice = FeeInvoice.objects.filter(
                student=instance.student,
                term=instance.term,
                academic_year=instance.academic_year
            ).first()
            
            if invoice:
                invoice.scholarship_amount += instance.amount_awarded
                invoice.save()
                
                # Create financial transaction
                from .models import FinancialTransaction
                
                FinancialTransaction.objects.create(
                    transaction_type='expense',
                    finance_category='fees',
                    amount=instance.amount_awarded,
                    description=f"Bursary awarded: {instance.get_type_display()} - {instance.reason}",
                    reference_number=f"BUR-{instance.id}",
                    account_debit='5100',  # Scholarship expense
                    account_credit='1101',  # Accounts Receivable
                    transaction_status='posted',
                    date=instance.approval_date or timezone.now().date(),
                )
                
                logger.info(f"Applied bursary {instance.amount_awarded} to invoice {invoice.invoice_number}")
                
    except Exception as e:
        logger.error(f"Error applying bursary to invoice: {e}")


@receiver(post_save, sender=Bursary)
def check_bursary_renewal(sender, instance, **kwargs):
    """Check if bursary needs renewal"""
    try:
        if instance.renewable and instance.next_review_date:
            if instance.next_review_date <= timezone.now().date():
                # Create renewal notification
                logger.info(f"Bursary {instance.id} needs renewal review")
                
                # In a real app, you would send notification here
                
    except Exception as e:
        logger.error(f"Error checking bursary renewal: {e}")


#  STUDENT SIGNALS 
@receiver(post_save, sender='students.Student')
def create_initial_invoice(sender, instance, created, **kwargs):
    """Create initial fee invoice for new student"""
    try:
        if created:
            from schools.models import AcademicYear, Term
            
            current_year = AcademicYear.objects.filter(is_current=True).first()
            current_term = Term.objects.filter(is_current=True).first()
            
            if current_year and current_term:
                # Get fee structure for student's class
                from .models import FeeStructure
                
                fee_structure = FeeStructure.objects.filter(
                    school=instance.school,
                    class_level=instance.current_class.level if instance.current_class else 'General',
                    term=current_term,
                    academic_year=current_year,
                    fees_status='active'
                ).first()
                
                if fee_structure:
                    # Calculate total amount
                    total_amount = FeeStructure.objects.filter(
                        school=instance.school,
                        class_level=instance.current_class.level if instance.current_class else 'General',
                        term=current_term,
                        academic_year=current_year,
                        fees_status='active',
                        is_compulsory=True
                    ).aggregate(models.Sum('amount'))['amount__sum'] or 0
                    
                    # Create invoice
                    FeeInvoice.objects.create(
                        student=instance,
                        term=current_term,
                        academic_year=current_year,
                        total_amount=total_amount,
                        due_date=current_term.fee_due_date if hasattr(current_term, 'fee_due_date') else current_term.end_date,
                        created_by=instance.user if instance.user else None,
                    )
                    
                    logger.info(f"Created initial invoice for student {instance.admission_number}")
                    
    except Exception as e:
        logger.error(f"Error creating initial invoice: {e}")


@receiver(post_save, sender=Payment)
def send_payment_confirmation(sender, instance, created, **kwargs):
    """Send payment confirmation to parent"""
    if instance.payment_status == 'completed' and created:
        try:
            parent_phone = instance.student.parent_phone
            # Send SMS
            # send_sms(parent_phone, f"Payment of KES {instance.amount} received for {instance.student.admission_number}")
            logger.info(f"SMS sent for payment {instance.payment_reference}")
        except Exception as e:
            logger.error(f"Error sending payment confirmation: {e}")