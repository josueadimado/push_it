"""
Management command to batch verify platform connections.
Run this periodically (e.g., via cron) to process pending verifications.

Usage:
    python manage.py verify_platforms
    python manage.py verify_platforms --limit 50
    python manage.py verify_platforms --no-auto-approve
"""

from django.core.management.base import BaseCommand
from influencers.verification import VerificationService


class Command(BaseCommand):
    help = 'Batch verify pending platform connections'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            default=100,
            help='Maximum number of connections to process (default: 100)',
        )
        parser.add_argument(
            '--no-auto-approve',
            action='store_true',
            help='Do not auto-approve connections, only flag them',
        )

    def handle(self, *args, **options):
        limit = options['limit']
        auto_approve = not options['no_auto_approve']
        
        self.stdout.write(f'Starting batch verification (limit: {limit}, auto-approve: {auto_approve})...')
        
        stats = VerificationService.batch_verify_pending(limit=limit, auto_approve=auto_approve)
        
        self.stdout.write(self.style.SUCCESS(
            f'\nVerification complete:\n'
            f'  Total processed: {stats["total_processed"]}\n'
            f'  Auto-approved: {stats["auto_approved"]}\n'
            f'  Flagged for review: {stats["flagged"]}\n'
            f'  Rejected: {stats["rejected"]}'
        ))

