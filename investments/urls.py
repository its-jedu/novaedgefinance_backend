from django.urls import path
from . import views

urlpatterns = [
    # Public Endpoints (Anyone can view plans)
    path('plans/', views.InvestmentPlansListView.as_view(), name='investment-plans'),
    path('plans/<int:id>/', views.InvestmentPlanDetailView.as_view(), name='plan-detail'),
    path('plans/<int:plan_id>/faqs/', views.PlanFAQsView.as_view(), name='plan-faqs'),
    path('plans/<int:plan_id>/performance/', views.PlanPerformanceView.as_view(), name='plan-performance'),
    
    # User Investment Endpoints
    path('invest/start/', views.StartInvestmentView.as_view(), name='start-investment'),
    path('my-investments/', views.UserInvestmentsView.as_view(), name='my-investments'),
    path('investments/<uuid:investment_id>/', views.InvestmentDetailView.as_view(), name='investment-detail'),
    path('withdraw/request/', views.RequestWithdrawalView.as_view(), name='request-withdrawal'),
    path('overview/', views.InvestmentOverviewView.as_view(), name='investment-overview'),
    path('alerts/', views.InvestmentAlertsView.as_view(), name='investment-alerts'),
    
    # Admin Endpoints
    path('admin/plans/', views.AdminPlanListView.as_view(), name='admin-plans'),
    path('admin/plans/<int:id>/', views.AdminPlanDetailView.as_view(), name='admin-plan-detail'),
    path('admin/investments/', views.AdminInvestmentListView.as_view(), name='admin-investments'),
    path('admin/withdrawals/', views.AdminWithdrawalListView.as_view(), name='admin-withdrawals'),
    path('admin/withdrawals/<uuid:withdrawal_id>/process/', views.AdminProcessWithdrawalView.as_view(), name='process-withdrawal'),
    path('admin/alerts/create/', views.AdminCreateAlertView.as_view(), name='admin-create-alert'),
    path('admin/performance-report/', views.AdminPerformanceReportView.as_view(), name='performance-report'),
]