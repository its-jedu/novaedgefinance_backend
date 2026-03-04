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
import hmac
from django.db import models
import hashlib
import json
from .utils import process_webhook_with_idempotency
from authentication.permissions import IsProfileCompleted, CanMakeDeposits
from .models import Wallet, Transaction, Deposit, WebhookLog
from investments.models import UserInvestment, InvestmentPlan
from investments.serializers import UserInvestmentSerializer, InvestmentPlanSerializer
from .serializers import (
    WalletSerializer, TransactionSerializer, 
    DepositSerializer, CreateDepositSerializer,
    WalletOverviewSerializer, DepositStatusSerializer
)
from .utils import NOWPaymentsClient
from .permissions import IsOwnerOrAdmin, IsWalletOwnerOrAdmin, AdminOnly

logger = logging.getLogger(__name__)


class WalletOverviewView(APIView):
    permission_classes = [IsAuthenticated, IsProfileCompleted]

    def get(self, request):
        wallet, _ = Wallet.objects.get_or_create(user=request.user)
        recent_transactions = Transaction.objects.filter(wallet=wallet).order_by('-created_at')[:10]
        
        # Get active investments
        from investments.models import UserInvestment
        active_investments = UserInvestment.objects.filter(
            user=request.user,
            status='ACTIVE'
        )
        
        # Calculate total invested and total profit
        total_invested = active_investments.aggregate(
            total=models.Sum('principal_amount')
        )['total'] or Decimal('0.00')
        
        total_profit = active_investments.aggregate(
            total=models.Sum('total_profit')
        )['total'] or Decimal('0.00')
        
        overview_data = {
            'balance': wallet.balance_usd,
            'total_balance': wallet.balance_usd + total_invested,
            'available_balance': wallet.balance_usd,
            'locked_balance': total_invested,
            'total_deposits': wallet.total_deposited,
            'total_investments': total_invested,
            'total_profits': total_profit,
            'total_withdrawn': wallet.total_withdrawn,
            'recent_transactions': recent_transactions,
            'active_investments_count': active_investments.count()
        }
        serializer = WalletOverviewSerializer(overview_data, context={'request': request})
        return Response(serializer.data)


class CreateDepositView(APIView):
    permission_classes = [IsAuthenticated, CanMakeDeposits]

    def post(self, request):
        serializer = CreateDepositSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        amount_usd = serializer.validated_data['amount_usd']
        currency = serializer.validated_data['currency']
        plan_id = serializer.validated_data.get('plan_id')
        
        # Validate plan if provided
        plan = None
        if plan_id:
            try:
                plan = InvestmentPlan.objects.get(id=plan_id, is_active=True)
                # Check if amount is within plan limits
                can_invest, message = plan.can_invest(amount_usd)
                if not can_invest:
                    return Response({'error': message}, status=status.HTTP_400_BAD_REQUEST)
            except InvestmentPlan.DoesNotExist:
                return Response({'error': 'Invalid investment plan'}, status=status.HTTP_404_NOT_FOUND)

        # Initialize NOWPayments client
        nowpayments = NOWPaymentsClient()
        
        # Get estimated amount
        estimate = nowpayments.get_estimated_amount(amount_usd, currency)
        if not estimate:
            logger.error(f"Failed to get estimate for {amount_usd} {currency}")
            return Response(
                {'error': 'Failed to get estimated amount'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # Create invoice
        invoice = nowpayments.create_invoice(
            amount_usd, 
            currency, 
            description=f"Deposit of ${amount_usd}" + (f" for {plan.name}" if plan else "")
        )
        
        if not invoice:
            logger.error(f"Failed to create invoice for {amount_usd} {currency}")
            return Response(
                {'error': 'Failed to create invoice'}, 
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
            payment_details={
                'invoice': invoice,
                'plan_id': plan_id,
                'plan_name': plan.name if plan else None
            },
            status=Deposit.PaymentStatus.WAITING
        )
        
        # Prepare response data
        response_data = DepositSerializer(deposit).data
        response_data.update({
            'payment_url': invoice.get('invoice_url'),
            'qr_code_url': invoice.get('qr_code_url'),
            'expires_at': invoice.get('expires_at'),
            'pay_address': invoice.get('pay_address')
        })
        
        return Response(response_data, status=status.HTTP_201_CREATED)


class DepositStatusView(APIView):
    """
    Check deposit status
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        payment_id = request.query_params.get('payment_id')
        if not payment_id:
            return Response(
                {'error': 'payment_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            deposit = Deposit.objects.get(payment_id=payment_id, user=request.user)
            serializer = DepositStatusSerializer(deposit)
            return Response(serializer.data)
        except Deposit.DoesNotExist:
            return Response(
                {'error': 'Deposit not found'},
                status=status.HTTP_404_NOT_FOUND
            )


class InvestmentPlansView(APIView):
    """
    Public: List investment plans
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        plans = InvestmentPlan.objects.filter(is_active=True).order_by('display_order', 'min_amount')
        
        # Add user's current plan if any
        current_investment = UserInvestment.objects.filter(
            user=request.user,
            status='ACTIVE'
        ).first()
        
        serializer = InvestmentPlanSerializer(
            plans, 
            many=True, 
            context={'current_investment': current_investment}
        )
        return Response(serializer.data)


class InvestmentGrowthView(APIView):
    """
    Return growth chart data for a given investment
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, investment_id):
        investment = get_object_or_404(
            UserInvestment, 
            investment_id=investment_id, 
            user=request.user
        )
        
        # Generate growth data for the last 30 days
        from datetime import timedelta
        import random
        
        end_date = timezone.now()
        start_date = end_date - timedelta(days=30)
        
        growth_data = {
            'labels': [],
            'values': [],
            'principal': float(investment.principal_amount)
        }
        
        current_date = start_date
        while current_date <= end_date:
            growth_data['labels'].append(current_date.strftime('%Y-%m-%d'))
            
            # Calculate simulated growth based on plan parameters
            days_passed = (current_date - investment.start_date).days
            if days_passed < 0:
                value = float(investment.principal_amount)
            else:
                daily_rate = float(investment.plan.calculate_daily_return_rate())
                profit = float(investment.principal_amount) * daily_rate * days_passed
                value = float(investment.principal_amount) + profit
            
            growth_data['values'].append(round(value, 2))
            current_date += timedelta(days=1)
        
        return Response(growth_data)


class StartInvestmentView(APIView):
    """
    Start a new investment from wallet balance
    """
    permission_classes = [IsAuthenticated, IsProfileCompleted]

    @transaction.atomic
    def post(self, request):
        data = request.data
        plan_id = data.get('plan_id')
        amount = Decimal(data.get('amount', 0))
        
        # Validate plan
        try:
            plan = InvestmentPlan.objects.get(id=plan_id, is_active=True)
        except InvestmentPlan.DoesNotExist:
            return Response(
                {'error': 'Invalid investment plan'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check amount limits
        can_invest, message = plan.can_invest(amount)
        if not can_invest:
            return Response({'error': message}, status=status.HTTP_400_BAD_REQUEST)
        
        # Check wallet balance
        wallet = Wallet.objects.select_for_update().get(user=request.user)
        if wallet.balance_usd < amount:
            return Response(
                {'error': f'Insufficient balance. Available: ${wallet.balance_usd}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Calculate investment dates
        start_date = timezone.now()
        end_date = start_date + timezone.timedelta(days=plan.max_duration_days or 30)
        
        # Calculate expected returns
        avg_multiplier = (plan.min_return_multiplier + plan.max_return_multiplier) / 2
        expected_total = amount + (amount * (avg_multiplier / Decimal('100')))
        
        # Create investment
        user_investment = UserInvestment.objects.create(
            user=request.user,
            plan=plan,
            principal_amount=amount,
            expected_return_multiplier=avg_multiplier,
            expected_total=expected_total,
            current_value=amount,
            start_date=start_date,
            end_date=end_date,
            status=UserInvestment.InvestmentStatus.ACTIVE
        )
        
        # Debit wallet
        wallet.debit(
            amount=amount,
            transaction_type='INVESTMENT',
            reference=str(user_investment.investment_id),
            description=f"Investment in {plan.name}",
            metadata={
                'plan_id': plan.id,
                'plan_name': plan.name,
                'investment_id': str(user_investment.investment_id)
            },
            request=request
        )
        
        # Update plan statistics
        plan.total_invested += amount
        plan.total_investors = plan.user_investments.filter(
            status__in=['ACTIVE', 'COMPLETED']
        ).count()
        plan.save()
        
        serializer = UserInvestmentSerializer(user_investment)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class UserInvestmentsView(generics.ListAPIView):
    """
    List user investments
    """
    permission_classes = [IsAuthenticated, IsProfileCompleted]
    serializer_class = UserInvestmentSerializer

    def get_queryset(self):
        return UserInvestment.objects.filter(
            user=self.request.user
        ).select_related('plan').order_by('-start_date')


class UserInvestmentDetailView(generics.RetrieveAPIView):
    """
    Get investment details
    """
    permission_classes = [IsAuthenticated]
    serializer_class = UserInvestmentSerializer
    lookup_field = 'investment_id'

    def get_queryset(self):
        return UserInvestment.objects.filter(user=self.request.user)


class NOWPaymentsWebhookView(APIView):
    """
    Handle NOWPayments IPN callbacks with enhanced security
    """
    permission_classes = [permissions.AllowAny]
    authentication_classes = []  # No authentication required
    
    def post(self, request):
        # Get signature from headers
        signature = request.headers.get('X-Nowpayments-Sig', '')
        payment_id = request.data.get('payment_id')
        
        if not payment_id:
            logger.error("Webhook missing payment_id")
            return Response(
                {'error': 'Missing payment_id'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Verify signature
            secret = settings.NOWPAYMENTS_IPN_SECRET
            payload = json.dumps(request.data, separators=(',', ':')).encode('utf-8')
            expected_signature = hmac.new(
                secret.encode('utf-8'),
                payload,
                hashlib.sha512
            ).hexdigest()
            
            signature_valid = hmac.compare_digest(signature, expected_signature)
            
            if not signature_valid:
                logger.warning(f"Invalid signature for payment {payment_id}")
                return Response(
                    {'error': 'Invalid signature'},
                    status=status.HTTP_401_UNAUTHORIZED
                )
            
            # Process webhook with idempotency
            result = process_webhook_with_idempotency(
                payment_id=payment_id,
                payload=request.data,
                signature=signature
            )
            
            if result['status'] == 'ignored':
                return Response(
                    {'status': 'ignored', 'message': 'Already processed'},
                    status=status.HTTP_200_OK
                )
            
            # Get deposit
            try:
                deposit = Deposit.objects.get(payment_id=payment_id)
            except Deposit.DoesNotExist:
                logger.error(f"Deposit not found for payment {payment_id}")
                return Response(
                    {'error': 'Deposit not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Update deposit status based on webhook
            payment_status = request.data.get('payment_status')
            
            if payment_status in ['finished', 'confirmed']:
                deposit.status = Deposit.PaymentStatus.CONFIRMED
                deposit.payment_details.update({'webhook': request.data})
                deposit.save()
                
                # Process confirmation
                deposit.process_confirmation()
                
                # Create notification
                from notifications.models import Notification
                Notification.objects.create(
                    user=deposit.user,
                    notification_type='DEPOSIT_CONFIRMED',
                    title='Deposit Confirmed',
                    message=f'Your deposit of ${deposit.usd_amount} has been confirmed.',
                    metadata={'deposit_id': str(deposit.deposit_id)}
                )
                
                logger.info(f"Deposit {payment_id} confirmed")
                
            elif payment_status == 'failed':
                deposit.status = Deposit.PaymentStatus.FAILED
                deposit.payment_details.update({'webhook': request.data})
                deposit.save()
                
            elif payment_status == 'expired':
                deposit.status = Deposit.PaymentStatus.EXPIRED
                deposit.payment_details.update({'webhook': request.data})
                deposit.save()
            
            return Response(
                {'status': 'processed'},
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            logger.error(f"Webhook processing failed: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# User Transaction Endpoints

class UserTransactionsView(generics.ListAPIView):
    """
    Get user's transactions with pagination and filtering
    """
    permission_classes = [IsAuthenticated, IsProfileCompleted]
    serializer_class = TransactionSerializer
    
    def get_queryset(self):
        wallet, created = Wallet.objects.get_or_create(user=self.request.user)
        queryset = Transaction.objects.filter(wallet=wallet)
        
        # Filter by type
        tx_type = self.request.query_params.get('type')
        if tx_type:
            queryset = queryset.filter(transaction_type=tx_type.upper())
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        
        if start_date:
            queryset = queryset.filter(created_at__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__date__lte=end_date)
        
        return queryset.order_by('-created_at')


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
        
        # Filter by balance range
        min_balance = self.request.query_params.get('min_balance')
        max_balance = self.request.query_params.get('max_balance')
        
        if min_balance:
            queryset = queryset.filter(balance_usd__gte=min_balance)
        if max_balance:
            queryset = queryset.filter(balance_usd__lte=max_balance)
        
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


class AdminDepositDetailView(generics.RetrieveAPIView):
    """
    Admin: Get deposit details
    """
    permission_classes = [IsAuthenticated, AdminOnly]
    serializer_class = DepositSerializer
    queryset = Deposit.objects.all()
    lookup_field = 'deposit_id'


class AdminInvestmentListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated, AdminOnly]
    serializer_class = UserInvestmentSerializer

    def get_queryset(self):
        return UserInvestment.objects.all().select_related('user', 'plan').order_by('-start_date')


class AdminCreateInvestmentPlanView(generics.CreateAPIView):
    permission_classes = [IsAuthenticated, AdminOnly]
    serializer_class = InvestmentPlanSerializer


class AdminUpdateInvestmentPlanView(generics.UpdateAPIView):
    permission_classes = [IsAuthenticated, AdminOnly]
    serializer_class = InvestmentPlanSerializer
    queryset = InvestmentPlan.objects.all()
    lookup_field = 'id'