"""
Management command to create or reset Django admin superuser.
Usage: 
    python manage.py create_admin
    python manage.py create_admin --username admin --email admin@example.com --password mypassword
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from getpass import getpass

User = get_user_model()


class Command(BaseCommand):
    help = 'Create or reset Django admin superuser'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            type=str,
            help='Username for the admin user (default: admin)',
            default='admin'
        )
        parser.add_argument(
            '--email',
            type=str,
            help='Email for the admin user',
        )
        parser.add_argument(
            '--password',
            type=str,
            help='Password for the admin user (will prompt if not provided)',
        )
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Reset password for existing admin user',
        )

    def handle(self, *args, **options):
        username = options['username']
        email = options.get('email')
        password = options.get('password')
        reset = options.get('reset', False)
        
        # Get or create user
        try:
            user = User.objects.get(username=username)
            if not reset:
                self.stdout.write(self.style.WARNING(
                    f'User "{username}" already exists. Use --reset to change password.'
                ))
                return
            
            self.stdout.write(self.style.WARNING(f'Resetting password for existing user: {username}'))
        except User.DoesNotExist:
            user = None
            if not email:
                email = input(f'Enter email for admin user (or press Enter for {username}@pushit.com): ').strip()
                if not email:
                    email = f'{username}@pushit.com'
        
        # Get password
        if not password:
            password = getpass('Enter password: ')
            password_confirm = getpass('Confirm password: ')
            if password != password_confirm:
                self.stdout.write(self.style.ERROR('Passwords do not match!'))
                return
        
        # Create or update user
        if user:
            # Update existing user
            user.set_password(password)
            if email:
                user.email = email
            user.is_superuser = True
            user.is_staff = True
            user.is_active = True
            user.is_email_verified = True  # Auto-verify admin emails
            if not user.role:
                user.role = User.Roles.ADMIN
            user.save()
            self.stdout.write(self.style.SUCCESS(
                f'✓ Successfully reset password for admin user: {username}'
            ))
        else:
            # Create new user
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                is_superuser=True,
                is_staff=True,
                is_active=True,
                is_email_verified=True,  # Auto-verify admin emails
                role=User.Roles.ADMIN
            )
            self.stdout.write(self.style.SUCCESS(
                f'✓ Successfully created admin user: {username} ({email})'
            ))
        
        self.stdout.write(self.style.SUCCESS(
            f'\nAdmin Login Credentials:\n'
            f'  Username: {username}\n'
            f'  Email: {user.email}\n'
            f'  Password: {"*" * len(password) if password else "Set via command"}\n'
            f'\nLogin at: http://127.0.0.1:8000/admin/'
        ))

