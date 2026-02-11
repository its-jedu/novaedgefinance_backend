from decimal import Decimal
from django.core.exceptions import ValidationError
from django.utils import timezone

def validate_positive_amount(value):
    """Validate that amount is positive"""
    if value <= 0:
        raise ValidationError(
            f'Amount must be positive, got {value}',
            params={'value': value},
        )

def validate_minimum_deposit(value):
    """Validate minimum deposit amount"""
    if value < Decimal('10.00'):
        raise ValidationError(
            f'Minimum deposit is $10.00, got ${value}',
            params={'value': value},
        )

def validate_maximum_deposit(value):
    """Validate maximum deposit amount"""
    if value > Decimal('10000.00'):
        raise ValidationError(
            f'Maximum deposit is $10,000.00, got ${value}',
            params={'value': value},
        )

def validate_investment_amount(value, min_amount, max_amount=None):
    """Validate investment amount against plan limits"""
    if value < min_amount:
        raise ValidationError(
            f'Minimum investment is ${min_amount}, got ${value}',
            params={'value': value, 'min_amount': min_amount},
        )
    
    if max_amount and value > max_amount:
        raise ValidationError(
            f'Maximum investment is ${max_amount}, got ${value}',
            params={'value': value, 'max_amount': max_amount},
        )