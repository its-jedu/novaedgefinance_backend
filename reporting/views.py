from django.shortcuts import render

# Create your views here.
from rest_framework import generics, views, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q, Sum, Count, Avg
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.http import HttpResponse
from decimal import Decimal
import logging

from .models import (
    LedgerEntry, AuditLog, FinancialReport,
    UserActivityLog, SystemHealthCheck
)
from .serializers import (
    LedgerEntrySerializer, AuditLogSerializer,
    FinancialReportSerializer, CreateReportSerializer,
    UserActivityLogSerializer, SystemHealthCheckSerializer,
    TransactionHistorySerializer, FinancialSummarySerializer,
    DateRangeSerializer, ExportFormatSerializer
)
from .permissions import IsOwnerOrAdmin, AdminOnly, CanViewReports
from .utils import (
    generate_daily_summary, generate_user_transaction_history,
    export_to_csv, export_to_excel, calculate_financial_summary,
    check_system_health
)

logger = logging.getLogger(__name__)


class MyTransactionHistoryView(generics.ListAPIView):
    """
    Get user's transaction history
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        try:
            # Get date range from query params
            start_date = request.query_params.get('start_date')
            end_date = request.query_params.get('end_date') or timezone.now().date()
            
            # Generate transaction history
            history = generate_user_transaction_history(
                user=request.user,
                start_date=start_date,
                end_date=end_date
            )
            
            # Convert to serializer format
            formatted_history = []
            for tx in history:
                formatted_history.append({
                    'date': tx['date'],
                    'transaction_type': tx['transaction_type'],
                    'amount': tx['amount'],
                    'description': tx['description'],
                    'balance_after': tx['balance_after']
                })
            
            serializer = TransactionHistorySerializer(formatted_history, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error getting transaction history: {str(e)}")
            return Response(
                {'error': 'Failed to get transaction history'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ExportMyTransactionsView(APIView):
    """
    Export user's transactions
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        serializer = ExportFormatSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        export_format = serializer.validated_data['format']
        include_summary = serializer.validated_data.get('include_summary', True)
        
        try:
            # Get date range from query params
            start_date = request.query_params.get('start_date')
            end_date = request.query_params.get('end_date') or timezone.now().date()
            
            # Get transaction history
            history = generate_user_transaction_history(
                user=request.user,
                start_date=start_date,
                end_date=end_date
            )
            
            if not history:
                return Response(
                    {'error': 'No transactions found for the selected period'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Prepare data for export
            export_data = []
            for tx in history:
                export_data.append({
                    'Date': tx['date'],
                    'Time': tx['datetime'].split('T')[1][:8] if 'T' in tx['datetime'] else '',
                    'Transaction Type': tx['transaction_type'],
                    'Amount (USD)': float(tx['amount']),
                    'Balance Before': float(tx['balance_before']),
                    'Balance After': float(tx['balance_after']),
                    'Description': tx['description'],
                    'Reference ID': tx['reference_id'],
                    'Verified': 'Yes' if tx['is_verified'] else 'No',
                    'Source': tx['source_app']
                })
            
            # Add summary if requested
            if include_summary:
                summary = {
                    'Total Transactions': len(history),
                    'Total Deposit Amount': sum(float(tx['amount']) for tx in history if tx['transaction_type'] == 'DEPOSIT'),
                    'Total Withdrawal Amount': sum(float(tx['amount']) for tx in history if tx['transaction_type'] == 'WITHDRAWAL'),
                    'Total Profit Amount': sum(float(tx['amount']) for tx in history if tx['transaction_type'] == 'PROFIT'),
                    'Period': f"{start_date} to {end_date}" if start_date else f"All time up to {end_date}",
                    'Generated At': timezone.now().isoformat()
                }
                export_data.append({})  # Empty row
                export_data.append({'--- SUMMARY ---': ''})
                for key, value in summary.items():
                    export_data.append({key: value})
            
            # Export based on format
            if export_format == 'csv':
                csv_content = export_to_csv(export_data)
                if csv_content:
                    response = HttpResponse(csv_content, content_type='text/csv')
                    filename = f'transactions_{request.user.email}_{timezone.now().date()}.csv'
                    response['Content-Disposition'] = f'attachment; filename="{filename}"'
                    return response
            
            elif export_format == 'excel':
                excel_content = export_to_excel(export_data, 'Transactions')
                if excel_content:
                    response = HttpResponse(
                        excel_content,
                        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                    )
                    filename = f'transactions_{request.user.email}_{timezone.now().date()}.xlsx'
                    response['Content-Disposition'] = f'attachment; filename="{filename}"'
                    return response
            
            elif export_format == 'json':
                return Response(export_data, status=status.HTTP_200_OK)
            
            else:
                return Response(
                    {'error': 'Unsupported export format'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
        except Exception as e:
            logger.error(f"Error exporting transactions: {str(e)}")
            return Response(
                {'error': 'Failed to export transactions'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class FinancialSummaryView(APIView):
    """
    Get financial summary
    """
    permission_classes = [IsAuthenticated, AdminOnly]
    
    def get(self, request):
        try:
            # Get date range from query params
            start_date = request.query_params.get('start_date')
            end_date = request.query_params.get('end_date') or timezone.now().date()
            
            # Calculate financial summary
            summary = calculate_financial_summary(start_date, end_date)
            
            if not summary:
                return Response(
                    {'error': 'Failed to calculate financial summary'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            # Format for serializer
            formatted_summary = {
                'total_deposits': summary['totals']['deposits'],
                'total_withdrawals': summary['totals']['withdrawals'],
                'total_investments': summary['totals']['investments'],
                'total_profits': summary['totals']['profits'],
                'total_referral_bonuses': summary['totals']['referral_bonuses'],
                'net_flow': summary['totals']['net_flow'],
                'active_users': summary['user_stats']['active_users'],
                'active_investments': 0,  # Would need investment app integration
                'pending_withdrawals': Decimal('0.00')  # Would need withdrawal tracking
            }
            
            serializer = FinancialSummarySerializer(formatted_summary)
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error getting financial summary: {str(e)}")
            return Response(
                {'error': 'Failed to get financial summary'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class DailySummaryView(APIView):
    """
    Get daily financial summary
    """
    permission_classes = [IsAuthenticated, AdminOnly]
    
    def get(self, request):
        try:
            # Get date from query params or use today
            date_str = request.query_params.get('date')
            if date_str:
                date = timezone.datetime.strptime(date_str, '%Y-%m-%d').date()
            else:
                date = timezone.now().date()
            
            summary = generate_daily_summary(date)
            
            if summary:
                return Response(summary, status=status.HTTP_200_OK)
            else:
                return Response(
                    {'error': 'Failed to generate daily summary'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
        except ValueError:
            return Response(
                {'error': 'Invalid date format. Use YYYY-MM-DD'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error getting daily summary: {str(e)}")
            return Response(
                {'error': 'Failed to get daily summary'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CreateReportView(APIView):
    """
    Create a new financial report
    """
    permission_classes = [IsAuthenticated, AdminOnly]
    
    def post(self, request):
        serializer = CreateReportSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Create report record
            report = FinancialReport.objects.create(
                generated_by=request.user,
                report_type=serializer.validated_data['report_type'],
                report_format=serializer.validated_data['report_format'],
                title=serializer.validated_data['title'],
                description=serializer.validated_data.get('description', ''),
                date_from=serializer.validated_data.get('date_from'),
                date_to=serializer.validated_data.get('date_to'),
                filters=serializer.validated_data.get('filters', {}),
                generation_started_at=timezone.now()
            )
            
            # Start report generation (in production, this would be a Celery task)
            self.generate_report_async(report)
            
            return Response({
                'message': 'Report generation started',
                'report_id': str(report.report_id),
                'status': 'PROCESSING'
            }, status=status.HTTP_202_ACCEPTED)
            
        except Exception as e:
            logger.error(f"Error creating report: {str(e)}")
            return Response(
                {'error': 'Failed to create report'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def generate_report_async(self, report):
        """Generate report asynchronously (simulated)"""
        import threading
        import time
        
        def generate():
            try:
                time.sleep(2)  # Simulate processing time
                
                # Generate report data based on type
                if report.report_type == FinancialReport.ReportType.DAILY_SUMMARY:
                    data = generate_daily_summary(report.date_to)
                elif report.report_type == FinancialReport.ReportType.USER_ACTIVITY:
                    data = self.generate_user_activity_report(report)
                else:
                    data = {'message': 'Report type not implemented yet'}
                
                # Complete report generation
                report.complete_generation(data)
                
            except Exception as e:
                logger.error(f"Error generating report: {str(e)}")
                report.mark_as_failed(str(e))
        
        # Start generation in background thread
        thread = threading.Thread(target=generate)
        thread.daemon = True
        thread.start()
    
    def generate_user_activity_report(self, report):
        """Generate user activity report"""
        from .models import UserActivityLog
        
        query = UserActivityLog.objects.all()
        
        if report.date_from:
            query = query.filter(created_at__date__gte=report.date_from)
        if report.date_to:
            query = query.filter(created_at__date__lte=report.date_to)
        
        activities = query.order_by('-created_at')[:1000]  # Limit to 1000 records
        
        data = []
        for activity in activities:
            data.append({
                'user': activity.user.email,
                'activity_type': activity.activity_type,
                'description': activity.description,
                'timestamp': activity.created_at.isoformat(),
                'ip_address': activity.ip_address,
                'device': activity.device_type,
                'browser': activity.browser,
                'country': activity.country
            })
        
        return data


class ReportListView(generics.ListAPIView):
    """
    List generated reports
    """
    permission_classes = [IsAuthenticated, AdminOnly]
    serializer_class = FinancialReportSerializer
    queryset = FinancialReport.objects.all().order_by('-created_at')
    
    def get_queryset(self):
        queryset = FinancialReport.objects.all()
        
        # Filter by report type
        report_type = self.request.query_params.get('type', None)
        if report_type:
            queryset = queryset.filter(report_type=report_type)
        
        # Filter by status
        is_generated = self.request.query_params.get('is_generated', None)
        if is_generated is not None:
            queryset = queryset.filter(is_generated=is_generated.lower() == 'true')
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date', None)
        end_date = self.request.query_params.get('end_date', None)
        
        if start_date:
            queryset = queryset.filter(created_at__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__date__lte=end_date)
        
        return queryset.order_by('-created_at')


class ReportDetailView(generics.RetrieveAPIView):
    """
    Get report details
    """
    permission_classes = [IsAuthenticated, AdminOnly]
    serializer_class = FinancialReportSerializer
    lookup_field = 'report_id'
    queryset = FinancialReport.objects.all()


class DownloadReportView(APIView):
    """
    Download generated report
    """
    permission_classes = [IsAuthenticated, AdminOnly]
    
    def get(self, request, report_id):
        try:
            report = get_object_or_404(FinancialReport, report_id=report_id)
            
            if not report.is_generated:
                return Response(
                    {'error': 'Report is not generated yet'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Check if report has download URL
            if report.download_url:
                return Response({
                    'download_url': report.download_url
                }, status=status.HTTP_200_OK)
            
            # Generate download based on format
            if report.report_format == FinancialReport.ReportFormat.JSON:
                return Response(report.report_data, status=status.HTTP_200_OK)
            
            elif report.report_format == FinancialReport.ReportFormat.CSV:
                csv_content = export_to_csv(report.report_data)
                if csv_content:
                    response = HttpResponse(csv_content, content_type='text/csv')
                    filename = f"{report.title}_{report.report_id}.csv"
                    response['Content-Disposition'] = f'attachment; filename="{filename}"'
                    return response
            
            elif report.report_format == FinancialReport.ReportFormat.EXCEL:
                excel_content = export_to_excel(report.report_data, report.title)
                if excel_content:
                    response = HttpResponse(
                        excel_content,
                        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                    )
                    filename = f"{report.title}_{report.report_id}.xlsx"
                    response['Content-Disposition'] = f'attachment; filename="{filename}"'
                    return response
            
            return Response(
                {'error': 'Report format not supported for download'},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        except FinancialReport.DoesNotExist:
            return Response(
                {'error': 'Report not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error downloading report: {str(e)}")
            return Response(
                {'error': 'Failed to download report'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# Admin Views

class AdminLedgerListView(generics.ListAPIView):
    """
    Admin: List all ledger entries
    """
    permission_classes = [IsAuthenticated, AdminOnly]
    serializer_class = LedgerEntrySerializer
    queryset = LedgerEntry.objects.all().order_by('-created_at')
    
    def get_queryset(self):
        queryset = LedgerEntry.objects.all()
        
        # Filter by user email
        user_email = self.request.query_params.get('user_email', None)
        if user_email:
            queryset = queryset.filter(user__email__icontains=user_email)
        
        # Filter by transaction type
        transaction_type = self.request.query_params.get('type', None)
        if transaction_type:
            queryset = queryset.filter(transaction_type=transaction_type)
        
        # Filter by source app
        source_app = self.request.query_params.get('source_app', None)
        if source_app:
            queryset = queryset.filter(source_app=source_app)
        
        # Filter by verification status
        is_verified = self.request.query_params.get('is_verified', None)
        if is_verified is not None:
            queryset = queryset.filter(is_verified=is_verified.lower() == 'true')
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date', None)
        end_date = self.request.query_params.get('end_date', None)
        
        if start_date:
            queryset = queryset.filter(created_at__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__date__lte=end_date)
        
        return queryset.order_by('-created_at')


class AdminVerifyLedgerEntryView(APIView):
    """
    Admin: Verify a ledger entry
    """
    permission_classes = [IsAuthenticated, AdminOnly]
    
    def post(self, request, ledger_id):
        try:
            ledger_entry = get_object_or_404(LedgerEntry, ledger_id=ledger_id)
            
            if ledger_entry.is_verified:
                return Response(
                    {'error': 'Ledger entry is already verified'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            notes = request.data.get('notes', '')
            ledger_entry.verify(request.user, notes)
            
            return Response({
                'message': 'Ledger entry verified successfully',
                'ledger_entry': LedgerEntrySerializer(ledger_entry).data
            }, status=status.HTTP_200_OK)
            
        except LedgerEntry.DoesNotExist:
            return Response(
                {'error': 'Ledger entry not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error verifying ledger entry: {str(e)}")
            return Response(
                {'error': 'Failed to verify ledger entry'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AdminAuditLogListView(generics.ListAPIView):
    """
    Admin: List all audit logs
    """
    permission_classes = [IsAuthenticated, AdminOnly]
    serializer_class = AuditLogSerializer
    queryset = AuditLog.objects.all().order_by('-created_at')
    
    def get_queryset(self):
        queryset = AuditLog.objects.all()
        
        # Filter by admin email
        admin_email = self.request.query_params.get('admin_email', None)
        if admin_email:
            queryset = queryset.filter(admin__email__icontains=admin_email)
        
        # Filter by action
        action = self.request.query_params.get('action', None)
        if action:
            queryset = queryset.filter(action=action)
        
        # Filter by target model
        target_model = self.request.query_params.get('target_model', None)
        if target_model:
            queryset = queryset.filter(target_model__icontains=target_model)
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date', None)
        end_date = self.request.query_params.get('end_date', None)
        
        if start_date:
            queryset = queryset.filter(created_at__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__date__lte=end_date)
        
        return queryset.order_by('-created_at')


class AdminUserActivityListView(generics.ListAPIView):
    """
    Admin: List user activities
    """
    permission_classes = [IsAuthenticated, AdminOnly]
    serializer_class = UserActivityLogSerializer
    queryset = UserActivityLog.objects.all().order_by('-created_at')
    
    def get_queryset(self):
        queryset = UserActivityLog.objects.all()
        
        # Filter by user email
        user_email = self.request.query_params.get('user_email', None)
        if user_email:
            queryset = queryset.filter(user__email__icontains=user_email)
        
        # Filter by activity type
        activity_type = self.request.query_params.get('activity_type', None)
        if activity_type:
            queryset = queryset.filter(activity_type=activity_type)
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date', None)
        end_date = self.request.query_params.get('end_date', None)
        
        if start_date:
            queryset = queryset.filter(created_at__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__date__lte=end_date)
        
        # Filter by IP address
        ip_address = self.request.query_params.get('ip_address', None)
        if ip_address:
            queryset = queryset.filter(ip_address=ip_address)
        
        return queryset.order_by('-created_at')


class AdminSystemHealthView(APIView):
    """
    Admin: Check system health
    """
    permission_classes = [IsAuthenticated, AdminOnly]
    
    def get(self, request):
        try:
            health_status = check_system_health()
            
            if health_status:
                return Response(health_status, status=status.HTTP_200_OK)
            else:
                return Response(
                    {'error': 'Failed to check system health'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
        except Exception as e:
            logger.error(f"Error checking system health: {str(e)}")
            return Response(
                {'error': 'Failed to check system health'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AdminHealthHistoryView(generics.ListAPIView):
    """
    Admin: Get system health history
    """
    permission_classes = [IsAuthenticated, AdminOnly]
    serializer_class = SystemHealthCheckSerializer
    queryset = SystemHealthCheck.objects.all().order_by('-created_at')
    
    def get_queryset(self):
        queryset = SystemHealthCheck.objects.all()
        
        # Filter by check type
        check_type = self.request.query_params.get('check_type', None)
        if check_type:
            queryset = queryset.filter(check_type=check_type)
        
        # Filter by status
        status_filter = self.request.query_params.get('status', None)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date', None)
        end_date = self.request.query_params.get('end_date', None)
        
        if start_date:
            queryset = queryset.filter(created_at__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__date__lte=end_date)
        
        return queryset.order_by('-created_at')[:100]  # Limit to 100 records


class AdminDashboardStatsView(APIView):
    """
    Admin: Get dashboard statistics
    """
    permission_classes = [IsAuthenticated, AdminOnly]
    
    def get(self, request):
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            
            # Today's date
            today = timezone.now().date()
            week_ago = today - timezone.timedelta(days=7)
            month_ago = today - timezone.timedelta(days=30)
            
            # User statistics
            total_users = User.objects.count()
            new_users_today = User.objects.filter(
                created_at__date=today
            ).count()
            new_users_week = User.objects.filter(
                created_at__date__gte=week_ago
            ).count()
            active_users = User.objects.filter(is_active=True).count()
            verified_users = User.objects.filter(
                is_verified=True, email_verified=True
            ).count()
            
            # Transaction statistics
            from .models import LedgerEntry
            
            total_transactions = LedgerEntry.objects.count()
            transactions_today = LedgerEntry.objects.filter(
                created_at__date=today
            ).count()
            transactions_week = LedgerEntry.objects.filter(
                created_at__date__gte=week_ago
            ).count()
            
            # Financial statistics
            total_deposits = LedgerEntry.objects.filter(
                transaction_type='DEPOSIT'
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            
            total_withdrawals = LedgerEntry.objects.filter(
                transaction_type='WITHDRAWAL'
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            
            deposits_today = LedgerEntry.objects.filter(
                transaction_type='DEPOSIT',
                created_at__date=today
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            
            # Support statistics
            try:
                from support.models import SupportTicket
                total_tickets = SupportTicket.objects.count()
                open_tickets = SupportTicket.objects.filter(
                    status__in=['OPEN', 'IN_PROGRESS']
                ).count()
            except ImportError:
                total_tickets = 0
                open_tickets = 0
            
            # Investment statistics (if investments app is installed)
            try:
                from investments.models import UserInvestment
                active_investments = UserInvestment.objects.filter(
                    status='ACTIVE'
                ).count()
                total_invested = UserInvestment.objects.aggregate(
                    total=Sum('principal_amount')
                )['total'] or Decimal('0.00')
            except ImportError:
                active_investments = 0
                total_invested = Decimal('0.00')
            
            stats = {
                'user_stats': {
                    'total_users': total_users,
                    'new_users_today': new_users_today,
                    'new_users_week': new_users_week,
                    'active_users': active_users,
                    'verified_users': verified_users
                },
                'transaction_stats': {
                    'total_transactions': total_transactions,
                    'transactions_today': transactions_today,
                    'transactions_week': transactions_week
                },
                'financial_stats': {
                    'total_deposits': total_deposits,
                    'total_withdrawals': total_withdrawals,
                    'deposits_today': deposits_today,
                    'net_flow': total_deposits - total_withdrawals
                },
                'support_stats': {
                    'total_tickets': total_tickets,
                    'open_tickets': open_tickets
                },
                'investment_stats': {
                    'active_investments': active_investments,
                    'total_invested': total_invested
                },
                'period': {
                    'today': today.isoformat(),
                    'week_ago': week_ago.isoformat(),
                    'month_ago': month_ago.isoformat()
                }
            }
            
            return Response(stats, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error getting dashboard stats: {str(e)}")
            return Response(
                {'error': 'Failed to get dashboard statistics'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

