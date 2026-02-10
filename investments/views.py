from django.shortcuts import render

# Create your views here.
from rest_framework import generics, views, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.db import transaction
from django.utils import timezone
from django.shortcuts import get_object_or_404
from decimal import Decimal
import logging

from authentication.permissions import IsProfileCompleted, CanMakeDeposits
from .models import (
    InvestmentPlan, PlanFAQ, PlanPerformance,
    UserInvestment, ProfitWithdrawal, InvestmentAlert
)
from .serializers import (
    InvestmentPlanSerializer, PlanFAQSerializer,
    PlanPerformanceSerializer, UserInvestmentSerializer,
    CreateInvestmentSerializer, ProfitWithdrawalSerializer,
    RequestWithdrawalSerializer, InvestmentAlertSerializer,
    InvestmentOverviewSerializer
)
from .permissions import CanInvest, IsOwnerOrAdmin, AdminOnly, CanManagePlans

logger = logging.getLogger(__name__)


class InvestmentPlansListView(generics.ListAPIView):
    """
    Get all active investment plans
    """
    permission_classes = [AllowAny]  # Allow anyone to view plans
    serializer_class = InvestmentPlanSerializer
    
    def get_queryset(self):
        queryset = InvestmentPlan.objects.filter(is_active=True)
        
        # Filter by plan type if provided
        plan_type = self.request.query_params.get('type', None)
        if plan_type:
            queryset = queryset.filter(plan_type=plan_type)
        
        # Filter by category if provided
        category = self.request.query_params.get('category', None)
        if category:
            queryset = queryset.filter(category=category)
        
        # Filter by min/max amount if provided
        min_amount = self.request.query_params.get('min_amount', None)
        if min_amount:
            queryset = queryset.filter(min_amount__gte=min_amount)
        
        max_amount = self.request.query_params.get('max_amount', None)
        if max_amount:
            queryset = queryset.filter(
                max_amount__lte=max_amount
            ) | queryset.filter(max_amount__isnull=True)
        
        # Order by display order
        return queryset.order_by('display_order', 'min_amount')


class InvestmentPlanDetailView(generics.RetrieveAPIView):
    """
    Get detailed information about a specific investment plan
    """
    permission_classes = [AllowAny]
    serializer_class = InvestmentPlanSerializer
    queryset = InvestmentPlan.objects.filter(is_active=True)
    lookup_field = 'id'


class PlanFAQsView(generics.ListAPIView):
    """
    Get FAQs for a specific investment plan
    """
    permission_classes = [AllowAny]
    serializer_class = PlanFAQSerializer
    
    def get_queryset(self):
        plan_id = self.kwargs.get('plan_id')
        return PlanFAQ.objects.filter(
            plan_id=plan_id
        ).order_by('display_order')


class PlanPerformanceView(generics.ListAPIView):
    """
    Get performance history for a specific investment plan
    """
    permission_classes = [AllowAny]
    serializer_class = PlanPerformanceSerializer
    
    def get_queryset(self):
        plan_id = self.kwargs.get('plan_id')
        return PlanPerformance.objects.filter(
            plan_id=plan_id
        ).order_by('-period_start')


class StartInvestmentView(APIView):
    """
    Start a new investment in a plan
    """
    permission_classes = [IsAuthenticated, CanInvest]
    
    def post(self, request):
        serializer = CreateInvestmentSerializer(
            data=request.data,
            context={'request': request}
        )
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        plan = serializer.validated_data['plan']
        amount = serializer.validated_data['amount']
        duration_days = serializer.validated_data.get('duration_days', plan.min_duration_days)
        
        try:
            with transaction.atomic():
                # Check if user has wallet with sufficient balance
                # This assumes wallet app is installed
                try:
                    from wallet.models import Wallet
                    wallet = Wallet.objects.get(user=request.user)
                    
                    if wallet.balance_usd < amount:
                        return Response(
                            {'error': 'Insufficient wallet balance'},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                    
                    # Deduct from wallet
                    wallet.debit(amount, transaction_type='INVESTMENT')
                    
                    # Record wallet transaction
                    from wallet.models import Transaction
                    Transaction.objects.create(
                        wallet=wallet,
                        transaction_type='INVESTMENT',
                        amount=amount,
                        status='COMPLETED',
                        description=f"Investment in {plan.name} plan",
                        metadata={
                            'plan_id': plan.id,
                            'plan_name': plan.name,
                            'duration_days': duration_days
                        }
                    )
                    
                except ImportError:
                    # Wallet app not installed, skip wallet operations
                    logger.warning("Wallet app not installed, skipping wallet operations")
                
                # Calculate expected return (use average of min and max)
                avg_multiplier = (plan.min_return_multiplier + plan.max_return_multiplier) / 2
                expected_total = amount + (amount * (avg_multiplier / Decimal('100')))
                
                # Calculate dates
                start_date = timezone.now()
                end_date = start_date + timezone.timedelta(days=duration_days)
                
                # Create investment
                investment = UserInvestment.objects.create(
                    user=request.user,
                    plan=plan,
                    principal_amount=amount,
                    expected_return_multiplier=avg_multiplier,
                    expected_total=expected_total,
                    current_value=amount,
                    start_date=start_date,
                    end_date=end_date if not plan.is_flexible_duration else None,
                    status=UserInvestment.InvestmentStatus.ACTIVE,
                    metadata={
                        'duration_days': duration_days,
                        'plan_type': plan.plan_type,
                        'category': plan.category
                    }
                )
                
                # Update plan statistics
                plan.total_investors = plan.user_investments.filter(
                    status__in=['ACTIVE', 'PENDING', 'COMPLETED']
                ).count()
                plan.total_invested += amount
                plan.save()
                
                # Send notification (would be handled by notification app)
                logger.info(f"Investment created: {investment.investment_id}")
                
                serializer = UserInvestmentSerializer(investment)
                return Response(serializer.data, status=status.HTTP_201_CREATED)
                
        except Exception as e:
            logger.error(f"Error creating investment: {str(e)}")
            return Response(
                {'error': 'Failed to create investment'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class UserInvestmentsView(generics.ListAPIView):
    """
    Get user's investments
    """
    permission_classes = [IsAuthenticated, IsProfileCompleted]
    serializer_class = UserInvestmentSerializer
    
    def get_queryset(self):
        # Update investment values before returning
        investments = UserInvestment.objects.filter(user=self.request.user)
        
        for investment in investments:
            if investment.status == investment.InvestmentStatus.ACTIVE:
                investment.update_current_value()
        
        return investments.order_by('-created_at')


class InvestmentDetailView(generics.RetrieveAPIView):
    """
    Get detailed information about a specific investment
    """
    permission_classes = [IsAuthenticated, IsProfileCompleted, IsOwnerOrAdmin]
    serializer_class = UserInvestmentSerializer
    lookup_field = 'investment_id'
    
    def get_queryset(self):
        if self.request.user.role == 'ADMIN':
            return UserInvestment.objects.all()
        return UserInvestment.objects.filter(user=self.request.user)


class RequestWithdrawalView(APIView):
    """
    Request withdrawal from an investment
    """
    permission_classes = [IsAuthenticated, IsProfileCompleted]
    
    def post(self, request):
        serializer = RequestWithdrawalSerializer(
            data=request.data,
            context={'request': request}
        )
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        investment = serializer.validated_data['investment']
        amount = serializer.validated_data['amount']
        payment_method = serializer.validated_data['payment_method']
        payment_details = serializer.validated_data.get('payment_details', {})
        
        try:
            with transaction.atomic():
                # Check if withdrawal is allowed
                if not investment.plan.is_flexible_duration:
                    return Response(
                        {'error': 'This plan does not allow flexible withdrawals'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Request withdrawal
                success, result = investment.request_withdrawal(amount)
                
                if not success:
                    return Response(
                        {'error': result},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Create withdrawal record
                withdrawal = ProfitWithdrawal.objects.create(
                    user=request.user,
                    investment=investment,
                    amount=amount,
                    fee=result['fee'],
                    net_amount=result['net_amount'],
                    payment_method=payment_method,
                    payment_details=payment_details,
                    status=ProfitWithdrawal.WithdrawalStatus.PENDING
                )
                
                # Update investment
                investment.total_withdrawn += amount
                investment.save()
                
                serializer = ProfitWithdrawalSerializer(withdrawal)
                return Response(serializer.data, status=status.HTTP_201_CREATED)
                
        except Exception as e:
            logger.error(f"Error requesting withdrawal: {str(e)}")
            return Response(
                {'error': 'Failed to process withdrawal request'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class InvestmentOverviewView(APIView):
    """
    Get investment overview for user dashboard
    """
    permission_classes = [IsAuthenticated, IsProfileCompleted]
    
    def get(self, request):
        try:
            # Get user's investments
            investments = UserInvestment.objects.filter(user=request.user)
            
            # Calculate totals
            total_invested = sum(
                inv.principal_amount for inv in investments
            )
            
            total_profits = sum(
                inv.total_profit for inv in investments
            )
            
            active_investments = investments.filter(
                status=UserInvestment.InvestmentStatus.ACTIVE
            ).count()
            
            completed_investments = investments.filter(
                status=UserInvestment.InvestmentStatus.COMPLETED
            ).count()
            
            # Calculate pending withdrawals
            pending_withdrawals = ProfitWithdrawal.objects.filter(
                user=request.user,
                status__in=['PENDING', 'PROCESSING']
            ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')
            
            # Estimate monthly income from active investments
            estimated_monthly_income = Decimal('0.00')
            for inv in investments.filter(status='ACTIVE'):
                daily_rate = inv.plan.calculate_daily_return_rate()
                estimated_monthly_income += inv.current_value * daily_rate * Decimal('30')
            
            # Calculate portfolio distribution
            portfolio_distribution = {}
            for inv in investments.filter(status='ACTIVE'):
                plan_type = inv.plan.plan_type
                if plan_type not in portfolio_distribution:
                    portfolio_distribution[plan_type] = {
                        'amount': Decimal('0.00'),
                        'percentage': Decimal('0.00')
                    }
                portfolio_distribution[plan_type]['amount'] += inv.current_value
            
            # Calculate percentages
            total_active = sum(dist['amount'] for dist in portfolio_distribution.values())
            if total_active > 0:
                for dist in portfolio_distribution.values():
                    dist['percentage'] = (dist['amount'] / total_active) * Decimal('100')
            
            overview_data = {
                'total_invested': total_invested,
                'total_profits': total_profits,
                'active_investments': active_investments,
                'completed_investments': completed_investments,
                'pending_withdrawals': pending_withdrawals,
                'estimated_monthly_income': estimated_monthly_income,
                'portfolio_distribution': portfolio_distribution
            }
            
            serializer = InvestmentOverviewSerializer(overview_data)
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error getting investment overview: {str(e)}")
            return Response(
                {'error': 'Failed to get investment overview'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class InvestmentAlertsView(generics.ListAPIView):
    """
    Get investment alerts for user
    """
    permission_classes = [IsAuthenticated, IsProfileCompleted]
    serializer_class = InvestmentAlertSerializer
    
    def get_queryset(self):
        now = timezone.now()
        
        # Get alerts for all users or specific to user
        alerts = InvestmentAlert.objects.filter(
            is_active=True,
            valid_from__lte=now,
        ).filter(
            models.Q(valid_until__isnull=True) | models.Q(valid_until__gte=now)
        ).filter(
            models.Q(is_for_all_users=True) |
            models.Q(target_users=self.request.user) |
            models.Q(target_plans__user_investments__user=self.request.user)
        ).distinct()
        
        return alerts.order_by('-priority', '-created_at')


# Admin Views

class AdminPlanListView(generics.ListCreateAPIView):
    """
    Admin: List and create investment plans
    """
    permission_classes = [IsAuthenticated, AdminOnly]
    serializer_class = InvestmentPlanSerializer
    queryset = InvestmentPlan.objects.all().order_by('display_order')


class AdminPlanDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Admin: Retrieve, update, or delete investment plan
    """
    permission_classes = [IsAuthenticated, AdminOnly]
    serializer_class = InvestmentPlanSerializer
    queryset = InvestmentPlan.objects.all()
    lookup_field = 'id'


class AdminInvestmentListView(generics.ListAPIView):
    """
    Admin: List all investments
    """
    permission_classes = [IsAuthenticated, AdminOnly]
    serializer_class = UserInvestmentSerializer
    queryset = UserInvestment.objects.all().order_by('-created_at')
    
    def get_queryset(self):
        queryset = UserInvestment.objects.all()
        
        # Filter by status
        status_filter = self.request.query_params.get('status', None)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filter by plan
        plan_id = self.request.query_params.get('plan_id', None)
        if plan_id:
            queryset = queryset.filter(plan_id=plan_id)
        
        # Filter by user
        user_email = self.request.query_params.get('user_email', None)
        if user_email:
            queryset = queryset.filter(user__email__icontains=user_email)
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date', None)
        end_date = self.request.query_params.get('end_date', None)
        
        if start_date:
            queryset = queryset.filter(created_at__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__date__lte=end_date)
        
        return queryset.order_by('-created_at')


class AdminWithdrawalListView(generics.ListAPIView):
    """
    Admin: List all withdrawal requests
    """
    permission_classes = [IsAuthenticated, AdminOnly]
    serializer_class = ProfitWithdrawalSerializer
    queryset = ProfitWithdrawal.objects.all().order_by('-created_at')
    
    def get_queryset(self):
        queryset = ProfitWithdrawal.objects.all()
        
        # Filter by status
        status_filter = self.request.query_params.get('status', None)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filter by user
        user_email = self.request.query_params.get('user_email', None)
        if user_email:
            queryset = queryset.filter(user__email__icontains=user_email)
        
        return queryset.order_by('-created_at')


class AdminProcessWithdrawalView(APIView):
    """
    Admin: Process a withdrawal request
    """
    permission_classes = [IsAuthenticated, AdminOnly]
    
    def post(self, request, withdrawal_id):
        try:
            withdrawal = get_object_or_404(ProfitWithdrawal, withdrawal_id=withdrawal_id)
            
            action = request.data.get('action')  # 'approve', 'reject', 'cancel'
            admin_notes = request.data.get('admin_notes', '')
            
            if action == 'approve':
                withdrawal.status = ProfitWithdrawal.WithdrawalStatus.COMPLETED
                withdrawal.processed_at = timezone.now()
                withdrawal.admin_notes = admin_notes
                withdrawal.save()
                
                # Credit to user's wallet
                try:
                    from wallet.models import Wallet
                    wallet = Wallet.objects.get(user=withdrawal.user)
                    wallet.credit(withdrawal.net_amount, transaction_type='WITHDRAWAL')
                    
                    # Record transaction
                    from wallet.models import Transaction
                    Transaction.objects.create(
                        wallet=wallet,
                        transaction_type='WITHDRAWAL',
                        amount=withdrawal.net_amount,
                        status='COMPLETED',
                        description=f"Profit withdrawal from investment",
                        reference=str(withdrawal.withdrawal_id)
                    )
                    
                except ImportError:
                    logger.warning("Wallet app not installed, skipping wallet operations")
                
                message = 'Withdrawal approved and processed'
                
            elif action == 'reject':
                withdrawal.status = ProfitWithdrawal.WithdrawalStatus.DENIED
                withdrawal.admin_notes = admin_notes
                withdrawal.save()
                
                # Return amount to investment
                if withdrawal.investment:
                    withdrawal.investment.total_withdrawn -= withdrawal.amount
                    withdrawal.investment.save()
                
                message = 'Withdrawal rejected'
                
            elif action == 'cancel':
                withdrawal.status = ProfitWithdrawal.WithdrawalStatus.CANCELLED
                withdrawal.admin_notes = admin_notes
                withdrawal.save()
                message = 'Withdrawal cancelled'
                
            else:
                return Response(
                    {'error': 'Invalid action'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            serializer = ProfitWithdrawalSerializer(withdrawal)
            return Response({
                'message': message,
                'withdrawal': serializer.data
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error processing withdrawal: {str(e)}")
            return Response(
                {'error': 'Failed to process withdrawal'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AdminCreateAlertView(generics.CreateAPIView):
    """
    Admin: Create investment alert
    """
    permission_classes = [IsAuthenticated, AdminOnly]
    serializer_class = InvestmentAlertSerializer


class AdminPerformanceReportView(APIView):
    """
    Admin: Get performance report
    """
    permission_classes = [IsAuthenticated, AdminOnly]
    
    def get(self, request):
        try:
            # Get date range from query params
            start_date = request.query_params.get('start_date')
            end_date = request.query_params.get('end_date') or timezone.now().date()
            
            # Calculate overall statistics
            total_investments = UserInvestment.objects.count()
            active_investments = UserInvestment.objects.filter(
                status='ACTIVE'
            ).count()
            completed_investments = UserInvestment.objects.filter(
                status='COMPLETED'
            ).count()
            
            total_invested = UserInvestment.objects.aggregate(
                total=models.Sum('principal_amount')
            )['total'] or Decimal('0.00')
            
            total_profits = UserInvestment.objects.aggregate(
                total=models.Sum('total_profit')
            )['total'] or Decimal('0.00')
            
            total_withdrawals = ProfitWithdrawal.objects.filter(
                status='COMPLETED'
            ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')
            
            # Plan-wise distribution
            plan_stats = {}
            for plan in InvestmentPlan.objects.all():
                plan_investments = plan.user_investments.all()
                plan_stats[plan.name] = {
                    'total_investments': plan_investments.count(),
                    'total_invested': sum(inv.principal_amount for inv in plan_investments),
                    'total_profits': sum(inv.total_profit for inv in plan_investments),
                    'active_investments': plan_investments.filter(status='ACTIVE').count(),
                    'success_rate': plan.success_rate
                }
            
            # Monthly growth
            monthly_growth = []
            for i in range(6):  # Last 6 months
                month = timezone.now() - timezone.timedelta(days=30*i)
                month_start = month.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                month_end = (month_start + timezone.timedelta(days=32)).replace(day=1) - timezone.timedelta(days=1)
                
                month_investments = UserInvestment.objects.filter(
                    created_at__range=[month_start, month_end]
                )
                
                monthly_growth.append({
                    'month': month_start.strftime('%Y-%m'),
                    'new_investments': month_investments.count(),
                    'total_invested': sum(inv.principal_amount for inv in month_investments),
                    'total_profits': sum(inv.total_profit for inv in month_investments)
                })
            
            report = {
                'overall': {
                    'total_investments': total_investments,
                    'active_investments': active_investments,
                    'completed_investments': completed_investments,
                    'total_invested': total_invested,
                    'total_profits': total_profits,
                    'total_withdrawals': total_withdrawals,
                    'net_profit': total_profits - total_withdrawals
                },
                'plan_statistics': plan_stats,
                'monthly_growth': monthly_growth,
                'top_performing_plans': sorted(
                    plan_stats.items(),
                    key=lambda x: x[1]['total_profits'],
                    reverse=True
                )[:5]
            }
            
            return Response(report, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error generating performance report: {str(e)}")
            return Response(
                {'error': 'Failed to generate report'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )