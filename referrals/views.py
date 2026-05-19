from django.shortcuts import render

# Create your views here.
from rest_framework import generics, views, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.conf import settings as django_settings
from decimal import Decimal
import logging

from .models import (
    Referral, BonusWallet, UserReferralCode,
    ReferralBonusSettings
)
from .serializers import (
    ReferralSerializer, BonusWalletSerializer,
    UserReferralCodeSerializer, CreateCustomCodeSerializer,
    ReferralStatsSerializer, WithdrawBonusSerializer,
    ReferralBonusSettingsSerializer, ReferralLinkSerializer
)
from .permissions import IsOwnerOrAdmin, AdminOnly
from .utils import generate_referral_qr_code

logger = logging.getLogger(__name__)


class MyReferralCodeView(generics.RetrieveAPIView):
    """
    Get user's referral code
    """
    permission_classes = [IsAuthenticated]
    serializer_class = UserReferralCodeSerializer
    
    def get_object(self):
        referral_code, created = UserReferralCode.objects.get_or_create(
            user=self.request.user
        )
        if created:
            referral_code.generate_code()
            referral_code.save()
        return referral_code


class CreateCustomCodeView(APIView):
    """
    Create custom referral code
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        serializer = CreateCustomCodeSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        custom_code = serializer.validated_data['custom_code']
        try:
            referral_code = UserReferralCode.objects.get(user=request.user)
            referral_code.custom_code = custom_code
            referral_code.save()
            return Response({
                'message': 'Custom referral code created successfully',
                'referral_code': UserReferralCodeSerializer(referral_code).data
            }, status=status.HTTP_200_OK)
        except UserReferralCode.DoesNotExist:
            return Response({'error': 'Referral code not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error creating custom code: {str(e)}")
            return Response({'error': 'Failed to create custom code'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MyReferralsView(generics.ListAPIView):
    """
    Get user's referrals
    """
    permission_classes = [IsAuthenticated]
    serializer_class = ReferralSerializer
    
    def get_queryset(self):
        return Referral.objects.filter(referrer=self.request.user).order_by('-created_at')


class ReferralStatsView(APIView):
    """
    Get user's referral statistics
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        try:
            referrals = Referral.objects.filter(referrer=request.user)
            total_referrals = referrals.count()
            active_referrals = referrals.filter(status='PENDING').count()
            earned_referrals = referrals.filter(status='EARNED').count()
            total_bonus_earned = sum(ref.bonus_amount for ref in referrals.filter(bonus_paid=True))
            pending_bonus = sum(ref.bonus_amount for ref in referrals.filter(status='EARNED', bonus_paid=False))
            
            try:
                bonus_wallet = BonusWallet.objects.get(user=request.user)
                bonus_wallet_balance = bonus_wallet.balance
            except BonusWallet.DoesNotExist:
                bonus_wallet_balance = Decimal('0.00')
            
            stats = {
                'total_referrals': total_referrals,
                'active_referrals': active_referrals,
                'earned_referrals': earned_referrals,
                'total_bonus_earned': total_bonus_earned,
                'pending_bonus': pending_bonus,
                'bonus_wallet_balance': bonus_wallet_balance
            }
            
            serializer = ReferralStatsSerializer(stats)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error getting referral stats: {str(e)}")
            return Response({'error': 'Failed to get referral statistics'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MyBonusWalletView(generics.RetrieveAPIView):
    """
    Get user's bonus wallet
    """
    permission_classes = [IsAuthenticated]
    serializer_class = BonusWalletSerializer
    
    def get_object(self):
        bonus_wallet, created = BonusWallet.objects.get_or_create(user=self.request.user)
        return bonus_wallet


class WithdrawBonusView(APIView):
    """
    Withdraw bonus to main wallet
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        serializer = WithdrawBonusSerializer(data=request.data, context={'request': request})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        amount = serializer.validated_data['amount']
        to_main_wallet = serializer.validated_data.get('to_main_wallet', True)
        bonus_wallet = serializer.validated_data['bonus_wallet']
        
        try:
            with transaction.atomic():
                settings_obj = ReferralBonusSettings.get_settings()
                if not settings_obj.bonus_withdrawal_enabled:
                    return Response({'error': 'Bonus withdrawal is currently disabled'}, status=status.HTTP_400_BAD_REQUEST)
                
                fee = amount * (settings_obj.withdrawal_fee_percentage / Decimal('100'))
                net_amount = amount - fee
                bonus_wallet.debit(amount)
                
                if to_main_wallet:
                    try:
                        from wallet.models import Wallet
                        main_wallet = Wallet.objects.get(user=request.user)
                        main_wallet.credit(net_amount, transaction_type='REFERRAL_BONUS')
                        
                        from wallet.models import Transaction
                        Transaction.objects.create(
                            wallet=main_wallet,
                            transaction_type=Transaction.TransactionType.DEPOSIT,
                            amount=net_amount,
                            status=Transaction.TransactionStatus.COMPLETED,
                            description=f"Referral bonus withdrawal (fee: ${fee})",
                            metadata={'source': 'referral_bonus', 'fee': str(fee), 'gross_amount': str(amount)}
                        )
                        message = f"${net_amount} transferred to main wallet (fee: ${fee})"
                    except ImportError:
                        logger.warning("Wallet app not installed")
                        message = "Bonus debited but wallet app not available"
                else:
                    message = f"${amount} withdrawn from bonus wallet (fee: ${fee})"
                
                try:
                    from notifications.utils import create_notification
                    create_notification(
                        user=request.user,
                        notification_type='REFERRAL_BONUS',
                        title='Bonus Withdrawal',
                        message=f"You have withdrawn ${amount} from your bonus wallet. Net amount: ${net_amount}",
                        metadata={'amount': str(amount), 'fee': str(fee), 'net_amount': str(net_amount)}
                    )
                except ImportError:
                    logger.warning("Notifications app not installed")
                
                return Response({
                    'message': message,
                    'amount': amount,
                    'fee': fee,
                    'net_amount': net_amount,
                    'remaining_balance': bonus_wallet.balance
                }, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error withdrawing bonus: {str(e)}")
            return Response({'error': 'Failed to withdraw bonus'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ReferralLinkView(APIView):
    """
    Get referral link and QR code
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        try:
            referral_code = UserReferralCode.objects.get(user=request.user)
            display_code = referral_code.get_display_code()
            base_url = getattr(django_settings, 'FRONTEND_URL', 'https://novaedgefinance.com')
            referral_link = f"{base_url}/register?ref={display_code}"
            qr_code_url = generate_referral_qr_code(referral_link)
            
            data = {
                'referral_code': display_code,
                'referral_link': referral_link,
                'qr_code_url': qr_code_url
            }
            
            serializer = ReferralLinkSerializer(data)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except UserReferralCode.DoesNotExist:
            return Response({'error': 'Referral code not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error generating referral link: {str(e)}")
            return Response({'error': 'Failed to generate referral link'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ============================================
# ADMIN VIEWS
# ============================================

class AdminReferralListView(generics.ListAPIView):
    """
    Admin: List all referrals with filters
    """
    permission_classes = [IsAuthenticated, AdminOnly]
    serializer_class = ReferralSerializer
    
    def get_queryset(self):
        queryset = Referral.objects.all()
        referrer_email = self.request.query_params.get('referrer_email', None)
        if referrer_email:
            queryset = queryset.filter(referrer__email__icontains=referrer_email)
        referred_email = self.request.query_params.get('referred_email', None)
        if referred_email:
            queryset = queryset.filter(referred_user__email__icontains=referred_email)
        status_filter = self.request.query_params.get('status', None)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        return queryset.order_by('-created_at')


class AdminBonusWalletListView(generics.ListAPIView):
    """
    Admin: List all bonus wallets with filters
    """
    permission_classes = [IsAuthenticated, AdminOnly]
    serializer_class = BonusWalletSerializer
    
    def get_queryset(self):
        queryset = BonusWallet.objects.all()
        user_email = self.request.query_params.get('user_email', None)
        if user_email:
            queryset = queryset.filter(user__email__icontains=user_email)
        return queryset.order_by('-balance')


class AdminReferralStatsView(APIView):
    """
    Admin: Get referral system statistics
    """
    permission_classes = [IsAuthenticated, AdminOnly]
    
    def get(self, request):
        try:
            from django.db.models import Count, Sum, Q
            from datetime import timedelta
            
            # Overall statistics
            total_referrals = Referral.objects.count()
            pending_referrals = Referral.objects.filter(status='PENDING').count()
            earned_referrals = Referral.objects.filter(status='EARNED').count()
            cancelled_referrals = Referral.objects.filter(status='CANCELLED').count()
            
            # Bonus totals using Sum directly
            total_bonus_paid = Referral.objects.filter(bonus_paid=True).aggregate(
                total=Sum('bonus_amount')
            )['total'] or Decimal('0.00')
            
            total_bonus_pending = Referral.objects.filter(
                status='EARNED', 
                bonus_paid=False
            ).aggregate(total=Sum('bonus_amount'))['total'] or Decimal('0.00')
            
            # Active referrers
            active_referrers = Referral.objects.values('referrer').distinct().count()
            total_referrers = UserReferralCode.objects.count()
            
            # Conversion rate
            conversion_rate = 0
            if total_referrals > 0:
                conversion_rate = round((earned_referrals / total_referrals) * 100, 1)
            
            # Top referrers
            top_referrers = []
            referrer_stats = Referral.objects.values(
                'referrer__email', 
                'referrer__first_name', 
                'referrer__last_name'
            ).annotate(
                total_count=Count('id'),
                successful_count=Count('id', filter=Q(status='EARNED')),
                total_earned=Sum('bonus_amount', filter=Q(bonus_paid=True))
            ).order_by('-successful_count')[:10]
            
            for stat in referrer_stats:
                top_referrers.append({
                    'user_email': stat['referrer__email'],
                    'user_name': f"{stat.get('referrer__first_name', '')} {stat.get('referrer__last_name', '')}".strip() or stat['referrer__email'],
                    'total_referrals': stat['total_count'],
                    'successful_referrals': stat['successful_count'],
                    'total_earned': str(stat['total_earned'] or Decimal('0.00'))
                })
            
            # Monthly growth (last 6 months)
            monthly_growth = []
            for i in range(5, -1, -1):
                month_date = timezone.now() - timedelta(days=30*i)
                month_start = month_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                
                if month_date.month == 12:
                    month_end = month_date.replace(year=month_date.year + 1, month=1, day=1)
                else:
                    month_end = month_date.replace(month=month_date.month + 1, day=1)
                
                month_referrals = Referral.objects.filter(
                    created_at__gte=month_start,
                    created_at__lt=month_end
                )
                
                monthly_growth.append({
                    'month': month_start.strftime('%Y-%m'),
                    'new_referrals': month_referrals.count(),
                    'successful_referrals': month_referrals.filter(status='EARNED').count(),
                    'bonus_paid': str(
                        month_referrals.filter(bonus_paid=True).aggregate(
                            total=Sum('bonus_amount')
                        )['total'] or Decimal('0.00')
                    )
                })
            
            stats = {
                'total_referrals': total_referrals,
                'successful_referrals': earned_referrals,
                'pending_referrals': pending_referrals,
                'cancelled_referrals': cancelled_referrals,
                'total_bonuses': str(total_bonus_paid),
                'total_bonus_pending': str(total_bonus_pending),
                'active_referrers': active_referrers,
                'total_referrers': total_referrers,
                'conversion_rate': conversion_rate,
                'top_referrers': top_referrers,
                'monthly_growth': monthly_growth
            }
            
            return Response(stats, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error getting admin referral stats: {str(e)}")
            import traceback
            traceback.print_exc()
            return Response({
                'error': 'Failed to get referral statistics',
                'detail': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AdminReferralSettingsView(generics.RetrieveUpdateAPIView):
    """
    Admin: Manage referral settings
    """
    permission_classes = [IsAuthenticated, AdminOnly]
    serializer_class = ReferralBonusSettingsSerializer
    
    def get_object(self):
        return ReferralBonusSettings.get_settings()


class AdminManualBonusView(APIView):
    """
    Admin: Manually credit bonus to user
    """
    permission_classes = [IsAuthenticated, AdminOnly]
    
    def post(self, request):
        user_id = request.data.get('user_id')
        amount = request.data.get('amount', 5.00)
        reason = request.data.get('reason', 'Manual bonus adjustment')
        
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user = User.objects.get(id=user_id)
            
            with transaction.atomic():
                bonus_wallet, created = BonusWallet.objects.get_or_create(user=user)
                bonus_wallet.credit(amount)
                
                try:
                    from notifications.utils import create_notification
                    create_notification(
                        user=user,
                        notification_type='REFERRAL_BONUS',
                        title='Manual Bonus Credit',
                        message=f'Admin has credited ${amount} to your bonus wallet. Reason: {reason}',
                        metadata={'amount': str(amount), 'reason': reason, 'admin': request.user.email}
                    )
                except ImportError:
                    logger.warning("Notifications app not installed")
                
                return Response({
                    'message': f'${amount} credited to {user.email}\'s bonus wallet',
                    'bonus_wallet': BonusWalletSerializer(bonus_wallet).data
                }, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error crediting manual bonus: {str(e)}")
            return Response({'error': 'Failed to credit bonus'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


