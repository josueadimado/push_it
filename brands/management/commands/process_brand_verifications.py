"""
Management command to process queued brand verifications.
Run this command periodically (every 1-2 minutes) via cron or scheduler.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from brands.models import BrandVerificationQueue
from brands.verification import BrandVerificationService
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Process scheduled brand verifications'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            default=50,
            help='Maximum number of verifications to process (default: 50)',
        )

    def handle(self, *args, **options):
        limit = options['limit']
        now = timezone.now()
        
        # Get unprocessed verifications that are due
        queue_items = BrandVerificationQueue.objects.filter(
            processed=False,
            scheduled_at__lte=now
        )[:limit]
        
        processed_count = 0
        approved_count = 0
        pending_count = 0
        
        for queue_item in queue_items:
            try:
                brand = queue_item.brand
                
                # Skip if brand is already verified or paused
                if brand.is_verified or brand.is_paused:
                    queue_item.processed = True
                    queue_item.save()
                    continue
                
                # Run verification
                result = BrandVerificationService.verify_brand(brand, auto_approve=True)
                
                if result.passed:
                    approved_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'✓ Brand {brand.company_name} auto-verified (confidence: {result.confidence:.2f})'
                        )
                    )
                else:
                    pending_count += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f'⚠ Brand {brand.company_name} needs manual review (confidence: {result.confidence:.2f})'
                        )
                    )
                
                # Mark as processed
                queue_item.processed = True
                queue_item.save()
                processed_count += 1
                
            except Exception as e:
                logger.error(f"Error processing verification for {queue_item.brand}: {e}")
                self.stdout.write(
                    self.style.ERROR(f'✗ Error processing {queue_item.brand}: {e}')
                )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\nProcessed {processed_count} verifications: '
                f'{approved_count} approved, {pending_count} pending review'
            )
        )

