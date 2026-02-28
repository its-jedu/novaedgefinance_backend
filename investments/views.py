from django.shortcuts import render
from rest_framework import generics, views, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.db import transaction, models
from django.utils import timezone
from django.shortcuts import get_object_or_404
from decimal import Decimal
import logging

from authentication.permissions import IsProfileCompleted
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
from .permissions import CanInvest, IsOwnerOrAdmin, AdminOnly

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
                models.Q(max_amount__lte=max_amount) | models.Q(max_amount__isnull=True)
            )
        
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

class WalletOverviewView(APIView):
    def get(self, request):
        data = {
            "balance": 0,
            "investments": []
        }
        return Response(data)

class CreateDepositView(APIView):
    def post(self, request):
        # Replace with actual logic to create a deposit
        data = {
            "message": "Deposit created successfully",
            "deposit": request.data
        }
        return Response(data, status=status.HTTP_201_CREATED)

class UserTransactionsView(APIView):
    def get(self, request):
        # Example response; replace with real logic
        data = {
            "transactions": [
                {"id": 1, "amount": 1000, "status": "completed"},
                {"id": 2, "amount": 500, "status": "pending"},
            ]
        }
        return Response(data, status=status.HTTP_200_OK)

class UserDepositsView(APIView):
    def get(self, request):
        # Example data; replace with your actual query to get user deposits
        deposits = [
            {"id": 1, "amount": 1000, "status": "completed"},
            {"id": 2, "amount": 500, "status": "pending"},
        ]
        return Response({"deposits": deposits}, status=status.HTTP_200_OK)

class NOWPaymentsWebhookView(APIView):
    def post(self, request, *args, **kwargs):
        # TODO: verify webhook signature here
        data = request.data
        # Example: just echo back the data for now
        return Response({"received": data}, status=status.HTTP_200_OK)

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
    Start a new investment in a plan with comprehensive validation
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
        
        # ============ VALIDATION LAYER ============
        # 1. Check if user is active
        if not request.user.is_active:
            return Response(
                {'error': 'Your account is suspended. Please contact support.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # 2. Check if user is under review
        if getattr(request.user, 'is_under_review', False):
            return Response(
                {'error': 'Your account is under review. Please contact support.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # 3. Check if plan is active
        if not plan.is_active:
            return Response(
                {'error': 'This investment plan is currently inactive.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 4. Check daily investment limit
        can_invest, limit_message = request.user.check_daily_investment_limit(amount)
        if not can_invest:
            return Response(
                {'error': limit_message},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 5. Check minimum amount
        if amount < plan.min_amount:
            return Response(
                {'error': f'Minimum investment amount is ${plan.min_amount}.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 6. Check maximum amount
        if plan.max_amount and amount > plan.max_amount:
            return Response(
                {'error': f'Maximum investment amount is ${plan.max_amount}.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Use atomic transaction for investment creation
            investment = UserInvestment.create_investment(
                user=request.user,
                plan=plan,
                amount=amount,
                duration_days=duration_days,
                request=request
            )
            
            # Update daily investment total
            request.user.daily_investment_total += amount
            request.user.last_investment_date = timezone.now().date()
            request.user.save()
            
            # Send notifications
            self.send_investment_notifications(investment)
            
            serializer = UserInvestmentSerializer(investment)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
            
        except ValueError as e:
            logger.warning(f"Investment validation failed: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error creating investment: {str(e)}")
            return Response(
                {'error': 'Failed to create investment'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def send_investment_notifications(self, investment):
        """Send notifications about new investment"""
        try:
            from notifications.utils import create_notification
            
            # Notify user
            create_notification(
                user=investment.user,
                notification_type='INVESTMENT_STARTED',
                title='Investment Started Successfully',
                message=f'Your investment of ${investment.principal_amount} in {investment.plan.name} has been started.',
                metadata={
                    'investment_id': str(investment.investment_id),
                    'plan_name': investment.plan.name,
                    'amount': str(investment.principal_amount)
                }
            )
            
            # Notify admins
            from django.contrib.auth import get_user_model
            User = get_user_model()
            admins = User.objects.filter(role='ADMIN', is_active=True)
            
            for admin in admins:
                create_notification(
                    user=admin,
                    notification_type='ADMIN_ACTION',
                    title='New Investment Created',
                    message=f'{investment.user.email} invested ${investment.principal_amount} in {investment.plan.name}',
                    metadata={
                        'user_email': investment.user.email,
                        'investment_id': str(investment.investment_id),
                        'amount': str(investment.principal_amount)
                    }
                )
                
        except ImportError:
            logger.warning("Notifications app not installed")
        except Exception as e:
            logger.error(f"Failed to send investment notifications: {str(e)}")


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
                
                # Check if investment is active
                if investment.status != investment.InvestmentStatus.ACTIVE:
                    return Response(
                        {'error': 'Cannot withdraw from inactive investment'},
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
                
                # Send notification
                self.send_withdrawal_notification(investment, withdrawal)
                
                serializer = ProfitWithdrawalSerializer(withdrawal)
                return Response(serializer.data, status=status.HTTP_201_CREATED)
                
        except Exception as e:
            logger.error(f"Error requesting withdrawal: {str(e)}")
            return Response(
                {'error': 'Failed to process withdrawal request'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def send_withdrawal_notification(self, investment, withdrawal):
        """Send withdrawal request notification"""
        try:
            from notifications.utils import create_notification
            
            # Notify user
            create_notification(
                user=investment.user,
                notification_type='WITHDRAWAL_REQUESTED',
                title='Withdrawal Request Submitted',
                message=f'Your withdrawal request of ${withdrawal.amount} has been submitted for processing.',
                metadata={
                    'investment_id': str(investment.investment_id),
                    'withdrawal_id': str(withdrawal.withdrawal_id),
                    'amount': str(withdrawal.amount),
                    'net_amount': str(withdrawal.net_amount)
                }
            )
            
        except ImportError:
            logger.warning("Notifications app not installed")


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
            ) or Decimal('0.00')
            
            total_profits = sum(
                inv.total_profit for inv in investments
            ) or Decimal('0.00')
            
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
                    dist['percentage'] = round(dist['percentage'], 2)
            
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


# ============ ADMIN VIEWS ============

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
    Admin: List all investments with advanced filtering
    """
    permission_classes = [IsAuthenticated, AdminOnly]
    serializer_class = UserInvestmentSerializer
    
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
        
        # Filter by amount range
        min_amount = self.request.query_params.get('min_amount', None)
        max_amount = self.request.query_params.get('max_amount', None)
        
        if min_amount:
            queryset = queryset.filter(principal_amount__gte=min_amount)
        if max_amount:
            queryset = queryset.filter(principal_amount__lte=max_amount)
        
        return queryset.select_related('user', 'plan').order_by('-created_at')


class AdminWithdrawalListView(generics.ListAPIView):
    """
    Admin: List all withdrawal requests
    """
    permission_classes = [IsAuthenticated, AdminOnly]
    serializer_class = ProfitWithdrawalSerializer
    
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
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date', None)
        end_date = self.request.query_params.get('end_date', None)
        
        if start_date:
            queryset = queryset.filter(created_at__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__date__lte=end_date)
        
        return queryset.select_related('user', 'investment').order_by('-created_at')


class AdminProcessWithdrawalView(APIView):
    """
    Admin: Process a withdrawal request with atomic transaction
    """
    permission_classes = [IsAuthenticated, AdminOnly]
    
    def post(self, request, withdrawal_id):
        try:
            withdrawal = get_object_or_404(
                ProfitWithdrawal.objects.select_related('user', 'investment'),
                withdrawal_id=withdrawal_id
            )
            
            action = request.data.get('action')  # 'approve', 'reject', 'cancel'
            admin_notes = request.data.get('admin_notes', '')
            
            with transaction.atomic():
                if action == 'approve':
                    # Check if already processed
                    if withdrawal.status != ProfitWithdrawal.WithdrawalStatus.PENDING:
                        return Response(
                            {'error': f'Withdrawal already {withdrawal.status.lower()}'},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                    
                    withdrawal.status = ProfitWithdrawal.WithdrawalStatus.COMPLETED
                    withdrawal.processed_at = timezone.now()
                    withdrawal.admin_notes = admin_notes
                    withdrawal.save()
                    
                    # Credit to user's wallet
                    try:
                        from wallet.models import Wallet
                        wallet = Wallet.objects.select_for_update().get(user=withdrawal.user)
                        wallet.credit(
                            amount=withdrawal.net_amount,
                            transaction_type='WITHDRAWAL',
                            reference=str(withdrawal.withdrawal_id),
                            description=f"Profit withdrawal from investment",
                            metadata={
                                'withdrawal_id': str(withdrawal.withdrawal_id),
                                'investment_id': str(withdrawal.investment.investment_id) if withdrawal.investment else None,
                                'gross_amount': str(withdrawal.amount),
                                'fee': str(withdrawal.fee)
                            },
                            request=request
                        )
                        
                    except ImportError:
                        logger.warning("Wallet app not installed, skipping wallet operations")
                    except Wallet.DoesNotExist:
                        logger.error(f"Wallet not found for user {withdrawal.user.email}")
                    
                    message = 'Withdrawal approved and processed'
                    
                    # Send notification
                    self.send_withdrawal_notification(withdrawal, 'approved')
                    
                elif action == 'reject':
                    withdrawal.status = ProfitWithdrawal.WithdrawalStatus.DENIED
                    withdrawal.admin_notes = admin_notes
                    withdrawal.save()
                    
                    # Return amount to investment
                    if withdrawal.investment:
                        withdrawal.investment.total_withdrawn -= withdrawal.amount
                        withdrawal.investment.save()
                    
                    message = 'Withdrawal rejected'
                    
                    # Send notification
                    self.send_withdrawal_notification(withdrawal, 'rejected')
                    
                elif action == 'cancel':
                    withdrawal.status = ProfitWithdrawal.WithdrawalStatus.CANCELLED
                    withdrawal.admin_notes = admin_notes
                    withdrawal.save()
                    
                    # Return amount to investment
                    if withdrawal.investment:
                        withdrawal.investment.total_withdrawn -= withdrawal.amount
                        withdrawal.investment.save()
                    
                    message = 'Withdrawal cancelled'
                    
                    # Send notification
                    self.send_withdrawal_notification(withdrawal, 'cancelled')
                    
                else:
                    return Response(
                        {'error': 'Invalid action. Must be approve, reject, or cancel'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Log admin action
                self.log_admin_action(request.user, withdrawal, action, admin_notes)
                
                serializer = ProfitWithdrawalSerializer(withdrawal)
                return Response({
                    'message': message,
                    'withdrawal': serializer.data
                }, status=status.HTTP_200_OK)
            
        except ProfitWithdrawal.DoesNotExist:
            return Response(
                {'error': 'Withdrawal not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error processing withdrawal: {str(e)}")
            return Response(
                {'error': 'Failed to process withdrawal'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def send_withdrawal_notification(self, withdrawal, status):
        """Send withdrawal status notification"""
        try:
            from notifications.utils import create_notification
            
            status_messages = {
                'approved': 'Your withdrawal request has been approved and processed.',
                'rejected': 'Your withdrawal request has been rejected.',
                'cancelled': 'Your withdrawal request has been cancelled.'
            }
            
            status_titles = {
                'approved': 'Withdrawal Approved',
                'rejected': 'Withdrawal Rejected',
                'cancelled': 'Withdrawal Cancelled'
            }
            
            create_notification(
                user=withdrawal.user,
                notification_type='WITHDRAWAL_COMPLETED' if status == 'approved' else 'WITHDRAWAL_REQUESTED',
                title=status_titles.get(status, 'Withdrawal Status Update'),
                message=status_messages.get(status, f'Your withdrawal request has been {status}.'),
                metadata={
                    'withdrawal_id': str(withdrawal.withdrawal_id),
                    'amount': str(withdrawal.amount),
                    'net_amount': str(withdrawal.net_amount),
                    'status': status
                }
            )
            
        except ImportError:
            logger.warning("Notifications app not installed")
    
    def log_admin_action(self, admin, withdrawal, action, notes):
        """Log admin action for audit"""
        try:
            from reporting.utils import log_audit_action
            
            log_audit_action(
                admin=admin,
                action='APPROVE' if action == 'approve' else 'REJECT',
                target_object=f"Withdrawal {withdrawal.withdrawal_id}",
                target_model='ProfitWithdrawal',
                target_id=str(withdrawal.withdrawal_id),
                changes_after={'status': withdrawal.status, 'admin_notes': notes},
                request=self.request
            )
            
        except ImportError:
            logger.warning("Reporting app not installed")


class AdminCreateAlertView(generics.CreateAPIView):
    """
    Admin: Create investment alert
    """
    permission_classes = [IsAuthenticated, AdminOnly]
    serializer_class = InvestmentAlertSerializer
    
    def perform_create(self, serializer):
        alert = serializer.save()
        
        # Send notifications to targeted users
        self.send_alert_notifications(alert)
    
    def send_alert_notifications(self, alert):
        """Send notifications for new alert"""
        try:
            from notifications.utils import create_notification
            
            # Determine target users
            if alert.is_for_all_users:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                users = User.objects.filter(is_active=True)
            else:
                users = alert.target_users.all()
            
            # Send notification to each user
            for user in users:
                create_notification(
                    user=user,
                    notification_type='SYSTEM_UPDATE',
                    title=alert.title,
                    message=alert.message[:500],
                    metadata={
                        'alert_id': alert.id,
                        'alert_type': alert.alert_type,
                        'priority': alert.priority
                    }
                )
                
        except ImportError:
            logger.warning("Notifications app not installed")


class AdminPerformanceReportView(APIView):
    """
    Admin: Get comprehensive performance report
    """
    permission_classes = [IsAuthenticated, AdminOnly]
    
    def get(self, request):
        try:
            # Get date range from query params
            start_date = request.query_params.get('start_date')
            end_date = request.query_params.get('end_date')
            
            if end_date:
                end_date = timezone.datetime.strptime(end_date, '%Y-%m-%d').date()
            else:
                end_date = timezone.now().date()
            
            if start_date:
                start_date = timezone.datetime.strptime(start_date, '%Y-%m-%d').date()
            else:
                start_date = end_date - timezone.timedelta(days=30)
            
            # Convert to datetime for filtering
            start_datetime = timezone.make_aware(
                timezone.datetime.combine(start_date, timezone.datetime.min.time())
            )
            end_datetime = timezone.make_aware(
                timezone.datetime.combine(end_date, timezone.datetime.max.time())
            )
            
            # ============ OVERALL STATISTICS ============
            total_investments = UserInvestment.objects.filter(
                created_at__range=[start_datetime, end_datetime]
            ).count()
            
            active_investments = UserInvestment.objects.filter(
                status='ACTIVE',
                created_at__range=[start_datetime, end_datetime]
            ).count()
            
            completed_investments = UserInvestment.objects.filter(
                status='COMPLETED',
                created_at__range=[start_datetime, end_datetime]
            ).count()
            
            total_invested = UserInvestment.objects.filter(
                created_at__range=[start_datetime, end_datetime]
            ).aggregate(total=models.Sum('principal_amount'))['total'] or Decimal('0.00')
            
            total_profits = UserInvestment.objects.filter(
                created_at__range=[start_datetime, end_datetime]
            ).aggregate(total=models.Sum('total_profit'))['total'] or Decimal('0.00')
            
            total_withdrawals = ProfitWithdrawal.objects.filter(
                status='COMPLETED',
                created_at__range=[start_datetime, end_datetime]
            ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')
            
            # ============ PLAN-WISE DISTRIBUTION ============
            plan_stats = []
            for plan in InvestmentPlan.objects.all():
                plan_investments = plan.user_investments.filter(
                    created_at__range=[start_datetime, end_datetime]
                )
                
                if plan_investments.exists():
                    plan_stats.append({
                        'id': plan.id,
                        'name': plan.name,
                        'total_investments': plan_investments.count(),
                        'total_invested': sum(inv.principal_amount for inv in plan_investments),
                        'total_profits': sum(inv.total_profit for inv in plan_investments),
                        'active_investments': plan_investments.filter(status='ACTIVE').count(),
                        'completed_investments': plan_investments.filter(status='COMPLETED').count(),
                        'success_rate': plan.success_rate,
                        'avg_investment': sum(inv.principal_amount for inv in plan_investments) / plan_investments.count() if plan_investments.exists() else 0
                    })
            
            # ============ DAILY GROWTH ============
            daily_growth = []
            current_date = start_date
            while current_date <= end_date:
                day_start = timezone.make_aware(
                    timezone.datetime.combine(current_date, timezone.datetime.min.time())
                )
                day_end = timezone.make_aware(
                    timezone.datetime.combine(current_date, timezone.datetime.max.time())
                )
                
                day_investments = UserInvestment.objects.filter(
                    created_at__range=[day_start, day_end]
                )
                
                daily_growth.append({
                    'date': current_date.isoformat(),
                    'new_investments': day_investments.count(),
                    'total_invested': sum(inv.principal_amount for inv in day_investments),
                    'total_profits': sum(inv.total_profit for inv in day_investments)
                })
                
                current_date += timezone.timedelta(days=1)
            
            # ============ USER STATISTICS ============
            from django.contrib.auth import get_user_model
            User = get_user_model()
            
            new_users = User.objects.filter(
                created_at__range=[start_datetime, end_datetime]
            ).count()
            
            active_users = User.objects.filter(
                is_active=True,
                last_login__range=[start_datetime, end_datetime]
            ).count()
            
            # ============ TOP PERFORMERS ============
            top_investors = UserInvestment.objects.filter(
                created_at__range=[start_datetime, end_datetime]
            ).values('user__email').annotate(
                total_invested=models.Sum('principal_amount'),
                total_profit=models.Sum('total_profit'),
                investment_count=models.Count('id')
            ).order_by('-total_invested')[:10]
            
            report = {
                'period': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat(),
                    'days': (end_date - start_date).days
                },
                'overall': {
                    'total_investments': total_investments,
                    'active_investments': active_investments,
                    'completed_investments': completed_investments,
                    'total_invested': float(total_invested),
                    'total_profits': float(total_profits),
                    'total_withdrawals': float(total_withdrawals),
                    'net_profit': float(total_profits - total_withdrawals),
                    'avg_investment': float(total_invested / total_investments) if total_investments > 0 else 0,
                    'profit_ratio': float(total_profits / total_invested) if total_invested > 0 else 0
                },
                'plan_statistics': plan_stats,
                'daily_growth': daily_growth,
                'user_statistics': {
                    'new_users': new_users,
                    'active_users': active_users,
                    'conversion_rate': float(new_users / total_investments * 100) if total_investments > 0 else 0
                },
                'top_investors': [
                    {
                        'email': investor['user__email'],
                        'total_invested': float(investor['total_invested']),
                        'total_profit': float(investor['total_profit']),
                        'investment_count': investor['investment_count']
                    }
                    for investor in top_investors
                ]
            }
            
            return Response(report, status=status.HTTP_200_OK)
            
        except ValueError as e:
            logger.error(f"Invalid date format: {str(e)}")
            return Response(
                {'error': 'Invalid date format. Use YYYY-MM-DD'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error generating performance report: {str(e)}")
            return Response(
                {'error': 'Failed to generate report'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

