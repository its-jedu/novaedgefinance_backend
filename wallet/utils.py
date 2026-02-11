import hashlib
import hmac
import json
import logging
from decimal import Decimal
from django.conf import settings
from django.utils import timezone
import uuid

logger = logging.getLogger(__name__)

class NOWPaymentsClient:
    """
    Enhanced NOWPayments client with signature verification and idempotency
    """
    
    def __init__(self):
        self.api_key = getattr(settings, 'NOWPAYMENTS_API_KEY', '')
        self.ipn_secret = getattr(settings, 'NOWPAYMENTS_IPN_SECRET', '')
        self.base_url = getattr(settings, 'NOWPAYMENTS_BASE_URL', 'https://api.nowpayments.io/v1')
        
    def get_headers(self):
        """Get API headers with authentication"""
        return {
            'x-api-key': self.api_key,
            'Content-Type': 'application/json'
        }
    
    def verify_webhook_signature(self, payload, signature):
        """
        Verify NOWPayments webhook signature using IPN secret
        Required: Strong signature verification
        """
        if not self.ipn_secret:
            logger.critical("NOWPayments IPN secret not configured - webhooks will be rejected")
            return False
        
        try:
            # Create HMAC SHA512 hash using IPN secret
            expected_signature = hmac.new(
                self.ipn_secret.encode('utf-8'),
                payload,
                hashlib.sha512
            ).hexdigest()
            
            # Use constant-time comparison to prevent timing attacks
            is_valid = hmac.compare_digest(expected_signature, signature)
            
            if not is_valid:
                logger.warning(f"Invalid webhook signature")
            
            return is_valid
            
        except Exception as e:
            logger.error(f"Signature verification failed: {str(e)}")
            return False
    
    def create_invoice(self, amount_usd, currency='usd', description=None, order_id=None):
        """
        Create a NOWPayments invoice with idempotency key
        """
        if not self.api_key:
            logger.error("NOWPayments API key not configured")
            return None
        
        if order_id is None:
            order_id = str(uuid.uuid4())
        
        url = f"{self.base_url}/invoice"
        
        payload = {
            'price_amount': float(amount_usd),
            'price_currency': 'usd',
            'pay_currency': currency.lower(),
            'ipn_callback_url': f"{settings.SITE_URL}/api/wallet/nowpayments-webhook/",
            'order_id': order_id,
            'order_description': description or f"Deposit of ${amount_usd}",
            'success_url': f"{settings.FRONTEND_URL}/deposit/success",
            'cancel_url': f"{settings.FRONTEND_URL}/deposit/cancel",
            'is_fee_paid_by_user': True
        }
        
        try:
            import requests
            response = requests.post(
                url,
                headers=self.get_headers(),
                json=payload,
                timeout=30
            )
            
            if response.status_code == 201:
                data = response.json()
                logger.info(f"NOWPayments invoice created: {data.get('id')}")
                return data
            else:
                logger.error(f"NOWPayments API error: {response.status_code} - {response.text}")
                return None
                
        except requests.RequestException as e:
            logger.error(f"NOWPayments API request failed: {str(e)}")
            return None
    
    def get_payment_status(self, payment_id):
        """
        Get payment status from NOWPayments
        """
        if not self.api_key:
            logger.error("NOWPayments API key not configured")
            return None
        
        url = f"{self.base_url}/payment/{payment_id}"
        
        try:
            import requests
            response = requests.get(
                url,
                headers=self.get_headers(),
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"NOWPayments status check failed: {response.status_code}")
                return None
                
        except requests.RequestException as e:
            logger.error(f"NOWPayments status check request failed: {str(e)}")
            return None
    
    def get_estimated_amount(self, amount_usd, currency):
        """
        Get estimated amount in cryptocurrency
        """
        if not self.api_key:
            logger.error("NOWPayments API key not configured")
            return None
        
        url = f"{self.base_url}/estimate"
        
        params = {
            'amount': float(amount_usd),
            'currency_from': 'usd',
            'currency_to': currency.lower()
        }
        
        try:
            import requests
            response = requests.get(
                url,
                headers=self.get_headers(),
                params=params,
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"NOWPayments estimate failed: {response.status_code}")
                return None
                
        except requests.RequestException as e:
            logger.error(f"NOWPayments estimate request failed: {str(e)}")
            return None


def process_webhook_with_idempotency(payment_id, payload, signature, request=None):
    """
    Process webhook with idempotency protection and replay attack prevention
    """
    from wallet.models import WebhookLog, Deposit
    from django.db import transaction
    
    # Create webhook log entry
    webhook_log = WebhookLog.objects.create(
        payment_id=payment_id,
        raw_payload=payload,
        signature=signature,
        headers=request.headers if request else {}
    )
    
    try:
        # Check if this payment has already been processed successfully
        existing_deposit = Deposit.objects.filter(payment_id=payment_id).first()
        
        if existing_deposit:
            if existing_deposit.status in [Deposit.PaymentStatus.CONFIRMED, 
                                          Deposit.PaymentStatus.FINISHED]:
                logger.info(f"Payment {payment_id} already processed - ignoring duplicate webhook")
                webhook_log.mark_processed()
                return {'status': 'ignored', 'reason': 'already_processed'}
        
        # Verify signature (required)
        client = NOWPaymentsClient()
        
        # Convert payload to bytes if it's a dict
        if isinstance(payload, dict):
            import json
            payload_bytes = json.dumps(payload).encode('utf-8')
        else:
            payload_bytes = payload
        
        if not client.verify_webhook_signature(payload_bytes, signature):
            webhook_log.signature_valid = False
            webhook_log.save()
            logger.error(f"Invalid signature for payment {payment_id}")
            return {'status': 'rejected', 'reason': 'invalid_signature'}
        
        webhook_log.signature_valid = True
        webhook_log.save()
        
        # Process the webhook
        with transaction.atomic():
            # Get user_id from payload metadata or order_id
            order_id = payload.get('order_id', '')
            user_id = None
            
            # Try to extract user_id from order_id if it contains user reference
            if 'user_' in order_id:
                try:
                    user_id = int(order_id.split('_')[1])
                except (IndexError, ValueError):
                    pass
            
            # Find or create deposit
            deposit, created = Deposit.objects.get_or_create(
                payment_id=payment_id,
                defaults={
                    'user_id': user_id,
                    'pay_currency': payload.get('pay_currency', '').upper(),
                    'pay_amount': Decimal(str(payload.get('pay_amount', 0))),
                    'usd_amount': Decimal(str(payload.get('price_amount', 0))),
                    'status': payload.get('payment_status', 'WAITING')
                }
            )
            
            # Update deposit status
            old_status = deposit.status
            deposit.status = payload.get('payment_status', deposit.status)
            deposit.payment_details = payload
            deposit.save()
            
            # Process if payment is confirmed (and not previously processed)
            if (deposit.status in ['confirmed', 'finished'] and 
                old_status not in ['confirmed', 'finished']):
                
                deposit.process_confirmation()
                
                # Trigger referral bonus if this is the user's first deposit
                try:
                    from referrals.utils import process_referral_on_deposit
                    process_referral_on_deposit(deposit.user, deposit.usd_amount)
                except ImportError:
                    logger.warning("Referral app not installed")
                
                logger.info(f"Deposit {deposit.deposit_id} processed successfully")
            
            webhook_log.mark_processed()
            
        return {'status': 'processed', 'deposit_id': str(deposit.deposit_id)}
        
    except Exception as e:
        webhook_log.mark_failed(str(e))
        logger.error(f"Error processing webhook for payment {payment_id}: {str(e)}")
        raise


def calculate_investment_growth(investment):
    """
    Calculate growth data for an investment
    
    Args:
        investment: UserInvestment instance
    
    Returns:
        list: Growth data points
    """
    growth_data = []
    
    if investment.status != investment.InvestmentStatus.ACTIVE:
        return growth_data
    
    # Calculate daily growth
    from datetime import timedelta
    
    start_date = investment.start_date.date()
    end_date = investment.end_date.date()
    current_date = min(timezone.now().date(), end_date)
    
    # Get number of days
    elapsed_days = (current_date - start_date).days
    
    for day in range(0, elapsed_days + 1):
        date_point = start_date + timedelta(days=day)
        
        # Calculate value for this day
        profit = investment.plan.calculate_profit(
            investment.principal_amount,
            day
        )
        value = investment.principal_amount + profit
        
        growth_data.append({
            'date': date_point,
            'value': float(value),
            'profit': float(profit)
        })
    
    return growth_data


def update_all_active_investments():
    """
    Update current value for all active investments
    """
    try:
        from investments.models import UserInvestment
        
        active_investments = UserInvestment.objects.filter(
            status=UserInvestment.InvestmentStatus.ACTIVE
        )
        
        updated_count = 0
        for investment in active_investments:
            try:
                investment.update_current_value()
                updated_count += 1
            except Exception as e:
                logger.error(f"Failed to update investment {investment.investment_id}: {str(e)}")
        
        logger.info(f"Updated {updated_count} active investments")
        return updated_count
        
    except ImportError:
        logger.warning("Investments app not installed")
        return 0