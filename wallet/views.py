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
from ..utils import process_webhook_with_idempotency
from authentication.permissions import IsProfileCompleted, CanMakeDeposits
from .models import Wallet, Transaction, Deposit
from .serializers import (
    WalletSerializer, TransactionSerializer,
    DepositSerializer, CreateDepositSerializer,
    WalletOverviewSerializer
)
from .utils import NOWPaymentsClient
from .permissions import IsOwnerOrAdmin, IsWalletOwnerOrAdmin, AdminOnly

logger = logging.getLogger(__name__)


class WalletOverviewView(APIView):
    """
    Get wallet overview including balance, profits, and recent transactions
    """
    permission_classes = [IsAuthenticated, IsProfileCompleted]
    
    def get(self, request):
        try:
            # Get or create wallet
            wallet, created = Wallet.objects.get_or_create(user=request.user)
            
            # Get recent transactions
            recent_transactions = Transaction.objects.filter(
                wallet=wallet
            ).order_by('-created_at')[:10]
            
            overview_data = {
                'balance': wallet.balance_usd,
                'total_deposits': wallet.total_deposited,
                'total_investments': wallet.total_invested,
                'total_profits': wallet.total_profit,
                'recent_transactions': recent_transactions
            }
            
            serializer = WalletOverviewSerializer(overview_data, context={'request': request})
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
            # Process webhook with idempotency
            result = process_webhook_with_idempotency(
                payment_id=payment_id,
                payload=request.data,
                signature=signature
            )
            
            if result['status'] == 'rejected':
                return Response(
                    {'error': result['reason']},
                    status=status.HTTP_401_UNAUTHORIZED
                )
            
            if result['status'] == 'ignored':
                return Response(
                    {'status': 'ignored', 'message': 'Already processed'},
                    status=status.HTTP_200_OK
                )
            
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


class AdminDepositDetailView(generics.RetrieveAPIView):
    """
    Admin: Get deposit details
    """
    permission_classes = [IsAuthenticated, AdminOnly]
    serializer_class = DepositSerializer
    queryset = Deposit.objects.all()
    lookup_field = 'deposit_id'

