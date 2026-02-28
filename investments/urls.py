from django.urls import path
from . import views

urlpatterns = [
    # ================= USER WALLET / INVESTMENT ENDPOINTS =================
    path('overview/', views.WalletOverviewView.as_view(), name='wallet-overview'),
    path('deposits/create/', views.CreateDepositView.as_view(), name='create-deposit'),
    path('transactions/my/', views.UserTransactionsView.as_view(), name='my-transactions'),
    path('deposits/my/', views.UserDepositsView.as_view(), name='my-deposits'),
    
    # NOWPayments Webhook
    path('nowpayments-webhook/', views.NOWPaymentsWebhookView.as_view(), name='nowpayments-webhook'),
    
    # ================= INVESTMENT PLANS =================
    path('plans/', views.InvestmentPlansListView.as_view(), name='investment-plans-list'),
    path('plans/<int:id>/', views.InvestmentPlanDetailView.as_view(), name='investment-plan-detail'),
    path('plans/<int:plan_id>/faqs/', views.PlanFAQsView.as_view(), name='plan-faqs'),
    path('plans/<int:plan_id>/performance/', views.PlanPerformanceView.as_view(), name='plan-performance'),
    
    # ================= USER INVESTMENTS =================
    path('investments/start/', views.StartInvestmentView.as_view(), name='start-investment'),
    path('investments/my/', views.UserInvestmentsView.as_view(), name='user-investments'),
    path('investments/<uuid:investment_id>/', views.InvestmentDetailView.as_view(), name='investment-detail'),
    path('investments/request-withdrawal/', views.RequestWithdrawalView.as_view(), name='request-withdrawal'),
    path('investments/overview/', views.InvestmentOverviewView.as_view(), name='investment-overview'),
    path('investments/alerts/', views.InvestmentAlertsView.as_view(), name='investment-alerts'),
    
    # ================= ADMIN PLANS =================
    path('admin/plans/', views.AdminPlanListView.as_view(), name='admin-plan-list'),
    path('admin/plans/<int:id>/', views.AdminPlanDetailView.as_view(), name='admin-plan-detail'),
    
    # ================= ADMIN INVESTMENTS & WITHDRAWALS =================
    path('admin/investments/', views.AdminInvestmentListView.as_view(), name='admin-investment-list'),
    path('admin/withdrawals/', views.AdminWithdrawalListView.as_view(), name='admin-withdrawal-list'),
    path('admin/withdrawals/<uuid:withdrawal_id>/process/', views.AdminProcessWithdrawalView.as_view(), name='admin-process-withdrawal'),
    
    # ================= ADMIN ALERTS =================
    path('admin/alerts/create/', views.AdminCreateAlertView.as_view(), name='admin-create-alert'),
    
    # ================= ADMIN REPORT =================
    path('admin/performance-report/', views.AdminPerformanceReportView.as_view(), name='admin-performance-report'),
]