from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .api.viewsets import (
    FeeStructureViewSet,
    FeeInvoiceViewSet,
    FinanceReportView,
    FinanceStatisticsView,
    MpesaCallbackView,
    PaymentViewSet,
    PaymentPlanViewSet,
    BursaryViewSet,
    FinancialTransactionViewSet,
    FinanceDashboardView,
    StudentFinanceView
    )
router = DefaultRouter()
router.register(r'fee-structures', FeeStructureViewSet, basename='feestructure')
router.register(r'invoices', FeeInvoiceViewSet, basename='invoice')
router.register(r'payments', PaymentViewSet, basename='payment')
router.register(r'payment-plans', PaymentPlanViewSet, basename='paymentplan')
router.register(r'bursaries', BursaryViewSet, basename='bursary')
router.register(r'transactions', FinancialTransactionViewSet, basename='transaction')

urlpatterns = [
    path('', include(router.urls)),
 
    path('dashboard/', FinanceDashboardView.as_view(), name='finance_dashboard'),
    path('statistics/', FinanceStatisticsView.as_view(), name='finance_statistics'),
    path('student_finance/', StudentFinanceView.as_view(), name='student_finance'),
    path('reports/', FinanceReportView.as_view(), name='finance_reports'),
    path('mpesa_callback/', MpesaCallbackView.as_view(), name='mpesa_callback'),
    path('fee_structures/for_class/', FeeStructureViewSet.as_view({'get': 'for_class'}), name='fee_for_class'),
    path('invoices/overdue/', FeeInvoiceViewSet.as_view({'get': 'overdue'}), name='overdue_invoices'),
    path('invoices/generate/', FeeInvoiceViewSet.as_view({'post': 'generate'}), name='generate_invoice'),
    path('payments/today/', PaymentViewSet.as_view({'get': 'today'}), name='today_payments'),
    path('bursaries/pending/', BursaryViewSet.as_view({'get': 'pending'}), name='pending_bursaries'),
]