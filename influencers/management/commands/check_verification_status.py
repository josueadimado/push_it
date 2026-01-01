"""
Management command to check verification status of platform connections.
Usage: python manage.py check_verification_status
       python manage.py check_verification_status --platform youtube
       python manage.py check_verification_status --user-email user@example.com
"""
from django.core.management.base import BaseCommand
from influencers.models import PlatformConnection, Influencer
from accounts.models import User


class Command(BaseCommand):
    help = 'Check verification status of platform connections'

    def add_arguments(self, parser):
        parser.add_argument(
            '--platform',
            type=str,
            help='Filter by platform (youtube, tiktok, instagram, etc.)',
        )
        parser.add_argument(
            '--user-email',
            type=str,
            help='Filter by user email',
        )
        parser.add_argument(
            '--pending-only',
            action='store_true',
            help='Show only pending verifications',
        )

    def handle(self, *args, **options):
        platform = options.get('platform')
        user_email = options.get('user_email')
        pending_only = options.get('pending_only', False)
        
        # Build query
        connections = PlatformConnection.objects.all().select_related('influencer', 'influencer__user')
        
        if platform:
            connections = connections.filter(platform=platform)
        
        if user_email:
            try:
                user = User.objects.get(email=user_email)
                influencer = user.influencer_profile
                connections = connections.filter(influencer=influencer)
            except (User.DoesNotExist, AttributeError):
                self.stdout.write(self.style.ERROR(f'User with email {user_email} not found or not an influencer.'))
                return
        
        if pending_only:
            connections = connections.filter(verification_status='pending')
        
        # Display results
        if not connections.exists():
            self.stdout.write(self.style.WARNING('No platform connections found matching criteria.'))
            return
        
        self.stdout.write(self.style.SUCCESS(f'\nFound {connections.count()} platform connection(s):\n'))
        self.stdout.write('=' * 100)
        
        for conn in connections:
            self.stdout.write(f'\nPlatform: {conn.get_platform_display()}')
            self.stdout.write(f'Handle: @{conn.handle}')
            self.stdout.write(f'User: {conn.influencer.user.email}')
            self.stdout.write(f'Status: {conn.get_verification_status_display()}')
            self.stdout.write(f'User Provided Count: {conn.followers_count:,}')
            self.stdout.write(f'Verified Count: {conn.verified_followers_count or "N/A"}')
            self.stdout.write(f'Confidence: {conn.verification_confidence:.2f}')
            self.stdout.write(f'Method: {conn.verification_method}')
            self.stdout.write(f'Created: {conn.created_at.strftime("%Y-%m-%d %H:%M:%S")}')
            
            if conn.verification_flags:
                self.stdout.write(f'Flags:')
                for flag in conn.verification_flags:
                    self.stdout.write(f'  - {flag}')
            else:
                self.stdout.write('Flags: None')
            
            self.stdout.write('-' * 100)
        
        # Summary
        status_counts = {}
        for conn in connections:
            status = conn.verification_status
            status_counts[status] = status_counts.get(status, 0) + 1
        
        self.stdout.write(self.style.SUCCESS(f'\nSummary:'))
        for status, count in status_counts.items():
            self.stdout.write(f'  {status}: {count}')

