"""
Management command to manually verify a user's email for testing purposes.
Usage: python manage.py verify_user_email <email>
"""
from django.core.management.base import BaseCommand
from accounts.models import User


class Command(BaseCommand):
    help = 'Manually verify a user\'s email address (for testing)'

    def add_arguments(self, parser):
        parser.add_argument('email', type=str, help='Email address of the user to verify')

    def handle(self, *args, **options):
        email = options['email']
        
        try:
            user = User.objects.get(email=email)
            if user.is_email_verified:
                self.stdout.write(self.style.WARNING(f'User {email} is already verified.'))
            else:
                user.is_email_verified = True
                user.save()
                self.stdout.write(self.style.SUCCESS(f'Successfully verified email for {email}'))
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'User with email {email} not found.'))

