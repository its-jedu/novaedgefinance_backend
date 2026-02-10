from django.urls import path
from . import views

urlpatterns = [
    # User Referral Endpoints
    path('my-code/', views.MyReferralCodeView.as_view(), name='my-referral-code'),
    path('create-custom/', views.CreateCustomCodeView.as_view(), name='create-custom-code'),
    path('my-referrals/', views.MyReferralsView.as_view(), name='my-referrals'),
    path('stats/', views.ReferralStatsView.as_view(), name='referral-stats'),
    path('bonus-wallet/', views.MyBonusWalletView.as_view(), name='bonus-wallet'),
    path('withdraw-bonus/', views.WithdrawBonusView.as_view(), name='withdraw-bonus'),
    path('referral-link/', views.ReferralLinkView.as_view(), name='referral-link'),
    
    # Admin Referral Endpoints
    path('admin/referrals/', views.AdminReferralListView.as_view(), name='admin-referrals'),
    path('admin/bonus-wallets/', views.AdminBonusWalletListView.as_view(), name='admin-bonus-wallets'),
    path('admin/stats/', views.AdminReferralStatsView.as_view(), name='admin-referral-stats'),
    path('admin/settings/', views.AdminReferralSettingsView.as_view(), name='referral-settings'),
    path('admin/manual-bonus/', views.AdminManualBonusView.as_view(), name='manual-bonus'),
]