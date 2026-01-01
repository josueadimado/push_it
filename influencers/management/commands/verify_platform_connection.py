"""
Management command to manually verify a platform connection.
Usage: python manage.py verify_platform_connection --connection-id <id>
       python manage.py verify_platform_connection --platform youtube --user-email user@example.com
"""
from django.core.management.base import BaseCommand
from influencers.models import PlatformConnection, Influencer
from accounts.models import User
from influencers.verification import VerificationService


class Command(BaseCommand):
    help = 'Manually verify a platform connection'

    def add_arguments(self, parser):
        parser.add_argument(
            '--connection-id',
            type=int,
            help='ID of the platform connection to verify',
        )
        parser.add_argument(
            '--platform',
            type=str,
            help='Platform to verify (youtube, tiktok, instagram, etc.)',
        )
        parser.add_argument(
            '--user-email',
            type=str,
            help='User email to find the connection',
        )

    def handle(self, *args, **options):
        connection_id = options.get('connection_id')
        platform = options.get('platform')
        user_email = options.get('user_email')
        
        # Find the connection
        if connection_id:
            try:
                connection = PlatformConnection.objects.get(id=connection_id)
            except PlatformConnection.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'Connection with ID {connection_id} not found.'))
                return
        elif platform and user_email:
            try:
                user = User.objects.get(email=user_email)
                influencer = user.influencer_profile
                connection = PlatformConnection.objects.filter(
                    influencer=influencer,
                    platform=platform
                ).first()
                if not connection:
                    self.stdout.write(self.style.ERROR(f'No {platform} connection found for {user_email}.'))
                    return
            except (User.DoesNotExist, AttributeError):
                self.stdout.write(self.style.ERROR(f'User with email {user_email} not found or not an influencer.'))
                return
        else:
            self.stdout.write(self.style.ERROR('Please provide either --connection-id or both --platform and --user-email.'))
            return
        
        # Display current status
        self.stdout.write(self.style.SUCCESS(f'\nCurrent Status:'))
        self.stdout.write(f'Platform: {connection.get_platform_display()}')
        self.stdout.write(f'Handle: @{connection.handle}')
        self.stdout.write(f'User Provided Count: {connection.followers_count:,}')
        self.stdout.write(f'Verified Count: {connection.verified_followers_count or "N/A"}')
        self.stdout.write(f'Status: {connection.get_verification_status_display()}')
        self.stdout.write(f'Confidence: {connection.verification_confidence:.2f}')
        if connection.verification_flags:
            self.stdout.write(f'Flags: {", ".join(connection.verification_flags)}')
        
        # Run verification
        self.stdout.write(self.style.SUCCESS(f'\nRunning verification...'))
        try:
            result = VerificationService.verify_connection(connection, auto_approve=True)
            
            # Refresh connection
            connection.refresh_from_db()
            
            # Display results
            self.stdout.write(self.style.SUCCESS(f'\nVerification Results:'))
            self.stdout.write(f'Passed: {result.passed}')
            self.stdout.write(f'Reason: {result.reason}')
            self.stdout.write(f'Confidence: {result.confidence:.2f}')
            if result.flags:
                self.stdout.write(f'Flags:')
                for flag in result.flags:
                    self.stdout.write(f'  - {flag}')
            
            self.stdout.write(self.style.SUCCESS(f'\nUpdated Status:'))
            self.stdout.write(f'Status: {connection.get_verification_status_display()}')
            self.stdout.write(f'Verified Count: {connection.verified_followers_count or "N/A"}')
            self.stdout.write(f'Confidence: {connection.verification_confidence:.2f}')
            
            if result.passed:
                self.stdout.write(self.style.SUCCESS(f'\n✓ Verification successful! Connection is now verified.'))
            else:
                self.stdout.write(self.style.WARNING(f'\n⚠ Verification did not pass. Connection remains {connection.get_verification_status_display()}.'))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\n✗ Verification failed with error: {e}'))
            import traceback
            self.stdout.write(traceback.format_exc())

