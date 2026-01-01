"""
Management command to process queued influencer verifications.
Run this command periodically (every 1-2 minutes) via cron or scheduler.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from influencers.models import InfluencerVerificationQueue, Influencer
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Process scheduled influencer verifications'

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
        queue_items = InfluencerVerificationQueue.objects.filter(
            processed=False,
            scheduled_at__lte=now
        )[:limit]
        
        processed_count = 0
        approved_count = 0
        pending_count = 0
        
        for queue_item in queue_items:
            try:
                influencer = queue_item.influencer
                
                # Skip if influencer is already approved or paused
                if influencer.verification_status == Influencer.VerificationStatus.APPROVED or influencer.is_paused:
                    queue_item.processed = True
                    queue_item.save()
                    continue
                
                # Check if influencer meets verification criteria
                # They need: verified platforms, minimum followers, niche, primary platform
                has_verified_platforms = influencer.verified_platforms.exists()
                has_minimum_followers = influencer.has_minimum_followers
                has_niche = influencer.niche is not None
                has_primary_platform = influencer.primary_platform is not None
                
                if has_verified_platforms and has_minimum_followers and has_niche and has_primary_platform:
                    # Auto-approve
                    influencer.verification_status = Influencer.VerificationStatus.APPROVED
                    influencer.save()
                    approved_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'✓ Influencer {influencer.user.username} auto-approved'
                        )
                    )
                else:
                    # Keep as pending for manual review
                    pending_count += 1
                    missing = []
                    if not has_verified_platforms:
                        missing.append("verified platforms")
                    if not has_minimum_followers:
                        missing.append("minimum followers")
                    if not has_niche:
                        missing.append("niche")
                    if not has_primary_platform:
                        missing.append("primary platform")
                    
                    self.stdout.write(
                        self.style.WARNING(
                            f'⚠ Influencer {influencer.user.username} needs manual review (missing: {", ".join(missing)})'
                        )
                    )
                
                # Mark as processed
                queue_item.processed = True
                queue_item.save()
                processed_count += 1
                
            except Exception as e:
                logger.error(f"Error processing verification for {queue_item.influencer}: {e}")
                self.stdout.write(
                    self.style.ERROR(f'✗ Error processing {queue_item.influencer}: {e}')
                )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\nProcessed {processed_count} verifications: '
                f'{approved_count} approved, {pending_count} pending review'
            )
        )

