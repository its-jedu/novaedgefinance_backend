from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from . import views

urlpatterns = [
    # Authentication endpoints
    path('register/', views.UserRegistrationView.as_view(), name='register'),
    path('verify-email/', views.EmailVerificationView.as_view(), name='verify-email'),
    path('login/', views.UserLoginView.as_view(), name='login'),
    path('logout/', views.LogoutView.as_view(), name='logout'),
    path('resend-verification/', views.ResendVerificationView.as_view(), name='resend-verification'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # Password management
    path('password-reset/', views.PasswordResetView.as_view(), name='password-reset'),
    path('password-reset/confirm/', views.PasswordResetConfirmView.as_view(), name='password-reset-confirm'),
    path('change-password/', views.ChangePasswordView.as_view(), name='change-password'),
    
    # User profile and investment profile
    path('profile/', views.UserProfileView.as_view(), name='profile'),
    path('profile/status/', views.ProfileStatusView.as_view(), name='profile-status'),
    path('profile/investment/', views.InvestmentProfileView.as_view(), name='investment-profile'),
    path('profile/complete/', views.CompleteProfileView.as_view(), name='complete-profile'),
    
    # Admin endpoints
    path('admin/users/', views.AdminUserListView.as_view(), name='admin-users-list'),
    path('admin/users/<int:user_id>/', views.AdminUserDetailView.as_view(), name='admin-user-detail'),
    path('admin/users/<int:user_id>/toggle-status/', views.AdminToggleUserStatusView.as_view(), name='admin-toggle-status'),
    path('admin/users/<int:user_id>/reset-password/', views.AdminResetUserPasswordView.as_view(), name='admin-reset-password'),
    path('admin/users/<int:user_id>/change-role/', views.AdminChangeUserRoleView.as_view(), name='admin-change-role'),
    path('admin/users/<int:user_id>/investments/', views.AdminUserInvestmentsView.as_view(), name='admin-user-investments'),
    # Admin Dashboard (aggregated endpoint)
    path('admin/dashboard/', views.AdminDashboardView.as_view(), name='admin-dashboard'),
]