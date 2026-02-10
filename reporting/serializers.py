from rest_framework import serializers
from django.utils import timezone
from decimal import Decimal
from .models import (
    LedgerEntry, AuditLog, FinancialReport,
    UserActivityLog, SystemHealthCheck
)

class LedgerEntrySerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    verified_by_email = serializers.EmailField(source='verified_by.email', read_only=True)
    
    class Meta:
        model = LedgerEntry
        fields = [
            'ledger_id', 'user', 'user_email', 'user_name',
            'transaction_type', 'reference_id', 'amount',
            'balance_before', 'balance_after', 'source_app',
            'source_model', 'source_id', 'description',
            'metadata', 'ip_address', 'user_agent',
            'is_verified', 'verified_by', 'verified_by_email',
            'verified_at', 'verification_notes', 'created_at'
        ]
        read_only_fields = fields

class AuditLogSerializer(serializers.ModelSerializer):
    admin_email = serializers.EmailField(source='admin.email', read_only=True)
    admin_name = serializers.CharField(source='admin.get_full_name', read_only=True)
    
    class Meta:
        model = AuditLog
        fields = [
            'audit_id', 'admin', 'admin_email', 'admin_name',
            'action', 'target_object', 'target_model', 'target_id',
            'changes_before', 'changes_after', 'changes_summary',
            'ip_address', 'user_agent', 'request_path', 'status',
            'error_message', 'created_at'
        ]
        read_only_fields = fields

class FinancialReportSerializer(serializers.ModelSerializer):
    generated_by_email = serializers.EmailField(source='generated_by.email', read_only=True)
    generated_by_name = serializers.CharField(source='generated_by.get_full_name', read_only=True)
    
    class Meta:
        model = FinancialReport
        fields = [
            'report_id', 'generated_by', 'generated_by_email', 'generated_by_name',
            'report_type', 'report_format', 'title', 'description',
            'date_from', 'date_to', 'filters', 'report_data', 'summary',
            'file_path', 'file_size', 'download_url', 'is_generated',
            'generation_started_at', 'generation_completed_at', 'generation_duration',
            'error_message', 'is_encrypted', 'encryption_key',
            'created_at', 'expires_at'
        ]
        read_only_fields = [
            'report_id', 'file_size', 'is_generated',
            'generation_started_at', 'generation_completed_at', 'generation_duration',
            'created_at', 'expires_at'
        ]

class CreateReportSerializer(serializers.Serializer):
    report_type = serializers.ChoiceField(
        choices=FinancialReport.ReportType.choices,
        required=True
    )
    report_format = serializers.ChoiceField(
        choices=FinancialReport.ReportFormat.choices,
        default=FinancialReport.ReportFormat.JSON
    )
    title = serializers.CharField(required=True, max_length=255)
    description = serializers.CharField(required=False, allow_blank=True)
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)
    filters = serializers.JSONField(required=False, default=dict)
    
    def validate(self, attrs):
        date_from = attrs.get('date_from')
        date_to = attrs.get('date_to')
        
        if date_from and date_to and date_from > date_to:
            raise serializers.ValidationError({
                'date_from': 'Start date cannot be after end date'
            })
        
        return attrs

class UserActivityLogSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    
    class Meta:
        model = UserActivityLog
        fields = [
            'activity_id', 'user', 'user_email', 'user_name',
            'activity_type', 'description', 'page_url', 'referrer_url',
            'session_id', 'ip_address', 'user_agent', 'device_type',
            'browser', 'operating_system', 'country', 'city',
            'latitude', 'longitude', 'metadata', 'created_at'
        ]
        read_only_fields = fields

class SystemHealthCheckSerializer(serializers.ModelSerializer):
    class Meta:
        model = SystemHealthCheck
        fields = [
            'check_id', 'check_type', 'status', 'response_time',
            'success_rate', 'message', 'details', 'error_message',
            'created_at'
        ]
        read_only_fields = fields

class TransactionHistorySerializer(serializers.Serializer):
    date = serializers.DateField()
    transaction_type = serializers.CharField()
    amount = serializers.DecimalField(max_digits=20, decimal_places=8)
    description = serializers.CharField()
    balance_after = serializers.DecimalField(max_digits=20, decimal_places=8)

class FinancialSummarySerializer(serializers.Serializer):
    total_deposits = serializers.DecimalField(max_digits=20, decimal_places=8)
    total_withdrawals = serializers.DecimalField(max_digits=20, decimal_places=8)
    total_investments = serializers.DecimalField(max_digits=20, decimal_places=8)
    total_profits = serializers.DecimalField(max_digits=20, decimal_places=8)
    total_referral_bonuses = serializers.DecimalField(max_digits=20, decimal_places=8)
    net_flow = serializers.DecimalField(max_digits=20, decimal_places=8)
    active_users = serializers.IntegerField()
    active_investments = serializers.IntegerField()
    pending_withdrawals = serializers.DecimalField(max_digits=20, decimal_places=8)

class DateRangeSerializer(serializers.Serializer):
    start_date = serializers.DateField(required=True)
    end_date = serializers.DateField(required=True)
    
    def validate(self, attrs):
        if attrs['start_date'] > attrs['end_date']:
            raise serializers.ValidationError("Start date cannot be after end date")
        return attrs

class ExportFormatSerializer(serializers.Serializer):
    format = serializers.ChoiceField(
        choices=['csv', 'json', 'excel', 'pdf'],
        default='csv'
    )
    include_summary = serializers.BooleanField(default=True)

