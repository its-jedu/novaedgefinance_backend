import logging
import csv
import json
import io
from datetime import datetime, timedelta
from decimal import Decimal
from django.utils import timezone
from django.db.models import Sum, Count, Avg, Q
import pandas as pd

logger = logging.getLogger(__name__)

def log_ledger_entry(user, transaction_type, amount, balance_before, 
                     balance_after, source_app, reference_id, 
                     description, metadata=None, request=None):
    """
    Create a ledger entry for financial transaction
    """
    try:
        from .models import LedgerEntry
        
        entry = LedgerEntry.objects.create(
            user=user,
            transaction_type=transaction_type,
            amount=amount,
            balance_before=balance_before,
            balance_after=balance_after,
            source_app=source_app,
            reference_id=reference_id,
            description=description,
            metadata=metadata or {},
            ip_address=request.META.get('REMOTE_ADDR') if request else None,
            user_agent=request.META.get('HTTP_USER_AGENT', '') if request else ''
        )
        
        logger.info(f"Ledger entry created: {entry.ledger_id}")
        return entry
        
    except Exception as e:
        logger.error(f"Error creating ledger entry: {str(e)}")
        return None


def log_audit_action(admin, action, target_object, target_model='', 
                     target_id='', changes_before=None, changes_after=None,
                     request=None):
    """
    Log admin audit action
    """
    try:
        from .models import AuditLog
        
        changes_summary = ""
        if changes_before and changes_after:
            changes_summary = f"Changed fields: {', '.join(changes_after.keys())}"
        
        audit_log = AuditLog.objects.create(
            admin=admin,
            action=action,
            target_object=target_object,
            target_model=target_model,
            target_id=target_id,
            changes_before=changes_before or {},
            changes_after=changes_after or {},
            changes_summary=changes_summary,
            ip_address=request.META.get('REMOTE_ADDR') if request else '0.0.0.0',
            user_agent=request.META.get('HTTP_USER_AGENT', '') if request else '',
            request_path=request.path if request else ''
        )
        
        logger.info(f"Audit log created: {audit_log.audit_id}")
        return audit_log
        
    except Exception as e:
        logger.error(f"Error creating audit log: {str(e)}")
        return None


def log_user_activity(user, activity_type, description, request=None, **kwargs):
    """
    Log user activity
    """
    try:
        from .models import UserActivityLog
        
        # Extract device info from user agent
        user_agent = request.META.get('HTTP_USER_AGENT', '') if request else ''
        device_info = extract_device_info(user_agent)
        
        activity = UserActivityLog.objects.create(
            user=user,
            activity_type=activity_type,
            description=description,
            page_url=kwargs.get('page_url', ''),
            referrer_url=kwargs.get('referrer_url', ''),
            session_id=kwargs.get('session_id', ''),
            ip_address=request.META.get('REMOTE_ADDR') if request else None,
            user_agent=user_agent,
            device_type=device_info.get('device_type', ''),
            browser=device_info.get('browser', ''),
            operating_system=device_info.get('os', ''),
            country=kwargs.get('country', ''),
            city=kwargs.get('city', ''),
            metadata=kwargs.get('metadata', {})
        )
        
        return activity
        
    except Exception as e:
        logger.error(f"Error logging user activity: {str(e)}")
        return None


def extract_device_info(user_agent):
    """
    Extract device information from user agent string
    """
    info = {
        'device_type': 'Desktop',
        'browser': 'Unknown',
        'os': 'Unknown'
    }
    
    if not user_agent:
        return info
    
    user_agent = user_agent.lower()
    
    # Detect device type
    if 'mobile' in user_agent:
        info['device_type'] = 'Mobile'
    elif 'tablet' in user_agent:
        info['device_type'] = 'Tablet'
    
    # Detect browser
    if 'chrome' in user_agent and 'chromium' not in user_agent:
        info['browser'] = 'Chrome'
    elif 'firefox' in user_agent:
        info['browser'] = 'Firefox'
    elif 'safari' in user_agent and 'chrome' not in user_agent:
        info['browser'] = 'Safari'
    elif 'edge' in user_agent:
        info['browser'] = 'Edge'
    elif 'opera' in user_agent:
        info['browser'] = 'Opera'
    
    # Detect OS
    if 'windows' in user_agent:
        info['os'] = 'Windows'
    elif 'mac' in user_agent:
        info['os'] = 'macOS'
    elif 'linux' in user_agent:
        info['os'] = 'Linux'
    elif 'android' in user_agent:
        info['os'] = 'Android'
    elif 'ios' in user_agent or 'iphone' in user_agent:
        info['os'] = 'iOS'
    
    return info


def generate_daily_summary(date=None):
    """
    Generate daily financial summary
    """
    try:
        if date is None:
            date = timezone.now().date()
        
        date_start = timezone.make_aware(datetime.combine(date, datetime.min.time()))
        date_end = timezone.make_aware(datetime.combine(date, datetime.max.time()))
        
        from .models import LedgerEntry
        
        # Get daily transactions
        daily_transactions = LedgerEntry.objects.filter(
            created_at__range=[date_start, date_end]
        )
        
        summary = {
            'date': date.isoformat(),
            'total_transactions': daily_transactions.count(),
            'total_deposits': daily_transactions.filter(
                transaction_type='DEPOSIT'
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00'),
            'total_withdrawals': daily_transactions.filter(
                transaction_type='WITHDRAWAL'
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00'),
            'total_investments': daily_transactions.filter(
                transaction_type='INVESTMENT'
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00'),
            'total_profits': daily_transactions.filter(
                transaction_type='PROFIT'
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00'),
            'total_referral_bonuses': daily_transactions.filter(
                transaction_type='REFERRAL_BONUS'
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00'),
            'unique_users': daily_transactions.values('user').distinct().count(),
            'top_transactions': list(daily_transactions.order_by('-amount')[:10].values(
                'ledger_id', 'user__email', 'transaction_type', 'amount', 'description'
            ))
        }
        
        return summary
        
    except Exception as e:
        logger.error(f"Error generating daily summary: {str(e)}")
        return None


def generate_user_transaction_history(user, start_date=None, end_date=None):
    """
    Generate transaction history for a user
    """
    try:
        from .models import LedgerEntry
        
        query = LedgerEntry.objects.filter(user=user)
        
        if start_date:
            query = query.filter(created_at__date__gte=start_date)
        
        if end_date:
            query = query.filter(created_at__date__lte=end_date)
        
        transactions = query.order_by('-created_at')
        
        history = []
        for tx in transactions:
            history.append({
                'date': tx.created_at.date().isoformat(),
                'datetime': tx.created_at.isoformat(),
                'transaction_type': tx.transaction_type,
                'amount': tx.amount,
                'balance_before': tx.balance_before,
                'balance_after': tx.balance_after,
                'description': tx.description,
                'reference_id': tx.reference_id,
                'is_verified': tx.is_verified,
                'source_app': tx.source_app
            })
        
        return history
        
    except Exception as e:
        logger.error(f"Error generating transaction history: {str(e)}")
        return []


def export_to_csv(data, filename=None):
    """
    Export data to CSV format
    """
    try:
        if not data:
            return None
        
        output = io.StringIO()
        
        # Determine fieldnames
        if isinstance(data, list) and data:
            fieldnames = data[0].keys()
        else:
            fieldnames = data.keys()
        
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        
        if isinstance(data, list):
            writer.writerows(data)
        else:
            writer.writerow(data)
        
        csv_content = output.getvalue()
        output.close()
        
        return csv_content
        
    except Exception as e:
        logger.error(f"Error exporting to CSV: {str(e)}")
        return None


def export_to_excel(data, sheet_name='Data'):
    """
    Export data to Excel format
    """
    try:
        if not data:
            return None
        
        # Convert to pandas DataFrame
        if isinstance(data, list):
            df = pd.DataFrame(data)
        else:
            df = pd.DataFrame([data])
        
        # Create Excel writer
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name=sheet_name, index=False)
        
        excel_content = output.getvalue()
        output.close()
        
        return excel_content
        
    except Exception as e:
        logger.error(f"Error exporting to Excel: {str(e)}")
        return None


def calculate_financial_summary(start_date=None, end_date=None):
    """
    Calculate comprehensive financial summary
    """
    try:
        from .models import LedgerEntry
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        # Base queries
        ledger_query = LedgerEntry.objects.all()
        if start_date:
            ledger_query = ledger_query.filter(created_at__date__gte=start_date)
        if end_date:
            ledger_query = ledger_query.filter(created_at__date__lte=end_date)
        
        # Calculate totals
        summary = {
            'period': {
                'start_date': start_date.isoformat() if start_date else None,
                'end_date': end_date.isoformat() if end_date else None
            },
            'totals': {
                'deposits': ledger_query.filter(
                    transaction_type='DEPOSIT'
                ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00'),
                'withdrawals': ledger_query.filter(
                    transaction_type='WITHDRAWAL'
                ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00'),
                'investments': ledger_query.filter(
                    transaction_type='INVESTMENT'
                ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00'),
                'profits': ledger_query.filter(
                    transaction_type='PROFIT'
                ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00'),
                'referral_bonuses': ledger_query.filter(
                    transaction_type='REFERRAL_BONUS'
                ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00'),
                'fees': ledger_query.filter(
                    transaction_type='FEE'
                ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            },
            'user_stats': {
                'total_users': User.objects.count(),
                'active_users': User.objects.filter(is_active=True).count(),
                'verified_users': User.objects.filter(
                    is_verified=True, email_verified=True
                ).count(),
                'new_users': User.objects.filter(
                    created_at__date__gte=start_date
                ).count() if start_date else 0
            },
            'transaction_stats': {
                'total_transactions': ledger_query.count(),
                'verified_transactions': ledger_query.filter(is_verified=True).count(),
                'average_transaction_size': ledger_query.aggregate(
                    avg=Avg('amount')
                )['avg'] or Decimal('0.00')
            }
        }
        
        # Calculate net flow
        summary['totals']['net_flow'] = (
            summary['totals']['deposits'] + 
            summary['totals']['profits'] + 
            summary['totals']['referral_bonuses']
        ) - (
            summary['totals']['withdrawals'] + 
            summary['totals']['investments'] +
            summary['totals']['fees']
        )
        
        return summary
        
    except Exception as e:
        logger.error(f"Error calculating financial summary: {str(e)}")
        return None


def check_system_health():
    """
    Perform system health check
    """
    try:
        from .models import SystemHealthCheck
        
        checks = []
        
        # Database check
        try:
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            db_status = 'HEALTHY'
            db_response_time = 10  # ms
        except Exception as e:
            db_status = 'UNHEALTHY'
            db_response_time = 0
            logger.error(f"Database check failed: {str(e)}")
        
        checks.append({
            'check_type': 'DATABASE',
            'status': db_status,
            'response_time': db_response_time,
            'success_rate': 100 if db_status == 'HEALTHY' else 0
        })
        
        # Cache check
        try:
            from django.core.cache import cache
            start = timezone.now()
            cache.set('health_check', 'ok', 10)
            cached = cache.get('health_check')
            end = timezone.now()
            
            cache_response_time = (end - start).total_seconds() * 1000  # ms
            cache_status = 'HEALTHY' if cached == 'ok' else 'UNHEALTHY'
        except Exception as e:
            cache_status = 'UNHEALTHY'
            cache_response_time = 0
            logger.error(f"Cache check failed: {str(e)}")
        
        checks.append({
            'check_type': 'CACHE',
            'status': cache_status,
            'response_time': cache_response_time,
            'success_rate': 100 if cache_status == 'HEALTHY' else 0
        })
        
        # Save checks
        for check_data in checks:
            SystemHealthCheck.objects.create(**check_data)
        
        # Overall status
        overall_status = 'HEALTHY'
        for check in checks:
            if check['status'] != 'HEALTHY':
                overall_status = 'DEGRADED'
                break
        
        return {
            'overall_status': overall_status,
            'checks': checks,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"System health check failed: {str(e)}")
        return None

