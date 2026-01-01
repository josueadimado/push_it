"""
Management command to add Facebook to platform settings.
"""
from django.core.management.base import BaseCommand
from influencers.models import PlatformSettings


class Command(BaseCommand):
    help = 'Add Facebook platform setting if it does not exist'

    def handle(self, *args, **options):
        platform_setting, created = PlatformSettings.objects.get_or_create(
            platform=PlatformSettings.Platform.FACEBOOK,
            defaults={
                'minimum_followers': 5000,
                'is_active': True,
            }
        )
        
        if created:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully created Facebook platform setting with minimum {platform_setting.minimum_followers:,} followers'
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING('Facebook platform setting already exists')
            )

