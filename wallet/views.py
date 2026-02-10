from django.shortcuts import render

# Create your views here.
from rest_framework import views, generics, status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.db import transaction
from django.shortcuts import get_object_or_404
from decimal import Decimal
import logging

from authentication.permissions import IsProfileCompleted, CanMakeDeposits
from .models import (
    Wallet, Transaction, InvestmentPlan,
    UserInvestment, Deposit
)
from .serializers import (
    WalletSerializer, TransactionSerializer,
    InvestmentPlanSerializer, UserInvestmentSerializer,
    CreateInvestmentSerializer, DepositSerializer,
    CreateDepositSerializer, InvestmentGrowthDataSerializer,
    WalletOverviewSerializer
)
from .utils import NOWPaymentsClient, calculate_investment_growth, update_all_active_investments
from .permissions import IsOwnerOrAdmin, IsWalletOwnerOrAdmin, AdminOnly

logger = logging.getLogger(__name__)


class WalletOverviewView(APIView):
    """
    Get wallet overview including balance, profits, and active investments
    """
    permission_classes = [IsAuthenticated, IsProfileCompleted]
    
    def get(self, request):
        try:
            # Update all active investments before fetching data
            update_all_active_investments()
            
            # Get or create wallet
            wallet, created = Wallet.objects.get_or_create(user=request.user)
            
            # Get active investments
            active_investments = UserInvestment.objects.filter(
                user=request.user,
                status=UserInvestment.InvestmentStatus.ACTIVE
            )
            
            # Calculate active investments total
            active_investments_total = sum(
                investment.current_value for investment in active_investments
            )
            
            # Get recent transactions
            recent_transactions = Transaction.objects.filter(
                wallet=wallet
            ).order_by('-created_at')[:10]
            
            # Get recent investments
            recent_investments = UserInvestment.objects.filter(
                user=request.user
            ).order_by('-created_at')[:5]
            
            overview_data = {
                'balance': wallet.balance_usd,
                'total_deposits': wallet.total_deposited,
                'total_investments': wallet.total_invested,
                'total_profits': wallet.total_profit,
                'active_investments_count': active_investments.count(),
                'active_investments_total': active_investments_total,
                'recent_transactions': recent_transactions,
                'recent_investments': recent_investments
            }
            
            serializer = WalletOverviewSerializer(overview_data)
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error getting wallet overview: {str(e)}")
            return Response(
                {'error': 'Failed to get wallet overview'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CreateDepositView(APIView):
    """
    Create a NOWPayments deposit
    """
    permission_classes = [IsAuthenticated, CanMakeDeposits]
    
    def post(self, request):
        serializer = CreateDepositSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        amount_usd = serializer.validated_data['amount_usd']
        currency = serializer.validated_data['currency']
        
        try:
            # Initialize NOWPayments client
            nowpayments = NOWPaymentsClient()
            
            # Get estimated amount in cryptocurrency
            estimate = nowpayments.get_estimated_amount(amount_usd, currency)
            if not estimate:
                return Response(
                    {'error': 'Failed to get estimated amount from payment processor'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            # Create invoice
            invoice = nowpayments.create_invoice(
                amount_usd=amount_usd,
                currency=currency,
                description=f"Deposit of ${amount_usd} to NovaEdgeFinance"
            )
            
            if not invoice:
                return Response(
                    {'error': 'Failed to create payment invoice'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            # Create deposit record
            deposit = Deposit.objects.create(
                user=request.user,
                payment_id=invoice.get('id'),
                invoice_id=invoice.get('invoice_id'),
                pay_address=invoice.get('pay_address'),
                pay_currency=currency.upper(),
                pay_amount=Decimal(str(estimate.get('estimated_amount', 0))),
                usd_amount=amount_usd,
                exchange_rate=Decimal(str(estimate.get('estimated_rate', 0))),
                payment_details=invoice
            )
            
            # Prepare response
            response_data = DepositSerializer(deposit).data
            response_data['payment_url'] = invoice.get('invoice_url')
            response_data['qr_code_url'] = invoice.get('qr_code_url')
            
            return Response(response_data, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"Error creating deposit: {str(e)}")
            return Response(
                {'error': 'Failed to create deposit'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class InvestmentPlansView(generics.ListAPIView):
    """
    Get all active investment plans
    """
    permission_classes = [IsAuthenticated, IsProfileCompleted]
    serializer_class = InvestmentPlanSerializer
    queryset = InvestmentPlan.objects.filter(is_active=True).order_by('min_amount')


class StartInvestmentView(APIView):
    """
    Start a new investment
    """
    permission_classes = [IsAuthenticated, IsProfileCompleted]
    
    def post(self, request):
        serializer = CreateInvestmentSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        plan = serializer.validated_data['plan']
        amount = serializer.validated_data['amount']
        
        try:
            with transaction.atomic():
                # Get or create wallet
                wallet, created = Wallet.objects.get_or_create(user=request.user)
                
                # Check if user has sufficient balance
                if not wallet.can_invest(amount):
                    return Response(
                        {'error': 'Insufficient balance'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Calculate end date
                start_date = timezone.now()
                end_date = start_date + timezone.timedelta(days=plan.duration_days)
                
                # Calculate expected total
                expected_total = amount + plan.calculate_profit(amount)
                
                # Create investment
                investment = UserInvestment.objects.create(
                    user=request.user,
                    plan=plan,
                    principal_amount=amount,
                    expected_total=expected_total,
                    current_value=amount,
                    start_date=start_date,
                    end_date=end_date,
                    last_compounded_at=start_date,
                    status=UserInvestment.InvestmentStatus.ACTIVE
                )
                
                # Debit amount from wallet
                wallet.debit(amount, transaction_type='INVESTMENT')
                
                # Record transaction
                Transaction.objects.create(
                    wallet=wallet,
                    transaction_type=Transaction.TransactionType.INVESTMENT,
                    amount=amount,
                    status=Transaction.TransactionStatus.COMPLETED,
                    description=f"Investment in {plan.name} plan",
                    reference=str(investment.investment_id),
                    metadata={
                        'plan_id': plan.id,
                        'plan_name': plan.name,
                        'duration_days': plan.duration_days
                    }
                )
                
                serializer = UserInvestmentSerializer(investment)
                return Response(serializer.data, status=status.HTTP_201_CREATED)
                
        except Exception as e:
            logger.error(f"Error starting investment: {str(e)}")
            return Response(
                {'error': 'Failed to start investment'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class InvestmentGrowthView(APIView):
    """
    Get investment growth data for charts
    """
    permission_classes = [IsAuthenticated, IsProfileCompleted, IsOwnerOrAdmin]
    
    def get(self, request, investment_id):
        try:
            investment = get_object_or_404(
                UserInvestment,
                investment_id=investment_id
            )
            
            # Check permission
            if investment.user != request.user and request.user.role != 'ADMIN':
                return Response(
                    {'error': 'Permission denied'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Update investment value
            investment.update_current_value()
            
            # Calculate growth data
            growth_data = calculate_investment_growth(investment)
            
            serializer = InvestmentGrowthDataSerializer(growth_data, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except UserInvestment.DoesNotExist:
            return Response(
                {'error': 'Investment not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error getting investment growth: {str(e)}")
            return Response(
                {'error': 'Failed to get growth data'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class NOWPaymentsWebhookView(APIView):
    """
    Handle NOWPayments IPN callbacks
    """
    permission_classes = [permissions.AllowAny]  # No authentication for webhooks
    
    def post(self, request):
        # Get signature from headers
        signature = request.headers.get('X-Nowpayments-Sig')
        
        # Verify signature
        nowpayments = NOWPaymentsClient()
        raw_body = request.body
        
        if not nowpayments.verify_webhook_signature(raw_body, signature):
            logger.warning(f"Invalid webhook signature: {signature}")
            return Response({'error': 'Invalid signature'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            payload = request.data
            
            # Log webhook receipt
            logger.info(f"NOWPayments webhook received: {payload}")
            
            payment_id = payload.get('payment_id')
            status = payload.get('payment_status')
            
            if not payment_id:
                logger.error("Webhook missing payment_id")
                return Response({'error': 'Missing payment_id'}, status=status.HTTP_400_BAD_REQUEST)
            
            # Find deposit
            try:
                deposit = Deposit.objects.get(payment_id=payment_id)
            except Deposit.DoesNotExist:
                logger.error(f"Deposit not found for payment_id: {payment_id}")
                return Response({'error': 'Deposit not found'}, status=status.HTTP_404_NOT_FOUND)
            
            # Update deposit status
            deposit.status = status
            deposit.payment_details = payload
            deposit.save()
            
            # Process if payment is confirmed
            if status in ['confirmed', 'finished']:
                deposit.process_confirmation()
                
                # Log successful processing
                logger.info(f"Deposit {deposit.deposit_id} processed successfully")
                
                # TODO: Send notifications to user and admin
            
            return Response({'status': 'processed'}, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error processing webhook: {str(e)}")
            return Response(
                {'error': 'Failed to process webhook'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# Admin Views

class AdminWalletListView(generics.ListAPIView):
    """
    Admin: List all wallets
    """
    permission_classes = [IsAuthenticated, AdminOnly]
    serializer_class = WalletSerializer
    queryset = Wallet.objects.all().order_by('-created_at')
    
    def get_queryset(self):
        queryset = Wallet.objects.all()
        
        # Filter by user email if provided
        user_email = self.request.query_params.get('user_email', None)
        if user_email:
            queryset = queryset.filter(user__email__icontains=user_email)
        
        return queryset.order_by('-created_at')


class AdminTransactionListView(generics.ListAPIView):
    """
    Admin: List all transactions
    """
    permission_classes = [IsAuthenticated, AdminOnly]
    serializer_class = TransactionSerializer
    queryset = Transaction.objects.all().order_by('-created_at')
    
    def get_queryset(self):
        queryset = Transaction.objects.all()
        
        # Filter by transaction type if provided
        transaction_type = self.request.query_params.get('type', None)
        if transaction_type:
            queryset = queryset.filter(transaction_type=transaction_type)
        
        # Filter by user email if provided
        user_email = self.request.query_params.get('user_email', None)
        if user_email:
            queryset = queryset.filter(wallet__user__email__icontains=user_email)
        
        # Filter by date range if provided
        start_date = self.request.query_params.get('start_date', None)
        end_date = self.request.query_params.get('end_date', None)
        
        if start_date:
            queryset = queryset.filter(created_at__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__date__lte=end_date)
        
        return queryset.order_by('-created_at')


class AdminDepositListView(generics.ListAPIView):
    """
    Admin: List all deposits
    """
    permission_classes = [IsAuthenticated, AdminOnly]
    serializer_class = DepositSerializer
    queryset = Deposit.objects.all().order_by('-created_at')
    
    def get_queryset(self):
        queryset = Deposit.objects.all()
        
        # Filter by status if provided
        status_filter = self.request.query_params.get('status', None)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filter by user email if provided
        user_email = self.request.query_params.get('user_email', None)
        if user_email:
            queryset = queryset.filter(user__email__icontains=user_email)
        
        # Filter by currency if provided
        currency = self.request.query_params.get('currency', None)
        if currency:
            queryset = queryset.filter(pay_currency=currency.upper())
        
        return queryset.order_by('-created_at')


class AdminInvestmentListView(generics.ListAPIView):
    """
    Admin: List all investments
    """
    permission_classes = [IsAuthenticated, AdminOnly]
    serializer_class = UserInvestmentSerializer
    queryset = UserInvestment.objects.all().order_by('-created_at')
    
    def get_queryset(self):
        queryset = UserInvestment.objects.all()
        
        # Filter by status if provided
        status_filter = self.request.query_params.get('status', None)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filter by plan if provided
        plan_id = self.request.query_params.get('plan_id', None)
        if plan_id:
            queryset = queryset.filter(plan_id=plan_id)
        
        # Filter by user email if provided
        user_email = self.request.query_params.get('user_email', None)
        if user_email:
            queryset = queryset.filter(user__email__icontains=user_email)
        
        return queryset.order_by('-created_at')


class AdminCreateInvestmentPlanView(generics.CreateAPIView):
    """
    Admin: Create investment plan
    """
    permission_classes = [IsAuthenticated, AdminOnly]
    serializer_class = InvestmentPlanSerializer


class AdminUpdateInvestmentPlanView(generics.UpdateAPIView):
    """
    Admin: Update investment plan
    """
    permission_classes = [IsAuthenticated, AdminOnly]
    serializer_class = InvestmentPlanSerializer
    queryset = InvestmentPlan.objects.all()
    lookup_field = 'id'


class UserInvestmentsView(generics.ListAPIView):
    """
    Get user's investments
    """
    permission_classes = [IsAuthenticated, IsProfileCompleted]
    serializer_class = UserInvestmentSerializer
    
    def get_queryset(self):
        return UserInvestment.objects.filter(
            user=self.request.user
        ).order_by('-created_at')


class UserTransactionsView(generics.ListAPIView):
    """
    Get user's transactions
    """
    permission_classes = [IsAuthenticated, IsProfileCompleted]
    serializer_class = TransactionSerializer
    
    def get_queryset(self):
        wallet, created = Wallet.objects.get_or_create(user=self.request.user)
        return Transaction.objects.filter(
            wallet=wallet
        ).order_by('-created_at')


class UserDepositsView(generics.ListAPIView):
    """
    Get user's deposits
    """
    permission_classes = [IsAuthenticated, IsProfileCompleted]
    serializer_class = DepositSerializer
    
    def get_queryset(self):
        return Deposit.objects.filter(
            user=self.request.user
        ).order_by('-created_at')