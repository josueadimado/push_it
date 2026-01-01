"""
Management command to flag suspicious platform connections for manual review.

Usage:
    python manage.py flag_suspicious
"""

from django.core.management.base import BaseCommand
from influencers.verification import VerificationService


class Command(BaseCommand):
    help = 'Flag suspicious platform connections for manual review'

    def handle(self, *args, **options):
        self.stdout.write('Scanning for suspicious connections...')
        
        suspicious = VerificationService.flag_suspicious_connections()
        
        if suspicious:
            self.stdout.write(self.style.WARNING(
                f'Found {len(suspicious)} suspicious connections:'
            ))
            for conn in suspicious:
                self.stdout.write(
                    f'  - {conn.influencer.user.username} - {conn.get_platform_display()} '
                    f'(@{conn.handle}, {conn.followers_count:,} followers, '
                    f'{conn.engagement_rate}% engagement)'
                )
        else:
            self.stdout.write(self.style.SUCCESS('No suspicious connections found.'))

