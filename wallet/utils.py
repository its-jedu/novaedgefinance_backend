import hashlib
import hmac
import json
import requests
from django.conf import settings
from django.utils import timezone
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

class NOWPaymentsClient:
    """
    Client for NOWPayments API integration
    """
    
    def __init__(self):
        self.api_key = getattr(settings, 'NOWPAYMENTS_API_KEY', '')
        self.secret_key = getattr(settings, 'NOWPAYMENTS_SECRET_KEY', '')
        self.base_url = getattr(settings, 'NOWPAYMENTS_BASE_URL', 'https://api.nowpayments.io/v1')
        
    def get_headers(self):
        """Get API headers with authentication"""
        return {
            'x-api-key': self.api_key,
            'Content-Type': 'application/json'
        }
    
    def create_invoice(self, amount_usd, currency='usd', description=None):
        """
        Create a NOWPayments invoice
        
        Args:
            amount_usd: Amount in USD
            currency: Payment currency (BTC, ETH, etc.)
            description: Invoice description
        
        Returns:
            dict: Invoice response
        """
        if not self.api_key:
            logger.error("NOWPayments API key not configured")
            return None
        
        url = f"{self.base_url}/invoice"
        
        payload = {
            'price_amount': float(amount_usd),
            'price_currency': 'usd',
            'pay_currency': currency.lower(),
            'ipn_callback_url': f"{settings.SITE_URL}/api/wallet/nowpayments-webhook/",
            'order_id': f"deposit_{int(timezone.now().timestamp())}",
            'order_description': description or f"Deposit of ${amount_usd}",
            'success_url': f"{settings.FRONTEND_URL}/deposit/success",
            'cancel_url': f"{settings.FRONTEND_URL}/deposit/cancel"
        }
        
        try:
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
        
        Args:
            payment_id: NOWPayments payment ID
        
        Returns:
            dict: Payment status response
        """
        if not self.api_key:
            logger.error("NOWPayments API key not configured")
            return None
        
        url = f"{self.base_url}/payment/{payment_id}"
        
        try:
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
        
        Args:
            amount_usd: Amount in USD
            currency: Target cryptocurrency
        
        Returns:
            dict: Estimated amount response
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
    
    def verify_webhook_signature(self, payload, signature):
        """
        Verify NOWPayments webhook signature
        
        Args:
            payload: Raw request body
            signature: X-Nowpayments-Sig header value
        
        Returns:
            bool: True if signature is valid
        """
        if not self.secret_key:
            logger.warning("NOWPayments secret key not configured, skipping signature verification")
            return True
        
        try:
            # Create HMAC SHA512 hash
            expected_signature = hmac.new(
                self.secret_key.encode('utf-8'),
                payload,
                hashlib.sha512
            ).hexdigest()
            
            return hmac.compare_digest(expected_signature, signature)
            
        except Exception as e:
            logger.error(f"Signature verification failed: {str(e)}")
            return False


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
    import math
    
    start_date = investment.start_date.date()
    end_date = investment.end_date.date()
    current_date = min(timezone.now().date(), end_date)
    
    # Get number of days
    total_days = (end_date - start_date).days
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
            'value': value,
            'profit': profit
        })
    
    return growth_data


def update_all_active_investments():
    """
    Update current value for all active investments
    """
    from .models import UserInvestment
    
    active_investments = UserInvestment.objects.filter(
        status=UserInvestment.InvestmentStatus.ACTIVE
    )
    
    updated_count = 0
    for investment in active_investments:
        try:
            investment.update_current_value()
            updated_count += 1
        except Exception as e:
            logger.error(f"Failed to update investment {investment.id}: {str(e)}")
    
    logger.info(f"Updated {updated_count} active investments")
    return updated_count

