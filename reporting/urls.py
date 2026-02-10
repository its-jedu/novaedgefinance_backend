from django.urls import path
from . import views

urlpatterns = [
    # User Reporting Endpoints
    path('transactions/my/', views.MyTransactionHistoryView.as_view(), name='my-transactions'),
    path('transactions/export/', views.ExportMyTransactionsView.as_view(), name='export-transactions'),
    
    # Admin Reporting Endpoints
    path('admin/summary/', views.FinancialSummaryView.as_view(), name='financial-summary'),
    path('admin/daily-summary/', views.DailySummaryView.as_view(), name='daily-summary'),
    path('admin/reports/create/', views.CreateReportView.as_view(), name='create-report'),
    path('admin/reports/', views.ReportListView.as_view(), name='reports'),
    path('admin/reports/<uuid:report_id>/', views.ReportDetailView.as_view(), name='report-detail'),
    path('admin/reports/<uuid:report_id>/download/', views.DownloadReportView.as_view(), name='download-report'),
    path('admin/ledger/', views.AdminLedgerListView.as_view(), name='ledger'),
    path('admin/ledger/<uuid:ledger_id>/verify/', views.AdminVerifyLedgerEntryView.as_view(), name='verify-ledger'),
    path('admin/audit-logs/', views.AdminAuditLogListView.as_view(), name='audit-logs'),
    path('admin/user-activities/', views.AdminUserActivityListView.as_view(), name='user-activities'),
    path('admin/system-health/', views.AdminSystemHealthView.as_view(), name='system-health'),
    path('admin/health-history/', views.AdminHealthHistoryView.as_view(), name='health-history'),
    path('admin/dashboard-stats/', views.AdminDashboardStatsView.as_view(), name='dashboard-stats'),
]