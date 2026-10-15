from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .api.viewsets import (
    BursaryViewSet,
    FeeInvoiceViewSet,
    FeeStructureViewSet,
    FinanceDashboardView,
    FinanceReportView,
    FinancialTransactionViewSet,
    MpesaCallbackView,
    PaymentPlanViewSet,
    PaymentViewSet,
    SchoolPaymentAccountViewSet,
    StudentFinanceView,
)

router = DefaultRouter()

# Core resources
router.register(r"fee-structures", FeeStructureViewSet, basename="fee-structure")
router.register(r"invoices", FeeInvoiceViewSet, basename="invoice")
router.register(r"payments", PaymentViewSet, basename="payment")
router.register(r"payment-plans", PaymentPlanViewSet, basename="payment-plan")
router.register(r"bursaries", BursaryViewSet, basename="bursary")
router.register(r"transactions", FinancialTransactionViewSet, basename="transaction")
router.register(r"payment-accounts",SchoolPaymentAccountViewSet,basename="payment-account")

urlpatterns = [
    # Router endpoints
    path("", include(router.urls)),
    # Custom views
    path("dashboard/", FinanceDashboardView.as_view(), name="finance-dashboard"),
    path("student-finance/", StudentFinanceView.as_view(), name="student-finance"),
    path("reports/", FinanceReportView.as_view(), name="finance-reports"),

    # M-Pesa Daraja callback (no auth)
    path("mpesa-callback/", MpesaCallbackView.as_view(), name="mpesa-callback"),
]