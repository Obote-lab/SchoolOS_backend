from django.db.models import Count, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from ..models import ( Bursary, FeeInvoice, FeeStructure, FinancialTransaction,Payment, PaymentPlan,)
from .serializers import (
    ApproveBursarySerializer,BursaryDetailSerializer,
    FeeInvoiceCreateSerializer,FeeInvoiceDetailSerializer,
    FeeInvoiceListSerializer, FeeStructureCreateSerializer,
    FeeStructureDetailSerializer,FeeStructureListSerializer,
    # FinanceStatisticsSerializer,
    FinancialTransactionCreateSerializer,
    FinancialTransactionDetailSerializer,FinancialTransactionListSerializer,
    GenerateInvoiceSerializer,PaymentCreateSerializer,
    PaymentDetailSerializer,PaymentListSerializer,
    PaymentPlanDetailSerializer,RecordPaymentSerializer,
    StudentFinanceSummarySerializer,
    FinanceDashboardSerializer, FinanceReportSerializer,MpesaCallbackSerializer,
)

from core.choices.finance import (
    BursaryStatusChoices,
    FeesStatusChoices,
    FinanceTransactionStatusChoices,
    InvoiceStatusChoices,
    PaymentPlanStatusChoices,
    PaymentStatusChoices,
)
from drf_spectacular.utils import extend_schema, extend_schema_view
from drf_spectacular.types import OpenApiTypes




#  FEE STRUCTURE VIEWS
@extend_schema_view(
    list=extend_schema(tags=["Fee Structures"]),
    retrieve=extend_schema(tags=["Fee Structures"]),
    create=extend_schema(request=FeeStructureCreateSerializer, tags=["Fee Structures"]),
)
class FeeStructureViewSet(viewsets.ModelViewSet):
    """Fee structure management"""

    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["class_level", "term", "academic_year", "fees_category", "fees_status"]
    search_fields = ["description"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return FeeStructure.objects.none()
        user = self.request.user
        if hasattr(user, "school") and self.request.school:
            return FeeStructure.objects.filter(school=user.school)
        return FeeStructure.objects.all()

    def get_serializer_class(self):
        if self.action == "list":
            return FeeStructureListSerializer
        if self.action in ["create", "update", "partial_update"]:
            return FeeStructureCreateSerializer
        return FeeStructureDetailSerializer


    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        fee_structure = self.get_object()
        fee_structure.fees_status = FeesStatusChoices.APPROVED
        fee_structure.approved_by = request.user
        fee_structure.save(update_fields=["fees_status", "approved_by", "updated_at"])
        return Response({"status": "approved"})

    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        fee_structure = self.get_object()
        fee_structure.fees_status = FeesStatusChoices.ACTIVE
        fee_structure.save(update_fields=["fees_status", "updated_at"])
        return Response({"status": "activated"})

        # for_class
        fees_status=FeesStatusChoices.ACTIVE

    @action(detail=False, methods=["get"])
    def for_class(self, request):
        """Get fee structures for a specific class"""
        class_level = request.query_params.get("class_level")
        term_id = request.query_params.get("term")
        academic_year_id = request.query_params.get("academic_year")

        if not class_level or not term_id:
            return Response({"error": "class_level and term parameters required"}, status=400)

        fee_structures = FeeStructure.objects.filter(class_level=class_level, term_id=term_id, fees_status="active" )

        if academic_year_id:
            fee_structures = fee_structures.filter(academic_year_id=academic_year_id)

        serializer = FeeStructureListSerializer(fee_structures, many=True)
        return Response(serializer.data)


#  FEE INVOICE VIEWS
class FeeInvoiceViewSet(viewsets.ModelViewSet):
    """Fee invoice management"""

    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["student", "term", "academic_year", "invoice_status"]
    search_fields = ["invoice_number", "notes"]

    def get_queryset(self):
        # Filter by date range if provided
        if getattr(self, "swagger_fake_view", False):
            return FeeInvoice.objects.none()

        start_date = self.request.query_params.get("start_date")
        end_date = self.request.query_params.get("end_date")
        queryset = FeeInvoice.objects.all()
        if start_date and end_date:
            queryset = queryset.filter(issue_date__range=[start_date, end_date])
        user = self.request.user
        if hasattr(user, "student_profile"):
            queryset = queryset.filter(student=user.student_profile)

        if hasattr(user, "school"):
            queryset = queryset.filter(school=self.request.school)
        return queryset

    def get_serializer_class(self):
        if self.action == "list":
            return FeeInvoiceListSerializer
        elif self.action == "create":
            return FeeInvoiceCreateSerializer
        return FeeInvoiceDetailSerializer

    def perform_create(self, serializer):
        school = getattr(self.request, "school", None) or self.request.user.school
        serializer.save(created_by=self.request.user, school=school)

    
    @extend_schema(request=RecordPaymentSerializer, responses={200: OpenApiTypes.OBJECT}, tags=["Fee Invoices"])
    @action(detail=True, methods=["post"], url_path="record-payment")
    def record_payment(self, request, pk=None):
        """Record a payment for this invoice"""
        invoice = self.get_object()
        serializer = RecordPaymentSerializer(
            data=request.data, context={"invoice": invoice, "request": request}
        )
        serializer.is_valid(raise_exception=True)
        payment = serializer.save()

        return Response(
            {
                "status": "payment_recorded",
                "payment_id": str(payment.id),
                "payment_reference": payment.payment_reference,
                "invoice_balance": invoice.balance,
            }
        )

    @action(detail=True, methods=["post"])
    def issue(self, request, pk=None):
        """Issue the invoice"""
        invoice = self.get_object()
        invoice.invoice_status = InvoiceStatusChoices.ISSUED
        invoice.approved_by = request.user
        invoice.save()
        return Response({"status": "issued"})

    @action(detail=True, methods=["post"])
    def mark_paid(self, request, pk=None):
        """Mark invoice as paid"""
        invoice = self.get_object()
        invoice.invoice_status = InvoiceStatusChoices.PAID
        invoice.amount_paid = invoice.net_payable
        invoice.balance = 0
        invoice.save()
        return Response({"status": "marked_paid"})

    @action(detail=True, methods=["get"])
    def payment_history(self, request, pk=None):
        """Get payment history for this invoice"""
        invoice = self.get_object()
        payments = invoice.payments.all().order_by("-paid_at")
        serializer = PaymentListSerializer(payments, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["post"])
    def generate(self, request):
        """Generate invoice from fee structure"""
        serializer = GenerateInvoiceSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        invoice = serializer.save()
        return Response(
            {
                "status": "invoice_generated",
                "invoice_id": str(invoice.id),
                "invoice_number": invoice.invoice_number,
            }
        )

    @action(detail=False, methods=["get"])
    def overdue(self, request):
        """Get overdue invoices"""
        today = timezone.now().date()
        overdue_invoices = FeeInvoice.objects.filter(
            due_date__lt=today, invoice_status__in=[InvoiceStatusChoices.ISSUED, InvoiceStatusChoices.PARTIALLY_PAID]
        )
        serializer = self.get_serializer(overdue_invoices, many=True)
        return Response(serializer.data)


#  PAYMENT VIEWS
class PaymentViewSet(viewsets.ModelViewSet):
    """Payment management"""

    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["student", "invoice", "method", "payment_status", "received_by"]

    def get_queryset(self):
        user = self.request.user
        queryset = Payment.objects.all()

        if hasattr(user, "school"):
            queryset = queryset.filter(school=user.school)

        start_date = self.request.query_params.get("start_date")
        end_date = self.request.query_params.get("end_date")

        if start_date and end_date:
            queryset = queryset.filter(paid_at__date__range=[start_date, end_date])

        return queryset

    def get_serializer_class(self):
        if self.action == "list":
            return PaymentListSerializer
        elif self.action == "create":
            return PaymentCreateSerializer
        return PaymentDetailSerializer

    def perform_create(self, serializer):
        serializer.save(received_by=self.request.user)

    @action(detail=True, methods=["post"])
    def verify(self, request, pk=None):
        payment = self.get_object()
        if payment.payment_status == PaymentStatusChoices.COMPLETED:
            return Response({"detail": "Payment already verified"}, status=400)
        if getattr(payment, "ledger_posted", False):
            return Response({"detail": "Already posted to ledger"}, status=400)

        payment.payment_status = PaymentStatusChoices.COMPLETED
        payment.verified_by = request.user
        payment.save()

        payment.refresh_from_db()
        payment.invoice.refresh_from_db()
        return Response({
            "status": "verified",
            "invoice_balance": payment.invoice.balance,
            "payment_reference": payment.payment_reference,
        })

    @action(detail=True, methods=["post"])
    def reverse(self, request, pk=None):
        """Reverse payment"""
        payment = self.get_object()
        payment.payment_status = PaymentStatusChoices.REVERSED
        payment.reversal_reason = request.data.get("reason", "")
        payment.save()
        return Response({"status": "reversed"})

    @action(detail=False, methods=["get"])
    def today(self, request):
        """Get today's payments"""
        today = timezone.now().date()
        payments = Payment.objects.filter(
            paid_at__date=today, payment_status=PaymentStatusChoices.COMPLETED
        )
        serializer = self.get_serializer(payments, many=True)
        return Response(serializer.data)


#  PAYMENT PLAN VIEWS
class PaymentPlanViewSet(viewsets.ModelViewSet):
    """Payment plan management"""

    permission_classes = [IsAuthenticated]
    serializer_class = PaymentPlanDetailSerializer
    queryset = PaymentPlan.objects.all()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return PaymentPlan.objects.none()
        qs = PaymentPlan.objects.all()
        school = getattr(self.request, "school", None) or getattr(
            self.request.user, "school", None
        )
        if school:
            qs = qs.filter(school=school)
        return qs

    @action(detail=True, methods=["post"])
    def mark_defaulted(self, request, pk=None):
        """Mark payment plan as defaulted"""
        payment_plan = self.get_object()
        payment_plan.plan_status = PaymentPlanStatusChoices.DEFAULTED
        payment_plan.save()
        return Response({"status": "marked_defaulted"})


#  BURSARY VIEWS
class BursaryViewSet(viewsets.ModelViewSet):
    """Bursary management"""

    permission_classes = [IsAuthenticated]
    serializer_class = BursaryDetailSerializer

    def get_queryset(self):
        user = self.request.user
        queryset = Bursary.objects.all()

        if hasattr(user, "school"):
            queryset = queryset.filter(school=user.school)

        student_id = self.request.query_params.get("student")
        if student_id:
            queryset = queryset.filter(student_id=student_id)

        return queryset

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        """Approve bursary"""
        bursary = self.get_object()
        serializer = ApproveBursarySerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        bursary = serializer.update(bursary, serializer.validated_data)
        return Response({"status": "approved", "bursary_id": str(bursary.id)})

    @action(detail=True, methods=["post"])
    def disburse(self, request, pk=None):
        """Disburse bursary funds"""
        bursary = self.get_object()
        if bursary.bursary_status != BursaryStatusChoices.APPROVED:
            return Response({"error": "Bursary must be approved first"}, status=400)

        bursary.bursary_status = BursaryStatusChoices.DISBURSED
        bursary.disbursement_date = timezone.now().date()
        bursary.save()
        return Response({"status": "disbursed"})

    @action(detail=False, methods=["get"])
    def pending(self, request):
        """Get pending bursary applications"""
        pending_bursaries = Bursary.objects.filter(bursary_status=BursaryStatusChoices.APPLIED)
        serializer = self.get_serializer(pending_bursaries, many=True)
        return Response(serializer.data)


#  FINANCIAL TRANSACTION VIEWS
class FinancialTransactionViewSet(viewsets.ModelViewSet):
    """Financial transaction management"""

    permission_classes = [IsAuthenticated]
    serializer_class = FinancialTransactionDetailSerializer
    queryset = FinancialTransaction.objects.all()

    def get_queryset(self):
        user = self.request.user
        queryset = FinancialTransaction.objects.all()

        if hasattr(user, "school"):
            queryset = queryset.filter(school=user.school)

        start_date = self.request.query_params.get("start_date")
        end_date = self.request.query_params.get("end_date")

        if start_date and end_date:
            queryset = queryset.filter(date__range=[start_date, end_date])

        return queryset

    def get_serializer_class(self):
        if self.action == "list":
            return FinancialTransactionListSerializer
        elif self.action == "create":
            return FinancialTransactionCreateSerializer
        return FinancialTransactionDetailSerializer

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        """Approve transaction"""
        transaction = self.get_object()
        transaction.transaction_status = FinancialTransactionStatusChoices.APPROVED
        transaction.approved_by = request.user
        transaction.save()
        return Response({"status": "approved"})

    @action(detail=True, methods=["post"])
    def post(self, request, pk=None):
        """Post transaction to ledger"""
        transaction = self.get_object()
        transaction.transaction_status = FinancialTransactionStatusChoices.POSTED
        transaction.verified_by = request.user
        transaction.save()
        return Response({"status": "posted"})


#  DASHBOARD & STATISTICS VIEWS
class FinanceDashboardView(generics.GenericAPIView):
    """Finance dashboard"""

    permission_classes = [IsAuthenticated]
    serializer_class = FinanceDashboardSerializer
    queryset = FeeInvoice.objects.none()

    def get(self, request):
        data = {
            "today_stats": self.get_today_stats(),
            "monthly_summary": self.get_monthly_summary(),
            "recent_payments": self.get_recent_payments(),
            "overdue_invoices": self.get_overdue_invoices(),
            "pending_bursaries": self.get_pending_bursaries(),
        }
        return Response(data)

    def get_today_stats(self):
        today = timezone.now().date()
        user = self.request.user

        payments = Payment.objects.filter(
            paid_at__date=today, payment_status=PaymentStatusChoices.COMPLETED, school=user.school
        )

        invoices = FeeInvoice.objects.filter(issue_date=today, school=user.school)

        return {
            "date": today,
            "total_collected": payments.aggregate(Sum("amount"))["amount__sum"] or 0,
            "payments_count": payments.count(),
            "invoices_issued": invoices.count(),
            "invoices_amount": invoices.aggregate(Sum("total_amount"))[
                "total_amount__sum"
            ]
            or 0,
        }

    def get_monthly_summary(self):
        today = timezone.now().date()
        month_start = today.replace(day=1)
        user = self.request.user

        payments = Payment.objects.filter(
            paid_at__date__range=[month_start, today],
            payment_status=PaymentStatusChoices.COMPLETED,
            school=user.school,
        )

        invoices = FeeInvoice.objects.filter(
            issue_date__range=[month_start, today], school=user.school
        )

        return {
            "month": month_start.strftime("%B %Y"),
            "total_revenue": payments.aggregate(Sum("amount"))["amount__sum"] or 0,
            "total_invoiced": invoices.aggregate(Sum("total_amount"))[
                "total_amount__sum"
            ]
            or 0,
            "outstanding_balance": invoices.aggregate(Sum("balance"))["balance__sum"]
            or 0,
            "payment_methods": payments.values("method").annotate(
                total=Sum("amount"), count=Count("id")
            ),
        }

    def get_recent_payments(self):
        user = self.request.user
        payments = Payment.objects.filter(
            payment_status=PaymentStatusChoices.COMPLETED, school=user.school
        ).order_by("-paid_at")[:10]

        return PaymentListSerializer(payments, many=True).data

    def get_overdue_invoices(self):
        user = self.request.user
        overdue = FeeInvoice.objects.filter(
            due_date__lt=timezone.now().date(),
            invoice_status__in=[InvoiceStatusChoices.ISSUED, InvoiceStatusChoices.PARTIALLY_PAID],
            school=user.school,
        ).order_by("due_date")[:10]

        return FeeInvoiceListSerializer(overdue, many=True).data

    def get_pending_bursaries(self):
        user = self.request.user
        pending = Bursary.objects.filter(
            bursary_status=BursaryStatusChoices.APPLIED, school=user.school
        ).order_by("-created_at")[:5]

        return BursaryDetailSerializer(pending, many=True).data


class FinanceStatisticsView(generics.GenericAPIView):
    """Finance statistics"""

    permission_classes = [IsAuthenticated]
    serializer_class = FinanceDashboardSerializer
    queryset = FinancialTransaction.objects.none()

    def post(self, request):
        """Get financial statistics"""
        serializer = FinanceDashboardSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        stats = serializer.get_statistics()
        return Response(stats)


class StudentFinanceView(generics.GenericAPIView):
    """Student finance summary"""

    permission_classes = [IsAuthenticated]
    serializer_class = StudentFinanceSummarySerializer
    queryset = FeeInvoice.objects.none()

    def get(self, request):
        """Get student finance summary"""
        student_id = request.query_params.get("student")

        if not student_id:
            # If user is a student, use their own ID
            user = request.user
            if hasattr(user, "student_profile"):
                student_id = user.student_profile.id
            else:
                return Response({"error": "student parameter required"}, status=400)

        serializer = StudentFinanceSummarySerializer(data={"student_id": student_id})
        serializer.is_valid(raise_exception=True)
        summary = serializer.get_summary(student_id)
        return Response(summary)

    def post(self, request):
        student_id = request.data.get("student")

        if not student_id:
            return Response({"error": "student parameter required"}, status=400)

        user = request.user

        invoices = FeeInvoice.objects.filter(
            student_id=student_id, school=user.school
        ).order_by("-issue_date")

        payments = Payment.objects.filter(
            student_id=student_id, payment_status=PaymentStatusChoices.COMPLETED, school=user.school
        ).order_by("-paid_at")

        return Response(
            {
                "invoices": FeeInvoiceListSerializer(invoices, many=True).data,
                "payments": PaymentListSerializer(payments, many=True).data,
                "total_invoiced": invoices.aggregate(Sum("total_amount"))[
                    "total_amount__sum"
                ]
                or 0,
                "total_paid": payments.aggregate(Sum("amount"))["amount__sum"] or 0,
                "total_balance": invoices.aggregate(Sum("balance"))["balance__sum"]
                or 0,
            }
        )


#  REPORT VIEWS
class FinanceReportView(generics.GenericAPIView):
    """Finance reports"""

    permission_classes = [IsAuthenticated]
    serializer_class = FinanceReportSerializer
    queryset = FeeInvoice.objects.none()

    def post(self, request):
        """Generate finance report"""
        report_type = request.data.get("type", "revenue")
        start_date = request.data.get("start_date")
        end_date = request.data.get("end_date")
        format = request.data.get("format", "json")

        if not start_date or not end_date:
            return Response({"error": "start_date and end_date required"}, status=400)

        if report_type == "revenue":
            report = self.generate_revenue_report(start_date, end_date)
        elif report_type == "invoices":
            report = self.generate_invoice_report(start_date, end_date)
        elif report_type == "payments":
            report = self.generate_payment_report(start_date, end_date)
        elif report_type == "students":
            report = self.generate_student_report(start_date, end_date)
        else:
            return Response({"error": "Invalid report type"}, status=400)

        return Response(report)

    def generate_revenue_report(self, start_date, end_date):
        """Generate revenue report"""
        payments = Payment.objects.filter(
            paid_at__date__range=[start_date, end_date], payment_status=PaymentStatusChoices.COMPLETED
        )

        revenue_by_method = payments.values("method").annotate(
            total=Sum("amount"), count=Count("id")
        )

        revenue_by_day = (
            payments.values("paid_at__date")
            .annotate(total=Sum("amount"), count=Count("id"))
            .order_by("paid_at__date")
        )

        return {
            "report_type": "revenue",
            "period": f"{start_date} to {end_date}",
            "total_revenue": payments.aggregate(Sum("amount"))["amount__sum"] or 0,
            "total_transactions": payments.count(),
            "revenue_by_method": list(revenue_by_method),
            "revenue_by_day": list(revenue_by_day),
        }

    def generate_invoice_report(self, start_date, end_date):
        """Generate invoice report"""
        invoices = FeeInvoice.objects.filter(issue_date__range=[start_date, end_date])

        invoices_by_status = invoices.values("invoice_status").annotate(
            total_amount=Sum("total_amount"),
            total_balance=Sum("balance"),
            count=Count("id"),
        )

        invoices_by_class = invoices.values("student__current_class__level").annotate(
            total_amount=Sum("total_amount"),
            total_balance=Sum("balance"),
            count=Count("id"),
        )

        return {
            "report_type": "invoices",
            "period": f"{start_date} to {end_date}",
            "total_invoiced": invoices.aggregate(Sum("total_amount"))[
                "total_amount__sum"
            ]
            or 0,
            "total_outstanding": invoices.aggregate(Sum("balance"))["balance__sum"]
            or 0,
            "total_invoices": invoices.count(),
            "invoices_by_status": list(invoices_by_status),
            "invoices_by_class": list(invoices_by_class),
        }

    def generate_payment_report(self, start_date, end_date):
        """Generate payment report"""
        payments = Payment.objects.filter(
            paid_at__date__range=[start_date, end_date], payment_status=PaymentStatusChoices.COMPLETED
        )

        payments_by_method = payments.values("method").annotate(
            total=Sum("amount"), count=Count("id")
        )

        top_payers = (
            payments.values(
                "student__admission_number",
                "student__user__first_name",
                "student__user__last_name",
            )
            .annotate(total=Sum("amount"), count=Count("id"))
            .order_by("-total")[:10]
        )

        return {
            "report_type": "payments",
            "period": f"{start_date} to {end_date}",
            "total_payments": payments.aggregate(Sum("amount"))["amount__sum"] or 0,
            "payment_count": payments.count(),
            "payments_by_method": list(payments_by_method),
            "top_payers": list(top_payers),
        }

    def generate_student_report(self, start_date, end_date):
        """Generate student finance report"""
        students = (
            FeeInvoice.objects.filter(issue_date__range=[start_date, end_date])
            .values(
                "student__admission_number",
                "student__user__first_name",
                "student__user__last_name",
                "student__current_class__level",
            )
            .annotate(
                total_invoiced=Sum("total_amount"),
                total_paid=Sum("amount_paid"),
                total_balance=Sum("balance"),
                invoice_count=Count("id"),
            )
            .order_by("-total_balance")
        )

        return {
            "report_type": "students",
            "period": f"{start_date} to {end_date}",
            "total_students": students.count(),
            "total_outstanding": sum(item["total_balance"] or 0 for item in students),
            "student_details": list(students),
        }


#  MPESA CALLBACK VIEW
class MpesaCallbackView(generics.GenericAPIView):
    """MPesa payment callback handler"""

    permission_classes = []
    serializer_class = MpesaCallbackSerializer
    queryset = Payment.objects.none()

    def post(self, request):
        """Handle MPesa callback"""
        try:
            data = request.data

            # Extract payment details from MPesa callback
            mpesa_code = data.get("MpesaReceiptNumber")
            phone = data.get("PhoneNumber")
            amount = data.get("Amount")
            transaction_date = data.get("TransactionDate")

            # TODO: Implement MPesa callback processing
            # This would typically involve:
            # 1. Validating the callback
            # 2. Finding the associated invoice
            # 3. Creating a payment record
            # 4. Updating the invoice balance

            return Response({"ResultCode": 0, "ResultDesc": "Success"})

        except Exception as e:
            return Response({"ResultCode": 1, "ResultDesc": str(e)})
