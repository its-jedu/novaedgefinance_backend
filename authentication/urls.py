from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from . import views

urlpatterns = [
    # Authentication endpoints
    path('register/', views.UserRegistrationView.as_view(), name='register'),
    path('verify-phone/', views.PhoneVerificationView.as_view(), name='verify-phone'),
    path('login/', views.UserLoginView.as_view(), name='login'),
    path('logout/', views.LogoutView.as_view(), name='logout'),
    path('resend-verification/', views.ResendVerificationView.as_view(), name='resend-verification'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # User profile
    path('profile/', views.UserProfileView.as_view(), name='profile'),
    path('change-password/', views.ChangePasswordView.as_view(), name='change-password'),
    
    # Admin endpoints
    path('admin/users/', views.AdminUserListView.as_view(), name='admin-users-list'),
    path('admin/users/<int:pk>/', views.AdminUserDetailView.as_view(), name='admin-user-detail'),
    path('admin/users/<int:user_id>/suspend/', views.AdminSuspendUserView.as_view(), name='admin-suspend-user'),
    path('admin/users/<int:user_id>/activate/', views.AdminActivateUserView.as_view(), name='admin-activate-user'),
    path('admin/users/<int:user_id>/reset-password/', views.AdminResetUserPasswordView.as_view(), name='admin-reset-password'),
    path('admin/users/<int:user_id>/change-role/', views.AdminChangeUserRoleView.as_view(), name='admin-change-role'),
]