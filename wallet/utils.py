import hashlib
import hmac
import json
import logging
from decimal import Decimal
from django.conf import settings
from django.utils import timezone
from django.db import transaction
from django.db import models
import uuid
import requests
from datetime import timedelta

logger = logging.getLogger(__name__)

class NOWPaymentsClient:
    """
    Enhanced NOWPayments client with signature verification and idempotency
    """
    
    def __init__(self):
        self.api_key = getattr(settings, 'NOWPAYMENTS_API_KEY', '')
        self.ipn_secret = getattr(settings, 'NOWPAYMENTS_IPN_SECRET', '')
        self.base_url = getattr(settings, 'NOWPAYMENTS_BASE_URL', 'https://api.nowpayments.io/v1')
        
        # Validate configuration on initialization
        if not self.api_key:
            logger.warning("NOWPayments API key not configured")
        if not self.ipn_secret:
            logger.warning("NOWPayments IPN secret not configured - webhook verification will fail")
    
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
        
        Args:
            payload: Raw request body (bytes) or dictionary
            signature: Signature from X-Nowpayments-Sig header
        
        Returns:
            bool: True if signature is valid
        """
        if not self.ipn_secret:
            logger.critical("NOWPayments IPN secret not configured - webhooks will be rejected")
            return False
        
        try:
            # Convert payload to bytes if it's a dictionary
            if isinstance(payload, dict):
                # Sort keys to ensure consistent JSON stringification
                payload_str = json.dumps(payload, sort_keys=True, separators=(',', ':'))
                payload_bytes = payload_str.encode('utf-8')
            else:
                payload_bytes = payload
            
            # Create HMAC SHA512 hash using IPN secret
            expected_signature = hmac.new(
                self.ipn_secret.encode('utf-8'),
                payload_bytes,
                hashlib.sha512
            ).hexdigest()
            
            # Use constant-time comparison to prevent timing attacks
            is_valid = hmac.compare_digest(expected_signature, signature)
            
            if not is_valid:
                logger.warning(f"Invalid webhook signature. Expected: {expected_signature[:20]}..., Got: {signature[:20]}...")
            
            return is_valid
            
        except Exception as e:
            logger.error(f"Signature verification failed: {str(e)}")
            return False
    
    def create_invoice(self, amount_usd, currency='usd', description=None, order_id=None, user_id=None):
        """
        Create a NOWPayments invoice with idempotency key
        
        Args:
            amount_usd (Decimal): Amount in USD
            currency (str): Cryptocurrency to receive (btc, eth, usdt, etc.)
            description (str): Invoice description
            order_id (str): Custom order ID (will be auto-generated if None)
            user_id (int): User ID for tracking
        
        Returns:
            dict: Invoice data or None if failed
        """
        if not self.api_key:
            logger.error("NOWPayments API key not configured")
            return None
        
        if order_id is None:
            # Create unique order ID with timestamp and user reference
            timestamp = int(timezone.now().timestamp())
            user_part = f"user_{user_id}" if user_id else "guest"
            order_id = f"{user_part}_{timestamp}_{uuid.uuid4().hex[:8]}"
        
        url = f"{self.base_url}/invoice"
        
        # Get frontend and backend URLs with fallbacks
        frontend_url = getattr(settings, 'FRONTEND_URL', 'https://novaedgefinance.com')
        site_url = getattr(settings, 'SITE_URL', 'https://api.novaedgefinance.com')
        
        # Build payload with all required fields
        payload = {
            'price_amount': float(amount_usd),
            'price_currency': 'usd',
            'pay_currency': currency.lower(),
            'ipn_callback_url': f"{site_url}/api/wallet/nowpayments-webhook/",
            'order_id': order_id,
            'order_description': description or f"Deposit of ${amount_usd}",
            'success_url': f"{frontend_url}/dashboard/wallet?deposit=success",
            'cancel_url': f"{frontend_url}/dashboard/wallet?deposit=cancel",
            'is_fee_paid_by_user': True,  # Network fees are paid by user
        }
        
        # Add optional fields if configured
        if hasattr(settings, 'NOWPAYMENTS_PARTNER_ID'):
            payload['partner_id'] = settings.NOWPAYMENTS_PARTNER_ID
        
        try:
            response = requests.post(
                url,
                headers=self.get_headers(),
                json=payload,
                timeout=30
            )
            
            if response.status_code == 201:
                data = response.json()
                logger.info(f"NOWPayments invoice created: {data.get('id')} for order: {order_id}")
                
                # Enhance response with additional useful fields
                enhanced_data = {
                    'id': data.get('id'),
                    'invoice_id': data.get('invoice_id'),
                    'invoice_url': data.get('invoice_url'),
                    'pay_address': data.get('pay_address'),
                    'pay_amount': Decimal(str(data.get('pay_amount', 0))),
                    'pay_currency': data.get('pay_currency', currency).upper(),
                    'price_amount': Decimal(str(data.get('price_amount', amount_usd))),
                    'price_currency': data.get('price_currency', 'usd').upper(),
                    'exchange_rate': Decimal(str(data.get('exchange_rate', 0))),
                    'expires_at': data.get('expires_at'),
                    'qr_code_url': data.get('qr_code_url'),
                    'order_id': order_id,
                    'status': data.get('payment_status', 'waiting')
                }
                return enhanced_data
            else:
                logger.error(f"NOWPayments API error: {response.status_code} - {response.text}")
                return None
                
        except requests.RequestException as e:
            logger.error(f"NOWPayments API request failed: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error creating invoice: {str(e)}")
            return None
    
    def get_payment_status(self, payment_id):
        """
        Get payment status from NOWPayments
        
        Args:
            payment_id (str): NOWPayments payment ID
        
        Returns:
            dict: Payment status data or None if failed
        """
        if not self.api_key:
            logger.error("NOWPayments API key not configured")
            return None
        
        if not payment_id:
            logger.error("Payment ID is required")
            return None
        
        url = f"{self.base_url}/payment/{payment_id}"
        
        try:
            response = requests.get(
                url,
                headers=self.get_headers(),
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                logger.debug(f"Payment status for {payment_id}: {data.get('payment_status')}")
                return data
            elif response.status_code == 404:
                logger.warning(f"Payment {payment_id} not found")
                return None
            else:
                logger.error(f"NOWPayments status check failed: {response.status_code}")
                return None
                
        except requests.RequestException as e:
            logger.error(f"NOWPayments status check request failed: {str(e)}")
            return None
    
    def get_estimated_amount(self, amount_usd, currency):
        """
        Get estimated amount in cryptocurrency
        
        Args:
            amount_usd (Decimal): Amount in USD
            currency (str): Target cryptocurrency
        
        Returns:
            dict: Estimated amount data or None if failed
        """
        if not self.api_key:
            logger.error("NOWPayments API key not configured")
            return self._get_fallback_estimate(amount_usd, currency)
        
        url = f"{self.base_url}/estimate"
        
        params = {
            'amount': float(amount_usd),
            'currency_from': 'usd',
            'currency_to': currency.lower()
        }
        
        try:
            response = requests.get(
                url,
                headers=self.get_headers(),
                params=params,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'estimated_amount': Decimal(str(data.get('estimated_amount', 0))),
                    'estimated_rate': Decimal(str(data.get('exchange_rate', 0))),
                    'currency': currency.upper()
                }
            else:
                logger.error(f"NOWPayments estimate failed: {response.status_code} - using fallback")
                return self._get_fallback_estimate(amount_usd, currency)
                
        except requests.RequestException as e:
            logger.error(f"NOWPayments estimate request failed: {str(e)} - using fallback")
            return self._get_fallback_estimate(amount_usd, currency)
    
    def _get_fallback_estimate(self, amount_usd, currency):
        """
        Fallback method to estimate crypto amounts when API is unavailable
        Uses approximate market rates
        """
        # Approximate rates as of 2024 (update periodically)
        fallback_rates = {
            'btc': 0.000015,   # 1 USD ≈ 0.000015 BTC
            'eth': 0.0003,      # 1 USD ≈ 0.0003 ETH
            'usdt': 1.0,        # 1 USD = 1 USDT
            'usdc': 1.0,        # 1 USD = 1 USDC
            'busd': 1.0,        # 1 USD = 1 BUSD
            'dai': 1.0,         # 1 USD = 1 DAI
            'ltc': 0.0015,      # 1 USD ≈ 0.0015 LTC
            'xrp': 1.8,         # 1 USD ≈ 1.8 XRP
            'ada': 2.5,         # 1 USD ≈ 2.5 ADA
            'dot': 0.15,        # 1 USD ≈ 0.15 DOT
            'matic': 2.2,       # 1 USD ≈ 2.2 MATIC
            'sol': 0.012,       # 1 USD ≈ 0.012 SOL
            'bnb': 0.002,       # 1 USD ≈ 0.002 BNB
        }
        
        currency_lower = currency.lower()
        rate = fallback_rates.get(currency_lower, 1.0)
        
        estimated = float(amount_usd) * rate
        
        logger.info(f"Using fallback rate for {currency}: {rate} (estimated: {estimated})")
        
        return {
            'estimated_amount': Decimal(str(estimated)),
            'estimated_rate': Decimal(str(rate)),
            'currency': currency.upper(),
            'fallback': True
        }
    
    def get_minimum_payment_amount(self, currency):
        """
        Get minimum payment amount for a currency
        
        Args:
            currency (str): Cryptocurrency
        
        Returns:
            Decimal: Minimum amount or None if failed
        """
        if not self.api_key:
            logger.error("NOWPayments API key not configured")
            return None
        
        url = f"{self.base_url}/min-amount"
        
        params = {
            'currency_from': 'usd',
            'currency_to': currency.lower()
        }
        
        try:
            response = requests.get(
                url,
                headers=self.get_headers(),
                params=params,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                return Decimal(str(data.get('min_amount', 0)))
            else:
                logger.error(f"NOWPayments min amount check failed: {response.status_code}")
                return None
                
        except requests.RequestException as e:
            logger.error(f"NOWPayments min amount request failed: {str(e)}")
            return None
    
    def get_available_currencies(self):
        """
        Get list of available currencies
        
        Returns:
            list: Available currencies or None if failed
        """
        if not self.api_key:
            logger.error("NOWPayments API key not configured")
            return None
        
        url = f"{self.base_url}/currencies"
        
        try:
            response = requests.get(
                url,
                headers=self.get_headers(),
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get('currencies', [])
            else:
                logger.error(f"NOWPayments currencies check failed: {response.status_code}")
                return None
                
        except requests.RequestException as e:
            logger.error(f"NOWPayments currencies request failed: {str(e)}")
            return None


def process_webhook_with_idempotency(payment_id, payload, signature, request=None):
    """
    Process webhook with idempotency protection and replay attack prevention
    
    Args:
        payment_id (str): NOWPayments payment ID
        payload (dict): Webhook payload
        signature (str): Signature from headers
        request (HttpRequest): Original request object
    
    Returns:
        dict: Processing result with status and details
    """
    from wallet.models import WebhookLog, Deposit
    from django.db import transaction
    
    # Create webhook log entry for idempotency
    webhook_log = WebhookLog.objects.create(
        payment_id=payment_id,
        raw_payload=payload,
        signature=signature,
        headers=dict(request.headers) if request and hasattr(request, 'headers') else {}
    )
    
    try:
        # Check if this payment has already been processed successfully
        existing_deposit = Deposit.objects.filter(payment_id=payment_id).first()
        
        if existing_deposit:
            if existing_deposit.status in [
                Deposit.PaymentStatus.CONFIRMED, 
                Deposit.PaymentStatus.FINISHED,
                Deposit.PaymentStatus.SENDING
            ]:
                logger.info(f"Payment {payment_id} already processed with status {existing_deposit.status} - ignoring duplicate webhook")
                webhook_log.mark_processed()
                return {
                    'status': 'ignored', 
                    'reason': 'already_processed',
                    'deposit_id': str(existing_deposit.deposit_id)
                }
        
        # Verify signature (required for security)
        client = NOWPaymentsClient()
        
        # Convert payload to bytes for signature verification
        if isinstance(payload, dict):
            # Sort keys to ensure consistent JSON stringification
            payload_str = json.dumps(payload, sort_keys=True, separators=(',', ':'))
            payload_bytes = payload_str.encode('utf-8')
        else:
            payload_bytes = payload
        
        if not client.verify_webhook_signature(payload_bytes, signature):
            webhook_log.signature_valid = False
            webhook_log.save()
            logger.error(f"Invalid signature for payment {payment_id}")
            return {'status': 'rejected', 'reason': 'invalid_signature'}
        
        webhook_log.signature_valid = True
        webhook_log.save()
        
        # Process the webhook atomically
        with transaction.atomic():
            # Extract data from payload
            payment_status = payload.get('payment_status', 'waiting').upper()
            pay_amount = Decimal(str(payload.get('pay_amount', 0)))
            pay_currency = payload.get('pay_currency', '').upper()
            price_amount = Decimal(str(payload.get('price_amount', 0)))
            actually_paid = Decimal(str(payload.get('actually_paid', 0)))
            
            # Try to extract user_id from order_id if it contains user reference
            order_id = payload.get('order_id', '')
            user_id = None
            
            if 'user_' in order_id:
                try:
                    # Extract user ID from format like "user_123_timestamp_hash"
                    user_part = order_id.split('_')[1]
                    if user_part.isdigit():
                        user_id = int(user_part)
                except (IndexError, ValueError):
                    pass
            
            # Try to find existing deposit by payment_id
            deposit, created = Deposit.objects.get_or_create(
                payment_id=payment_id,
                defaults={
                    'user_id': user_id,
                    'pay_currency': pay_currency,
                    'pay_amount': pay_amount,
                    'usd_amount': price_amount,
                    'status': Deposit.PaymentStatus.WAITING,
                    'payment_details': payload
                }
            )
            
            # If deposit exists but no user assigned, try to assign
            if not created and not deposit.user_id and user_id:
                deposit.user_id = user_id
                deposit.save(update_fields=['user_id'])
            
            # Store old status for transition tracking
            old_status = deposit.status
            
            # Map NOWPayments status to our status enum
            status_mapping = {
                'WAITING': Deposit.PaymentStatus.WAITING,
                'CONFIRMING': Deposit.PaymentStatus.CONFIRMING,
                'CONFIRMED': Deposit.PaymentStatus.CONFIRMED,
                'SENDING': Deposit.PaymentStatus.SENDING,
                'FINISHED': Deposit.PaymentStatus.FINISHED,
                'FAILED': Deposit.PaymentStatus.FAILED,
                'REFUNDED': Deposit.PaymentStatus.REFUNDED,
                'EXPIRED': Deposit.PaymentStatus.EXPIRED,
                'PARTIALLY_PAID': Deposit.PaymentStatus.PARTIALLY_PAID,
            }
            
            new_status = status_mapping.get(payment_status, Deposit.PaymentStatus.WAITING)
            
            # Update deposit with new data
            deposit.status = new_status
            deposit.pay_amount = pay_amount
            deposit.pay_currency = pay_currency
            deposit.usd_amount = price_amount
            deposit.payment_details = payload
            
            # Update exchange rate if provided
            if 'exchange_rate' in payload:
                deposit.exchange_rate = Decimal(str(payload['exchange_rate']))
            
            # Update actual paid amount if available
            if actually_paid > 0:
                deposit.actually_paid = actually_paid
            
            deposit.save()
            
            # Process if payment is confirmed (and not previously processed)
            if new_status in [Deposit.PaymentStatus.CONFIRMED, Deposit.PaymentStatus.FINISHED]:
                if old_status not in [Deposit.PaymentStatus.CONFIRMED, Deposit.PaymentStatus.FINISHED]:
                    # This is a new confirmation
                    deposit.process_confirmation()
                    
                    # Trigger referral bonus if this is the user's first deposit
                    if deposit.user:
                        try:
                            from referrals.utils import process_referral_on_deposit
                            process_referral_on_deposit(deposit.user, deposit.usd_amount)
                        except ImportError:
                            logger.debug("Referral app not installed")
                        except Exception as e:
                            logger.error(f"Error processing referral for deposit {deposit.deposit_id}: {str(e)}")
                    
                    logger.info(f"Deposit {deposit.deposit_id} processed successfully for user {deposit.user_id}")
            
            # Handle partial payments
            elif new_status == Deposit.PaymentStatus.PARTIALLY_PAID:
                logger.info(f"Partial payment received for deposit {deposit.deposit_id}: {actually_paid}/{pay_amount}")
            
            # Handle failures
            elif new_status in [Deposit.PaymentStatus.FAILED, Deposit.PaymentStatus.EXPIRED]:
                logger.info(f"Deposit {deposit.deposit_id} {new_status}")
            
            webhook_log.mark_processed()
            
        return {
            'status': 'processed',
            'deposit_id': str(deposit.deposit_id),
            'new_status': new_status,
            'old_status': old_status
        }
        
    except Exception as e:
        webhook_log.mark_failed(str(e))
        logger.error(f"Error processing webhook for payment {payment_id}: {str(e)}", exc_info=True)
        raise


def calculate_investment_growth(investment):
    """
    Calculate growth data for an investment for chart display
    
    Args:
        investment: UserInvestment instance
    
    Returns:
        dict: Growth data with labels and values
    """
    try:
        from investments.models import UserInvestment
    except ImportError:
        logger.warning("Investments app not installed")
        return {
            'labels': [],
            'values': [],
            'principal': 0,
            'current_value': 0,
            'profit': 0
        }
    
    growth_data = {
        'labels': [],
        'values': [],
        'principal': float(investment.principal_amount),
        'current_value': float(investment.current_value),
        'profit': float(investment.total_profit)
    }
    
    if investment.status != UserInvestment.InvestmentStatus.ACTIVE:
        # Return just current value for non-active investments
        growth_data['values'] = [float(investment.current_value)]
        growth_data['labels'] = [investment.updated_at.strftime('%Y-%m-%d')]
        return growth_data
    
    # Calculate daily growth for the investment period
    start_date = investment.start_date
    end_date = min(timezone.now(), investment.end_date) if investment.end_date else timezone.now()
    
    # Generate data points (max 30 points for chart)
    total_days = (end_date - start_date).days
    if total_days <= 0:
        growth_data['values'] = [float(investment.principal_amount)]
        growth_data['labels'] = [start_date.strftime('%Y-%m-%d')]
        return growth_data
    
    # Determine number of points (max 30 for performance)
    num_points = min(total_days, 30)
    days_per_point = max(1, total_days // num_points)
    
    for i in range(0, total_days + 1, days_per_point):
        date_point = start_date + timedelta(days=i)
        
        # Calculate value for this day
        try:
            daily_rate = float(investment.plan.calculate_daily_return_rate())
            profit = float(investment.principal_amount) * daily_rate * i
        except (AttributeError, TypeError):
            # Fallback if plan method doesn't exist
            profit = float(investment.principal_amount) * 0.01 * i  # 1% daily as fallback
        
        # Apply max return multiplier if set
        if investment.expected_return_multiplier:
            max_profit = float(investment.principal_amount) * (float(investment.expected_return_multiplier) / 100)
            profit = min(profit, max_profit)
        
        value = float(investment.principal_amount) + profit
        
        growth_data['labels'].append(date_point.strftime('%Y-%m-%d'))
        growth_data['values'].append(round(value, 2))
    
    return growth_data


def update_all_active_investments():
    """
    Update current value for all active investments
    Scheduled task to run periodically (e.g., every hour)
    
    Returns:
        int: Number of updated investments
    """
    try:
        from investments.models import UserInvestment
        
        active_investments = UserInvestment.objects.filter(
            status=UserInvestment.InvestmentStatus.ACTIVE
        ).select_related('plan')
        
        updated_count = 0
        errors_count = 0
        
        for investment in active_investments:
            try:
                investment.update_current_value()
                updated_count += 1
                
                # Log every 100th investment for monitoring
                if updated_count % 100 == 0:
                    logger.info(f"Updated {updated_count} active investments so far")
                    
            except Exception as e:
                errors_count += 1
                logger.error(f"Failed to update investment {investment.investment_id}: {str(e)}")
        
        logger.info(f"Investment update completed: {updated_count} updated, {errors_count} errors")
        return updated_count
        
    except ImportError:
        logger.warning("Investments app not installed")
        return 0
    except Exception as e:
        logger.error(f"Error in update_all_active_investments: {str(e)}")
        return 0


def check_expired_deposits():
    """
    Check and mark expired deposits
    Scheduled task to run periodically
    
    Returns:
        int: Number of expired deposits marked
    """
    from wallet.models import Deposit
    
    # Define expiration time (e.g., 24 hours for waiting deposits)
    expiration_hours = getattr(settings, 'DEPOSIT_EXPIRATION_HOURS', 24)
    expiration_time = timezone.now() - timedelta(hours=expiration_hours)
    
    expired_deposits = Deposit.objects.filter(
        status=Deposit.PaymentStatus.WAITING,
        created_at__lt=expiration_time
    )
    
    count = expired_deposits.update(
        status=Deposit.PaymentStatus.EXPIRED,
        payment_details=models.F('payment_details')  # Preserve existing details
    )
    
    if count > 0:
        logger.info(f"Marked {count} deposits as expired")
    
    return count


def get_deposit_statistics():
    """
    Get deposit statistics for admin dashboard
    
    Returns:
        dict: Deposit statistics
    """
    from wallet.models import Deposit
    from django.db.models import Count, Sum
    
    today = timezone.now().date()
    start_of_month = today.replace(day=1)
    
    stats = {
        'total_deposits': Deposit.objects.count(),
        'total_amount': Deposit.objects.aggregate(total=Sum('usd_amount'))['total'] or 0,
        'today_deposits': Deposit.objects.filter(created_at__date=today).count(),
        'today_amount': Deposit.objects.filter(created_at__date=today).aggregate(
            total=Sum('usd_amount')
        )['total'] or 0,
        'month_deposits': Deposit.objects.filter(created_at__date__gte=start_of_month).count(),
        'month_amount': Deposit.objects.filter(created_at__date__gte=start_of_month).aggregate(
            total=Sum('usd_amount')
        )['total'] or 0,
        'status_breakdown': list(Deposit.objects.values('status').annotate(
            count=Count('id'),
            total=Sum('usd_amount')
        ))
    }
    
    return stats


def verify_nowpayments_configuration():
    """
    Verify NOWPayments configuration and connectivity
    
    Returns:
        dict: Configuration status
    """
    client = NOWPaymentsClient()
    
    status = {
        'api_key_configured': bool(client.api_key),
        'ipn_secret_configured': bool(client.ipn_secret),
        'api_connectivity': False,
        'currencies_available': False,
        'errors': []
    }
    
    # Test API connectivity
    if client.api_key:
        try:
            currencies = client.get_available_currencies()
            if currencies:
                status['api_connectivity'] = True
                status['currencies_available'] = True
                status['currency_count'] = len(currencies)
        except Exception as e:
            status['errors'].append(f"API connectivity test failed: {str(e)}")
    else:
        status['errors'].append("API key not configured")
    
    if not client.ipn_secret:
        status['errors'].append("IPN secret not configured - webhooks will be rejected")
    
    return status