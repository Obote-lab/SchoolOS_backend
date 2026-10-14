from django.db.models import Count, Sum
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import filters, generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
import logging
from rest_framework.permissions import AllowAny
from finance.services.mpesa import MpesaService

logger = logging.getLogger(__name__)

from core.choices.finance import (
    BursaryStatusChoices,
    FeesStatusChoices,
    FinanceTransactionStatusChoices,
    InvoiceStatusChoices,
    PaymentPlanStatusChoices,
    PaymentStatusChoices,
)

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
from .serializers import (
    ApproveBursarySerializer,
    BursaryDetailSerializer,
    FeeInvoiceCreateSerializer,
    FeeInvoiceDetailSerializer,
    FeeInvoiceListSerializer,
    FeeStructureCreateSerializer,
    FeeStructureDetailSerializer,
    FeeStructureListSerializer,
    FinancialTransactionCreateSerializer,
    FinancialTransactionDetailSerializer,
    FinancialTransactionListSerializer,
    FinanceDashboardSerializer,
    FinanceReportSerializer,
    GenerateInvoiceSerializer,
    MpesaCallbackSerializer,
    PaymentCreateSerializer,
    PaymentDetailSerializer,
    PaymentListSerializer,
    PaymentPlanDetailSerializer,
    RecordPaymentSerializer,
    StudentFinanceSummarySerializer,
    StkPushSerializer
)


# Helpers

def _school(request):
    """Prefer middleware-injected school, fall back to user.school."""
    return getattr(request, "school", None) or getattr(request.user, "school", None)


# Fee Structure
@extend_schema_view(
    list=extend_schema(tags=["Fee Structures"]),
    retrieve=extend_schema(tags=["Fee Structures"]),
    create=extend_schema(request=FeeStructureCreateSerializer, tags=["Fee Structures"]),
    update=extend_schema(tags=["Fee Structures"]),
    partial_update=extend_schema(tags=["Fee Structures"]),
    destroy=extend_schema(tags=["Fee Structures"]),
)
class FeeStructureViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = [
        "class_level",
        "level",
        "term",
        "academic_year",
        "fees_category",
        "fees_status",
    ]
    search_fields = ["description", "class_level"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return FeeStructure.objects.none()
        school = _school(self.request)
        qs = FeeStructure.objects.select_related(
            "school", "term", "academic_year", "level", "approved_by"
        )
        if school:
            return qs.filter(school=school)
        if self.request.user.is_superuser:
            return qs
        return qs.none()

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

    @action(detail=False, methods=["get"])
    def for_class(self, request):
        """Get active fee structures for a specific class / term."""
        class_level = request.query_params.get("class_level")
        term_id = request.query_params.get("term")
        academic_year_id = request.query_params.get("academic_year")

        if not class_level or not term_id:
            return Response(
                {"error": "class_level and term parameters required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        qs = self.get_queryset().filter(
            class_level=class_level,
            term_id=term_id,
            fees_status=FeesStatusChoices.ACTIVE,
        )
        if academic_year_id:
            qs = qs.filter(academic_year_id=academic_year_id)

        serializer = FeeStructureListSerializer(qs, many=True)
        return Response(serializer.data)


# # Fee Invoice
# @extend_schema(tags=["Fee Invoices"])
# class FeeInvoiceViewSet(viewsets.ModelViewSet):
#     permission_classes = [IsAuthenticated]
#     filter_backends = [DjangoFilterBackend, filters.SearchFilter]
#     filterset_fields = ["student", "term", "academic_year", "invoice_status"]
#     search_fields = ["invoice_number", "notes"]

#     def get_queryset(self):
#         if getattr(self, "swagger_fake_view", False):
#             return FeeInvoice.objects.none()

#         qs = FeeInvoice.objects.select_related(
#             "student__user", "term", "academic_year", "school", "created_by"
#         ).prefetch_related("items", "payments", "allocations")

#         school = _school(self.request)
#         if school:
#             qs = qs.filter(school=school)

#         # Student can only see their own invoices
#         if hasattr(self.request.user, "student_profile"):
#             qs = qs.filter(student=self.request.user.student_profile)

#         start_date = self.request.query_params.get("start_date")
#         end_date = self.request.query_params.get("end_date")
#         if start_date and end_date:
#             qs = qs.filter(issue_date__range=[start_date, end_date])

#         return qs

#     def get_serializer_class(self):
#         if self.action == "list":
#             return FeeInvoiceListSerializer
#         if self.action in ["create", "update", "partial_update"]:
#             return FeeInvoiceCreateSerializer
#         return FeeInvoiceDetailSerializer

#     def perform_create(self, serializer):
#         school = _school(self.request)
#         serializer.save(created_by=self.request.user, school=school)

#     @extend_schema(
#         request=RecordPaymentSerializer,
#         responses={200: OpenApiTypes.OBJECT},
#         tags=["Fee Invoices"],
#     )
#     @action(detail=True, methods=["post"], url_path="record-payment")
#     def record_payment(self, request, pk=None):
#         """Record a manual payment against this invoice."""
#         invoice = self.get_object()
#         serializer = RecordPaymentSerializer(
#             data=request.data, context={"invoice": invoice, "request": request}
#         )
#         serializer.is_valid(raise_exception=True)
#         payment = serializer.save()

#         # Refresh so we return the latest balance after signals
#         invoice.refresh_from_db()

#         return Response(
#             {
#                 "status": "payment_recorded",
#                 "payment_id": str(payment.id),
#                 "payment_reference": payment.payment_reference,
#                 "payment_status": payment.payment_status,
#                 "invoice_balance": str(invoice.balance),
#             }
#         )

#     @action(detail=True, methods=["post"])
#     def issue(self, request, pk=None):
#         invoice = self.get_object()
#         if invoice.invoice_status != InvoiceStatusChoices.DRAFT:
#             return Response(
#                 {"detail": "Only DRAFT invoices can be issued."},
#                 status=status.HTTP_400_BAD_REQUEST,
#             )
#         invoice.invoice_status = InvoiceStatusChoices.ISSUED
#         invoice.approved_by = request.user
#         invoice.save(update_fields=["invoice_status", "approved_by", "updated_at"])
#         return Response({"status": "issued"})

#     @action(detail=True, methods=["post"])
#     def mark_paid(self, request, pk=None):
#         """Force-mark as paid (use with care – prefer real payments)."""
#         invoice = self.get_object()
#         invoice.invoice_status = InvoiceStatusChoices.PAID
#         invoice.amount_paid = invoice.net_payable
#         invoice.balance = 0
#         invoice.save(
#             update_fields=["invoice_status", "amount_paid", "balance", "updated_at"]
#         )
#         return Response({"status": "marked_paid"})

#     @action(detail=True, methods=["get"])
#     def payment_history(self, request, pk=None):
#         invoice = self.get_object()
#         payments = invoice.payments.all().order_by("-paid_at")
#         serializer = PaymentListSerializer(payments, many=True)
#         return Response(serializer.data)

#     @action(detail=False, methods=["post"])
#     def generate(self, request):
#         """Generate invoice from approved fee structures + create line items."""
#         serializer = GenerateInvoiceSerializer(
#             data=request.data, context={"request": request}
#         )
#         serializer.is_valid(raise_exception=True)
#         invoice = serializer.save()
#         return Response(
#             {
#                 "status": "invoice_generated",
#                 "invoice_id": str(invoice.id),
#                 "invoice_number": invoice.invoice_number,
#                 "total_amount": str(invoice.total_amount),
#                 "balance": str(invoice.balance),
#             }
#         )

#     @action(detail=False, methods=["get"])
#     def overdue(self, request):
#         today = timezone.now().date()
#         qs = self.get_queryset().filter(
#             due_date__lt=today,
#             invoice_status__in=[
#                 InvoiceStatusChoices.ISSUED,
#                 InvoiceStatusChoices.PARTIALLY_PAID,
#             ],
#         )
#         serializer = FeeInvoiceListSerializer(qs, many=True)
#         return Response(serializer.data)



@extend_schema(tags=["Fee Invoices"])
class FeeInvoiceViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["student", "term", "academic_year", "invoice_status"]
    search_fields = ["invoice_number", "notes"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return FeeInvoice.objects.none()

        qs = FeeInvoice.objects.select_related(
            "student__user", "term", "academic_year", "school", "created_by"
        ).prefetch_related("items", "payments", "allocations")

        school = _school(self.request)
        if school:
            qs = qs.filter(school=school)

        # Student can only see their own invoices
        if hasattr(self.request.user, "student_profile"):
            qs = qs.filter(student=self.request.user.student_profile)

        start_date = self.request.query_params.get("start_date")
        end_date = self.request.query_params.get("end_date")
        if start_date and end_date:
            qs = qs.filter(issue_date__range=[start_date, end_date])

        return qs

    def get_serializer_class(self):
        if self.action == "list":
            return FeeInvoiceListSerializer
        if self.action in ["create", "update", "partial_update"]:
            return FeeInvoiceCreateSerializer
        return FeeInvoiceDetailSerializer

    def perform_create(self, serializer):
        school = _school(self.request)
        serializer.save(created_by=self.request.user, school=school)

    # ------------------------------------------------------------------
    # Manual payment (cash / bank / already-paid M-Pesa code)
    # ------------------------------------------------------------------
    @extend_schema(
        request=RecordPaymentSerializer,
        responses={200: OpenApiTypes.OBJECT},
        tags=["Fee Invoices"],
    )
    @action(detail=True, methods=["post"], url_path="record-payment")
    def record_payment(self, request, pk=None):
        """Record a manual payment against this invoice."""
        invoice = self.get_object()
        serializer = RecordPaymentSerializer(
            data=request.data, context={"invoice": invoice, "request": request}
        )
        serializer.is_valid(raise_exception=True)
        payment = serializer.save()

        invoice.refresh_from_db()

        return Response(
            {
                "status": "payment_recorded",
                "payment_id": str(payment.id),
                "payment_reference": payment.payment_reference,
                "payment_status": payment.payment_status,
                "invoice_balance": str(invoice.balance),
            }
        )

    # STK Push (Lipa Na M-Pesa)
    @extend_schema(
        request=StkPushSerializer,
        responses={200: OpenApiTypes.OBJECT},
        tags=["Fee Invoices"],
    )
    @action(detail=True, methods=["post"], url_path="stk-push")
    def stk_push(self, request, pk=None):
        """
        Initiate an M-Pesa STK Push for this invoice.
        The parent will receive a prompt on their phone to enter the M-Pesa PIN.
        """
        from finance.services.mpesa import MpesaError, MpesaService

        invoice = self.get_object()

        if invoice.balance <= 0:
            return Response(
                {"detail": "Invoice has no outstanding balance."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = StkPushSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        phone = serializer.validated_data["phone"]
        amount = serializer.validated_data.get("amount") or invoice.balance

        if amount > invoice.balance:
            return Response(
                {
                    "detail": f"Amount cannot exceed outstanding balance of KES {invoice.balance}."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            service = MpesaService()
            payment = service.stk_push(
                phone=phone,
                amount=amount,
                account_reference=invoice.invoice_number[-12:],  # max 12 chars
                transaction_desc=f"Fees {invoice.invoice_number}"[:13],
                invoice=invoice,
                student=invoice.student,
                school=invoice.school,
                initiated_by=request.user,
            )
        except MpesaError as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except Exception as e:
            return Response(
                {"detail": f"Unexpected error: {e}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            {
                "status": "stk_push_initiated",
                "payment_id": str(payment.id),
                "payment_reference": payment.payment_reference,
                "checkout_request_id": payment.checkout_request_id,
                "phone": payment.mpesa_phone,
                "amount": str(payment.amount),
                "message": "STK Push sent. Ask the parent to enter their M-Pesa PIN.",
            },
            status=status.HTTP_200_OK,
        )

    # ------------------------------------------------------------------
    # Other actions
    # ------------------------------------------------------------------
    @action(detail=True, methods=["post"])
    def issue(self, request, pk=None):
        invoice = self.get_object()
        if invoice.invoice_status != InvoiceStatusChoices.DRAFT:
            return Response(
                {"detail": "Only DRAFT invoices can be issued."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        invoice.invoice_status = InvoiceStatusChoices.ISSUED
        invoice.approved_by = request.user
        invoice.save(update_fields=["invoice_status", "approved_by", "updated_at"])
        return Response({"status": "issued"})

    @action(detail=True, methods=["post"])
    def mark_paid(self, request, pk=None):
        """Force-mark as paid (use with care – prefer real payments)."""
        invoice = self.get_object()
        invoice.invoice_status = InvoiceStatusChoices.PAID
        invoice.amount_paid = invoice.net_payable
        invoice.balance = 0
        invoice.save(
            update_fields=["invoice_status", "amount_paid", "balance", "updated_at"]
        )
        return Response({"status": "marked_paid"})

    @action(detail=True, methods=["get"])
    def payment_history(self, request, pk=None):
        invoice = self.get_object()
        payments = invoice.payments.all().order_by("-paid_at")
        serializer = PaymentListSerializer(payments, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["post"])
    def generate(self, request):
        """Generate invoice from approved fee structures + create line items."""
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
                "total_amount": str(invoice.total_amount),
                "balance": str(invoice.balance),
            }
        )

    @action(detail=False, methods=["get"])
    def overdue(self, request):
        today = timezone.now().date()
        qs = self.get_queryset().filter(
            due_date__lt=today,
            invoice_status__in=[
                InvoiceStatusChoices.ISSUED,
                InvoiceStatusChoices.PARTIALLY_PAID,
            ],
        )
        serializer = FeeInvoiceListSerializer(qs, many=True)
        return Response(serializer.data)



# Payment
@extend_schema(tags=["Payments"])
class PaymentViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = [
        "student",
        "invoice",
        "method",
        "payment_status",
        "received_by",
    ]
    search_fields = ["payment_reference", "mpesa_receipt", "bank_ref"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Payment.objects.none()

        qs = Payment.objects.select_related(
            "student__user", "invoice", "school", "received_by", "verified_by"
        ).prefetch_related("allocations")

        school = _school(self.request)
        if school:
            qs = qs.filter(school=school)

        start_date = self.request.query_params.get("start_date")
        end_date = self.request.query_params.get("end_date")
        if start_date and end_date:
            qs = qs.filter(paid_at__date__range=[start_date, end_date])

        return qs

    def get_serializer_class(self):
        if self.action == "list":
            return PaymentListSerializer
        if self.action in ["create", "update", "partial_update"]:
            return PaymentCreateSerializer
        return PaymentDetailSerializer

    def perform_create(self, serializer):
        serializer.save(received_by=self.request.user)

    @action(detail=True, methods=["post"])
    def verify(self, request, pk=None):
        """Mark a PENDING payment as COMPLETED (triggers allocation + ledger)."""
        payment = self.get_object()

        if payment.payment_status == PaymentStatusChoices.COMPLETED:
            return Response(
                {"detail": "Payment already verified"}, status=status.HTTP_400_BAD_REQUEST
            )
        if getattr(payment, "ledger_posted", False):
            return Response(
                {"detail": "Already posted to ledger"}, status=status.HTTP_400_BAD_REQUEST
            )

        payment.payment_status = PaymentStatusChoices.COMPLETED
        payment.verified_by = request.user
        payment.save(update_fields=["payment_status", "verified_by", "updated_at"])

        payment.refresh_from_db()
        balance = None
        if payment.invoice_id:
            payment.invoice.refresh_from_db()
            balance = str(payment.invoice.balance)

        return Response(
            {
                "status": "verified",
                "payment_reference": payment.payment_reference,
                "invoice_balance": balance,
            }
        )

    @action(detail=True, methods=["post"])
    def reverse(self, request, pk=None):
        payment = self.get_object()
        if payment.payment_status == PaymentStatusChoices.REVERSED:
            return Response(
                {"detail": "Already reversed"}, status=status.HTTP_400_BAD_REQUEST
            )

        payment.payment_status = PaymentStatusChoices.REVERSED
        payment.reversal_reason = request.data.get("reason", "")
        payment.save(
            update_fields=["payment_status", "reversal_reason", "updated_at"]
        )
        return Response({"status": "reversed"})

    @action(detail=False, methods=["get"])
    def today(self, request):
        today = timezone.now().date()
        qs = self.get_queryset().filter(
            paid_at__date=today,
            payment_status=PaymentStatusChoices.COMPLETED,
        )
        serializer = PaymentListSerializer(qs, many=True)
        return Response(serializer.data)


# Payment Plan
@extend_schema(tags=["Payment Plans"])
class PaymentPlanViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = PaymentPlanDetailSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["student", "term", "plan_status"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return PaymentPlan.objects.none()
        qs = PaymentPlan.objects.select_related("student__user", "term", "school")
        school = _school(self.request)
        if school:
            return qs.filter(school=school)
        if self.request.user.is_superuser:
            return qs
        return qs.none()

    @action(detail=True, methods=["post"])
    def mark_defaulted(self, request, pk=None):
        plan = self.get_object()
        plan.plan_status = PaymentPlanStatusChoices.DEFAULTED
        plan.save(update_fields=["plan_status", "updated_at"])
        return Response({"status": "marked_defaulted"})



# Bursary
@extend_schema(tags=["Bursaries"])
class BursaryViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = BursaryDetailSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["student", "bursary_status", "source", "term"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Bursary.objects.none()
        qs = Bursary.objects.select_related(
            "student__user", "school", "term", "academic_year", "approved_by"
        )
        school = _school(self.request)
        if school:
            qs = qs.filter(school=school)

        student_id = self.request.query_params.get("student")
        if student_id:
            qs = qs.filter(student_id=student_id)
        return qs

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        bursary = self.get_object()
        serializer = ApproveBursarySerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        bursary = serializer.update(bursary, serializer.validated_data)
        return Response({"status": "approved", "bursary_id": str(bursary.id)})

    @action(detail=True, methods=["post"])
    def disburse(self, request, pk=None):
        bursary = self.get_object()
        if bursary.bursary_status != BursaryStatusChoices.APPROVED:
            return Response(
                {"error": "Bursary must be approved first"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        bursary.bursary_status = BursaryStatusChoices.DISBURSED
        bursary.disbursement_date = timezone.now().date()
        bursary.save(
            update_fields=["bursary_status", "disbursement_date", "updated_at"]
        )
        return Response({"status": "disbursed"})

    @action(detail=False, methods=["get"])
    def pending(self, request):
        qs = self.get_queryset().filter(bursary_status=BursaryStatusChoices.APPLIED)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)


# Financial Transaction
@extend_schema(tags=["Financial Transactions"])
class FinancialTransactionViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = [
        "transaction_type",
        "finance_category",
        "transaction_status",
    ]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return FinancialTransaction.objects.none()
        qs = FinancialTransaction.objects.select_related(
            "school", "approved_by", "verified_by"
        )
        school = _school(self.request)
        if school:
            qs = qs.filter(school=school)

        start_date = self.request.query_params.get("start_date")
        end_date = self.request.query_params.get("end_date")
        if start_date and end_date:
            qs = qs.filter(date__range=[start_date, end_date])
        return qs

    def get_serializer_class(self):
        if self.action == "list":
            return FinancialTransactionListSerializer
        if self.action in ["create", "update", "partial_update"]:
            return FinancialTransactionCreateSerializer
        return FinancialTransactionDetailSerializer

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        txn = self.get_object()
        txn.transaction_status = FinanceTransactionStatusChoices.APPROVED
        txn.approved_by = request.user
        txn.save(update_fields=["transaction_status", "approved_by", "updated_at"])
        return Response({"status": "approved"})

    @action(detail=True, methods=["post"])
    def post(self, request, pk=None):
        txn = self.get_object()
        txn.transaction_status = FinanceTransactionStatusChoices.POSTED
        txn.verified_by = request.user
        txn.save(update_fields=["transaction_status", "verified_by", "updated_at"])
        return Response({"status": "posted"})


# Dashboard & Statistics
class FinanceDashboardView(generics.GenericAPIView):
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
        school = _school(self.request)

        payments = Payment.objects.filter(
            paid_at__date=today,
            payment_status=PaymentStatusChoices.COMPLETED,
            school=school,
        )
        invoices = FeeInvoice.objects.filter(issue_date=today, school=school)

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
        school = _school(self.request)

        payments = Payment.objects.filter(
            paid_at__date__range=[month_start, today],
            payment_status=PaymentStatusChoices.COMPLETED,
            school=school,
        )
        invoices = FeeInvoice.objects.filter(
            issue_date__range=[month_start, today], school=school
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
            "payment_methods": list(
                payments.values("method").annotate(
                    total=Sum("amount"), count=Count("id")
                )
            ),
        }

    def get_recent_payments(self):
        school = _school(self.request)
        payments = (
            Payment.objects.filter(
                payment_status=PaymentStatusChoices.COMPLETED, school=school
            )
            .order_by("-paid_at")[:10]
        )
        return PaymentListSerializer(payments, many=True).data

    def get_overdue_invoices(self):
        school = _school(self.request)
        overdue = (
            FeeInvoice.objects.filter(
                due_date__lt=timezone.now().date(),
                invoice_status__in=[
                    InvoiceStatusChoices.ISSUED,
                    InvoiceStatusChoices.PARTIALLY_PAID,
                ],
                school=school,
            )
            .order_by("due_date")[:10]
        )
        return FeeInvoiceListSerializer(overdue, many=True).data

    def get_pending_bursaries(self):
        school = _school(self.request)
        pending = (
            Bursary.objects.filter(
                bursary_status=BursaryStatusChoices.APPLIED, school=school
            )
            .order_by("-created_at")[:5]
        )
        return BursaryDetailSerializer(pending, many=True).data


class StudentFinanceView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = StudentFinanceSummarySerializer
    queryset = FeeInvoice.objects.none()

    def get(self, request):
        student_id = request.query_params.get("student")

        if not student_id:
            if hasattr(request.user, "student_profile"):
                student_id = str(request.user.student_profile.id)
            else:
                return Response(
                    {"error": "student parameter required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        serializer = StudentFinanceSummarySerializer(data={"student_id": student_id})
        serializer.is_valid(raise_exception=True)
        summary = serializer.get_summary(student_id)
        return Response(summary)

    def post(self, request):
        student_id = request.data.get("student")
        if not student_id:
            return Response(
                {"error": "student parameter required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        school = _school(request)
        invoices = FeeInvoice.objects.filter(
            student_id=student_id, school=school
        ).order_by("-issue_date")
        payments = Payment.objects.filter(
            student_id=student_id,
            payment_status=PaymentStatusChoices.COMPLETED,
            school=school,
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

# Reports

class FinanceReportView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = FinanceReportSerializer
    queryset = FeeInvoice.objects.none()

    def post(self, request):
        report_type = request.data.get("type", "revenue")
        start_date = request.data.get("start_date")
        end_date = request.data.get("end_date")

        if not start_date or not end_date:
            return Response(
                {"error": "start_date and end_date required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        school = _school(request)

        if report_type == "revenue":
            report = self._revenue_report(start_date, end_date, school)
        elif report_type == "invoices":
            report = self._invoice_report(start_date, end_date, school)
        elif report_type == "payments":
            report = self._payment_report(start_date, end_date, school)
        elif report_type == "students":
            report = self._student_report(start_date, end_date, school)
        else:
            return Response(
                {"error": "Invalid report type"}, status=status.HTTP_400_BAD_REQUEST
            )

        return Response(report)

    def _revenue_report(self, start_date, end_date, school):
        payments = Payment.objects.filter(
            paid_at__date__range=[start_date, end_date],
            payment_status=PaymentStatusChoices.COMPLETED,
            school=school,
        )
        return {
            "report_type": "revenue",
            "period": f"{start_date} to {end_date}",
            "total_revenue": payments.aggregate(Sum("amount"))["amount__sum"] or 0,
            "total_transactions": payments.count(),
            "revenue_by_method": list(
                payments.values("method").annotate(
                    total=Sum("amount"), count=Count("id")
                )
            ),
            "revenue_by_day": list(
                payments.values("paid_at__date")
                .annotate(total=Sum("amount"), count=Count("id"))
                .order_by("paid_at__date")
            ),
        }

    def _invoice_report(self, start_date, end_date, school):
        invoices = FeeInvoice.objects.filter(
            issue_date__range=[start_date, end_date], school=school
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
            "invoices_by_status": list(
                invoices.values("invoice_status").annotate(
                    total_amount=Sum("total_amount"),
                    total_balance=Sum("balance"),
                    count=Count("id"),
                )
            ),
        }

    def _payment_report(self, start_date, end_date, school):
        payments = Payment.objects.filter(
            paid_at__date__range=[start_date, end_date],
            payment_status=PaymentStatusChoices.COMPLETED,
            school=school,
        )
        return {
            "report_type": "payments",
            "period": f"{start_date} to {end_date}",
            "total_payments": payments.aggregate(Sum("amount"))["amount__sum"] or 0,
            "payment_count": payments.count(),
            "payments_by_method": list(
                payments.values("method").annotate(
                    total=Sum("amount"), count=Count("id")
                )
            ),
            "top_payers": list(
                payments.values(
                    "student__admission_number",
                    "student__user__first_name",
                    "student__user__last_name",
                )
                .annotate(total=Sum("amount"), count=Count("id"))
                .order_by("-total")[:10]
            ),
        }

    def _student_report(self, start_date, end_date, school):
        students = (
            FeeInvoice.objects.filter(
                issue_date__range=[start_date, end_date], school=school
            )
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

class MpesaCallbackView(generics.GenericAPIView):
    """
    Safaricom Daraja STK / C2B callback endpoint.
    No authentication – Safaricom calls this URL directly.
    """

    permission_classes = [AllowAny]
    serializer_class = MpesaCallbackSerializer
    queryset = Payment.objects.none()
    authentication_classes = []  # Explicitly disable all auth

    def post(self, request, *args, **kwargs):
        logger.info("M-Pesa callback received: %s", request.data)

        try:
            service = MpesaService()
            result = service.handle_stk_callback(request.data)
            return Response(result, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception("Unhandled error in M-Pesa callback")
            # Always return ResultCode 0 so Safaricom stops retrying
            return Response(
                {"ResultCode": 0, "ResultDesc": f"Accepted with internal error: {e}"},
                status=status.HTTP_200_OK,
            )