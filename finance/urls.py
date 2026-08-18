from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .api.viewsets import (
    BursaryViewSet,
    FeeInvoiceViewSet,
    FeeStructureViewSet,
    FinanceDashboardView,
    FinanceReportView,
    FinanceStatisticsView,
    FinancialTransactionViewSet,
    MpesaCallbackView,
    PaymentPlanViewSet,
    PaymentViewSet,
    StudentFinanceView,
)

router = DefaultRouter()
router.register(r"fee-structures", FeeStructureViewSet, basename="fee-structure")
router.register(r"invoices", FeeInvoiceViewSet, basename="invoice")
router.register(r"payments", PaymentViewSet, basename="payment")
router.register(r"", PaymentPlanViewSet, basename="payment-plan")
router.register(r"bursaries", BursaryViewSet, basename="bursary")
router.register(r"transactions", FinancialTransactionViewSet, basename="transaction")

urlpatterns = [
    path("", include(router.urls)),
    path("dashboard/", FinanceDashboardView.as_view(), name="finance-dashboard"),
    path("statistics/", FinanceStatisticsView.as_view(), name="finance-statistics"),
    path("student-finance/", StudentFinanceView.as_view(), name="student-finance"),
    path("reports/", FinanceReportView.as_view(), name="finance-reports"),
    path("mpesa-callback/", MpesaCallbackView.as_view(), name="mpesa-callback"),
]