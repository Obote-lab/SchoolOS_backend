from rest_framework import serializers
from django.utils import timezone
from django.db import transaction
from django.db import models
from ..models import FeeStructure, PaymentPlan, FeeInvoice, Payment, FinancialTransaction, Bursary


#  LIST SERIALIZERS 
class FeeStructureListSerializer(serializers.ModelSerializer):
    """Simple fee structure list"""
    category_display = serializers.CharField(source='get_fees_category_display')
    status_display = serializers.CharField(source='get_fees_status_display')
    approved_by_name = serializers.CharField(source='approved_by.get_full_name', read_only=True, allow_null=True)
    
    class Meta:
        model = FeeStructure
        fields = [
            'id', 'class_level', 'fees_category', 'category_display', 'description', 
            'amount', 'due_date', 'fees_status', 'status_display', 'approved_by', 'approved_by_name'
        ]


class FeeInvoiceListSerializer(serializers.ModelSerializer):
    """Simple invoice list"""
    student_name = serializers.CharField(source='student.user.get_full_name', read_only=True)
    student_admission = serializers.CharField(source='student.admission_number', read_only=True)
    status_display = serializers.CharField(source='get_invoice_status_display')

    
    class Meta:
        model = FeeInvoice
        fields = [
            'id', 'invoice_number', 'student', 'student_name', 'student_admission',
            'total_amount', 'amount_paid', 'balance', 'due_date', 'invoice_status', 'status_display'
        ]


class PaymentListSerializer(serializers.ModelSerializer):
    """Simple payment list"""
    student_name = serializers.CharField(source='student.user.get_full_name', read_only=True)
    method_display = serializers.CharField(source='get_method_display', read_only=True)
    status_display = serializers.CharField(source='get_payment_status_display', read_only=True)
    
    class Meta:
        model = Payment
        fields = [
            'id', 'payment_reference', 'student', 'student_name', 'amount',
            'method', 'method_display', 'payment_status', 'status_display', 'paid_at'
        ]


#  DETAIL SERIALIZERS 
class FeeStructureDetailSerializer(serializers.ModelSerializer):
    """Full fee structure details"""
    category_display = serializers.CharField(source='get_fees_category_display', read_only=True)
    # status_display = serializers.CharField(source='get_payment_status_display', read_only=True)
    status_display = serializers.CharField(source='get_fees_status_display', read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.get_full_name', read_only=True, allow_null=True)
    school_name = serializers.CharField(source='school.name', read_only=True)
    term_name = serializers.CharField(source='term.name', read_only=True)
    academic_year_name = serializers.CharField(source='academic_year.year', read_only=True)
    
    class Meta:
        model = FeeStructure
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_amount(self, value):
        if value < 0:
            raise serializers.ValidationError("Amount cannot be negative")
        return value
    
    def validate(self, data):
        if data.get('expiry_date') and data.get('effective_date'):
            if data['expiry_date'] < data['effective_date']:
                raise serializers.ValidationError({
                    'expiry_date': 'Expiry date cannot be before effective date'
                })
        return data


class FeeInvoiceDetailSerializer(serializers.ModelSerializer):
    """Full invoice details"""
    student_name = serializers.CharField(source='student.user.get_full_name', read_only=True)
    student_admission = serializers.CharField(source='student.admission_number', read_only=True)
    # status_display = serializers.CharField(source='get_payment_status_display', read_only=True)
    status_display = serializers.CharField(source='get_invoice_status_display', read_only=True)
    term_name = serializers.CharField(source='term.name', read_only=True)
    academic_year_name = serializers.CharField(source='academic_year.year', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True, allow_null=True)
    payments = PaymentListSerializer(source='payments', many=True, read_only=True)

    
    class Meta:
        model = FeeInvoice
        fields = '__all__'
        read_only_fields = ['id', 'invoice_number', 'created_at', 'updated_at', 'payments']
    
    def validate_due_date(self, value):
        if value < timezone.now().date():
            raise serializers.ValidationError("Due date cannot be in the past")
        return value
    
    def validate_total_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Total amount must be greater than zero")
        return value


class PaymentDetailSerializer(serializers.ModelSerializer):
    """Full payment details"""
    student_name = serializers.CharField(source='student.user.get_full_name', read_only=True)
    student_admission = serializers.CharField(source='student.admission_number', read_only=True)
    method_display = serializers.CharField(source='get_method_display', read_only=True)
    channel_display = serializers.CharField(source='get_channel_display', read_only=True)
    status_display = serializers.CharField(source='get_payment_status_display', read_only=True)
    received_by_name = serializers.CharField(source='received_by.get_full_name', read_only=True, allow_null=True)
    verified_by_name = serializers.CharField(source='verified_by.get_full_name', read_only=True, allow_null=True)
    
    invoice_number = serializers.CharField(source='invoice.invoice_number', read_only=True)
    
    class Meta:
        model = Payment
        fields = '__all__'
        read_only_fields = ['id', 'payment_reference', 'created_at', 'updated_at']
    
    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Payment amount must be greater than zero")
        return value


class PaymentPlanDetailSerializer(serializers.ModelSerializer):
    """Full payment plan details"""
    student_name = serializers.CharField(source='student.user.get_full_name', read_only=True)
    student_admission = serializers.CharField(source='student.admission_number', read_only=True)
    frequency_display = serializers.CharField(source='get_frequency_display', read_only=True)
    status_display = serializers.CharField(source='get_payment_status_display', read_only=True)
    signed_by_name = serializers.CharField(source='signed_by.get_full_name', read_only=True, allow_null=True)
    
    class Meta:
        model = PaymentPlan
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


class BursaryDetailSerializer(serializers.ModelSerializer):
    """Full bursary details"""
    student_name = serializers.CharField(source='student.user.get_full_name', read_only=True)
    student_admission = serializers.CharField(source='student.admission_number', read_only=True)
    type_display = serializers.CharField(source='get_type_display', read_only=True)
    # status_display = serializers.CharField(source='get_payment_status_display', read_only=True)
    status_display = serializers.CharField(source='get_bursary_status_display', read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.get_full_name', read_only=True, allow_null=True)
    
    class Meta:
        model = Bursary
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


#  CREATE/UPDATE SERIALIZERS 
class FeeStructureCreateSerializer(serializers.ModelSerializer):
    """Create fee structure"""
    class Meta:
        model = FeeStructure
        fields = [
            'school', 'class_level', 'term', 'academic_year', 'fees_category',
            'description', 'amount', 'due_date', 'late_fee_per_day',
            'is_compulsory', 'is_refundable', 'account_code', 'gl_account',
            'taxable', 'tax_rate', 'effective_date', 'expiry_date'
        ]
    
    def create(self, validated_data):
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            validated_data['approved_by'] = request.user
        return super().create(validated_data)


class FeeInvoiceCreateSerializer(serializers.ModelSerializer):
    """Create fee invoice"""
    class Meta:
        model = FeeInvoice
        fields = [
            'student', 'term', 'academic_year', 'total_amount', 'due_date',
            'previous_balance', 'late_fee', 'waiver_amount', 'scholarship_amount',
            'payment_plan', 'notes'
        ]
    
    def create(self, validated_data):
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            validated_data['created_by'] = request.user
        
        # Auto-set issue date
        validated_data['issue_date'] = timezone.now().date()
        
        return super().create(validated_data)


class PaymentCreateSerializer(serializers.ModelSerializer):
    """Create payment"""
    class Meta:
        model = Payment
        fields = [
            'invoice', 'student', 'amount', 'method', 'channel',
            'mpesa_code', 'bank_transaction_ref', 'cheque_number', 'card_last4',
            'narration', 'attachments'
        ]
    
    def create(self, validated_data):
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            validated_data['received_by'] = request.user
        
        # Auto-set paid_at
        validated_data['paid_at'] = timezone.now()
        
        return super().create(validated_data)


#  ACTION SERIALIZERS 
class RecordPaymentSerializer(serializers.Serializer):
    """Record a payment for an invoice"""
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0.01)
    method = serializers.ChoiceField(choices=Payment.MethodChoices.choices)
    channel = serializers.ChoiceField(choices=Payment.ChannelChoices.choices)
    mpesa_code = serializers.CharField(required=False, allow_blank=True)
    bank_transaction_ref = serializers.CharField(required=False, allow_blank=True)
    narration = serializers.CharField(required=False, allow_blank=True)
    
    def create(self, validated_data):
        invoice = self.context['invoice']
        request = self.context['request']
        
        payment = Payment.objects.create(
            invoice=invoice,
            student=invoice.student,
            amount=validated_data['amount'],
            method=validated_data['method'],
            channel=validated_data['channel'],
            mpesa_code=validated_data.get('mpesa_code', ''),
            bank_transaction_ref=validated_data.get('bank_transaction_ref', ''),
            narration=validated_data.get('narration', ''),
            received_by=request.user,
            paid_at=timezone.now(),
            payment_status='completed'
        )
        
        return payment


class ApproveBursarySerializer(serializers.Serializer):
    """Approve a bursary application"""
    approval_date = serializers.DateField(default=timezone.now().date)
    conditions = serializers.CharField(required=False, allow_blank=True)
    
    def update(self, instance, validated_data):
        instance.bursary_status = 'approved'
        instance.approval_date = validated_data['approval_date']
        instance.conditions = validated_data.get('conditions', '')
        instance.approved_by = self.context['request'].user
        instance.save()
        return instance



class GenerateInvoiceSerializer(serializers.Serializer):
    """Generate invoice from fee structure"""
    student_id = serializers.UUIDField(required=True)
    term_id = serializers.UUIDField(required=True)
    academic_year_id = serializers.UUIDField(required=True)
    
    @transaction.atomic
    def create(self, validated_data):
        from students.models import Student
        from schools.models import Term, AcademicYear
        
        student = Student.objects.get(id=validated_data['student_id'])
        term = Term.objects.get(id=validated_data['term_id'])
        academic_year = AcademicYear.objects.get(id=validated_data['academic_year_id'])
        
        # Get fee structures for student's class
        fee_structures = FeeStructure.objects.filter(
            school=student.school,
            class_level=student.current_class.level if student.current_class else 'General',
            term=term,
            academic_year=academic_year,
            fees_status='active',
            is_compulsory=True
        )
        
        total_amount = fee_structures.aggregate(models.Sum('amount'))['amount__sum'] or 0
        
        # Create invoice
        invoice, created = FeeInvoice.objects.get_or_create(
            student=student,
            term=term,
            academic_year=academic_year,
            defaults={
                'school': student.school, 
                'total_amount': total_amount,
                'due_date': term.end_date,  # Use term end date if no fee_due_date
                'created_by': self.context['request'].user,
            }
        )
        
        return invoice


#  STATISTICS SERIALIZERS 
class FinanceStatisticsSerializer(serializers.Serializer):
    """Finance statistics"""
    start_date = serializers.DateField(required=True)
    end_date = serializers.DateField(required=True)
    
    def validate(self, data):
        if data['start_date'] > data['end_date']:
            raise serializers.ValidationError("Start date cannot be after end date")
        
        if (data['end_date'] - data['start_date']).days > 365:
            raise serializers.ValidationError("Date range cannot exceed 1 year")
        
        return data
    
    def get_statistics(self):
        start_date = self.validated_data['start_date']
        end_date = self.validated_data['end_date']
        
        # Get data
        payments = Payment.objects.filter(
            paid_at__date__range=[start_date, end_date],
            payment_status='completed'
        )
        
        invoices = FeeInvoice.objects.filter(
            issue_date__range=[start_date, end_date]
        )
        
        stats = {
            'period': f"{start_date} to {end_date}",
            'total_revenue': payments.aggregate(models.Sum('amount'))['amount__sum'] or 0,
            'total_invoiced': invoices.aggregate(models.Sum('total_amount'))['total_amount__sum'] or 0,
            'total_payments': payments.count(),
            'total_invoices': invoices.count(),
            'outstanding_balance': invoices.aggregate(models.Sum('balance'))['balance__sum'] or 0,
            'by_method': payments.values('method').annotate(
                total=models.Sum('amount'),
                count=models.Count('id')
            ),
            'by_status': invoices.values('invoice_status').annotate(
                total_amount=models.Sum('total_amount'),
                total_balance=models.Sum('balance'),
                count=models.Count('id')
            ),
        }
        
        return stats


class StudentFinanceSummarySerializer(serializers.Serializer):
    """Student finance summary"""
    student_id = serializers.UUIDField(required=True)
    
    def get_summary(self, student_id):
        from students.models import Student
        
        try:
            student = Student.objects.get(id=student_id)
        except Student.DoesNotExist:
            raise serializers.ValidationError("Student not found")
        
        invoices = FeeInvoice.objects.filter(student=student)
        payments = Payment.objects.filter(student=student, payment_status='completed')
        
        summary = {
            'student': {
                'name': student.user.get_full_name(),
                'admission_number': student.admission_number,
                'class': student.current_class.name if student.current_class else 'N/A',
            },
            'total_invoiced': invoices.aggregate(models.Sum('total_amount'))['total_amount__sum'] or 0,
            'total_paid': payments.aggregate(models.Sum('amount'))['amount__sum'] or 0,
            'total_balance': invoices.aggregate(models.Sum('balance'))['balance__sum'] or 0,
            'active_invoices': invoices.filter(invoice_status__in=['issued', 'partially_paid', 'overdue']).count(),
            'paid_invoices': invoices.filter(payment_status='paid').count(),
            'payment_plan': None,
            'bursaries': Bursary.objects.filter(student=student, bursary_status='approved').values('type', 'amount_awarded', 'term__name'),
            'recent_payments': PaymentListSerializer(payments.order_by('-paid_at')[:5], many=True).data,
        }
        
        # Check for active payment plan
        active_plan = PaymentPlan.objects.filter(student=student, payment_plan_status='active').first()
        if active_plan:
            summary['payment_plan'] = {
                'total_amount': active_plan.total_amount,
                'installment_amount': active_plan.installment_amount,
                'next_due_date': active_plan.next_due_date,
                'default_count': active_plan.default_count,
            }
        
        return summary
    


class FinancialTransactionListSerializer(serializers.ModelSerializer):
    """Simple financial transaction list"""
    transaction_type_display = serializers.CharField(source='get_transaction_type_display', read_only=True)
    category_display = serializers.CharField(source='get_fees_category_display', read_only=True)
    status_display = serializers.CharField(source='get_payment_status_display', read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.get_full_name', read_only=True, allow_null=True)
    
    class Meta:
        model = FinancialTransaction
        fields = [
            'id', 'transaction_type', 'transaction_type_display', 'finance_category', 'category_display',
            'amount', 'date', 'description', 'reference_number', 'transaction_status', 'status_display',
            'approved_by_name'
        ]

class FinancialTransactionDetailSerializer(serializers.ModelSerializer):
    """Full financial transaction details"""
    transaction_type_display = serializers.CharField(source='get_transaction_type_display', read_only=True)
    category_display = serializers.CharField(source='get_fees_category_display', read_only=True)
    status_display = serializers.CharField(source='get_payment_status_display', read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.get_full_name', read_only=True, allow_null=True)
    verified_by_name = serializers.CharField(source='verified_by.get_full_name', read_only=True, allow_null=True)
    
    class Meta:
        model = FinancialTransaction
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than zero")
        return value

class FinancialTransactionCreateSerializer(serializers.ModelSerializer):
    """Create financial transaction"""
    class Meta:
        model = FinancialTransaction
        fields = [
            'transaction_type', 'finance_category', 'amount', 'currency', 'date',
            'description', 'reference_number', 'account_debit', 'account_credit',
            'attachments'
        ]
    
    def create(self, validated_data):
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            validated_data['approved_by'] = request.user
        return super().create(validated_data)