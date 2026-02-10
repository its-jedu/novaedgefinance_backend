from django.urls import path
from . import views

urlpatterns = [
    # User Wallet Endpoints
    path('overview/', views.WalletOverviewView.as_view(), name='wallet-overview'),
    path('deposits/create/', views.CreateDepositView.as_view(), name='create-deposit'),
    path('transactions/my/', views.UserTransactionsView.as_view(), name='my-transactions'),
    path('deposits/my/', views.UserDepositsView.as_view(), name='my-deposits'),
    
    # NOWPayments Webhook
    path('nowpayments-webhook/', views.NOWPaymentsWebhookView.as_view(), name='nowpayments-webhook'),
    
    # Admin Endpoints
    path('admin/wallets/', views.AdminWalletListView.as_view(), name='admin-wallets'),
    path('admin/transactions/', views.AdminTransactionListView.as_view(), name='admin-transactions'),
    path('admin/deposits/', views.AdminDepositListView.as_view(), name='admin-deposits'),
    path('admin/deposits/<uuid:deposit_id>/', views.AdminDepositDetailView.as_view(), name='admin-deposit-detail'),
]