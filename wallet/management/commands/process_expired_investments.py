from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Process expired investments and auto-complete them'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run in dry-run mode without making changes',
        )
    
    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        try:
            from investments.models import UserInvestment
            
            # Find expired active investments
            expired_investments = UserInvestment.objects.filter(
                status=UserInvestment.InvestmentStatus.ACTIVE,
                end_date__lte=timezone.now()
            )
            
            count = expired_investments.count()
            self.stdout.write(f"Found {count} expired investments")
            
            if dry_run:
                self.stdout.write("DRY RUN - No changes made")
                return
            
            completed = 0
            errors = 0
            
            for investment in expired_investments:
                try:
                    with transaction.atomic():
                        investment.complete_investment()
                        completed += 1
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"Completed investment {investment.investment_id} - "
                                f"User: {investment.user.email}, Profit: ${investment.total_profit}"
                            )
                        )
                except Exception as e:
                    errors += 1
                    self.stdout.write(
                        self.style.ERROR(
                            f"Failed to complete investment {investment.investment_id}: {str(e)}"
                        )
                    )
            
            self.stdout.write(
                self.style.SUCCESS(
                    f"Processed {completed} investments, {errors} errors"
                )
            )
            
        except ImportError:
            self.stdout.write(
                self.style.ERROR("Investments app not installed")
            )