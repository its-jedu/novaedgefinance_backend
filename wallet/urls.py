from django.urls import path
from . import views

urlpatterns = [
    # User Wallet Endpoints
    path('overview/', views.WalletOverviewView.as_view(), name='wallet-overview'),
    path('deposits/create/', views.CreateDepositView.as_view(), name='create-deposit'),
    path('deposits/status/', views.DepositStatusView.as_view(), name='deposit-status'),
    path('plans/', views.InvestmentPlansView.as_view(), name='investment-plans'),
    path('investments/start/', views.StartInvestmentView.as_view(), name='start-investment'),
    path('investments/my/', views.UserInvestmentsView.as_view(), name='my-investments'),
    path('investments/<uuid:investment_id>/growth/', views.InvestmentGrowthView.as_view(), name='investment-growth'),
    path('transactions/my/', views.UserTransactionsView.as_view(), name='my-transactions'),
    path('deposits/my/', views.UserDepositsView.as_view(), name='my-deposits'),
    
    # NOWPayments Webhook
    path('nowpayments-webhook/', views.NOWPaymentsWebhookView.as_view(), name='nowpayments-webhook'),
    
    # Admin Endpoints
    path('admin/wallets/', views.AdminWalletListView.as_view(), name='admin-wallets'),
    path('admin/transactions/', views.AdminTransactionListView.as_view(), name='admin-transactions'),
    path('admin/deposits/', views.AdminDepositListView.as_view(), name='admin-deposits'),
    path('admin/investments/', views.AdminInvestmentListView.as_view(), name='admin-investments'),
    path('admin/plans/create/', views.AdminCreateInvestmentPlanView.as_view(), name='admin-create-plan'),
    path('admin/plans/<int:id>/update/', views.AdminUpdateInvestmentPlanView.as_view(), name='admin-update-plan'),
]

