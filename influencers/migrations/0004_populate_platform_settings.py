from django.db import migrations


def populate_platform_settings(apps, schema_editor):
    """Populate default platform settings."""
    PlatformSettings = apps.get_model('influencers', 'PlatformSettings')
    
    # Default minimum follower requirements per platform
    defaults = [
        {'platform': 'tiktok', 'minimum_followers': 5000, 'is_active': True},
        {'platform': 'instagram', 'minimum_followers': 5000, 'is_active': True},
        {'platform': 'youtube', 'minimum_followers': 1000, 'is_active': True},  # YouTube uses subscribers
        {'platform': 'twitter', 'minimum_followers': 5000, 'is_active': True},
        {'platform': 'snapchat', 'minimum_followers': 5000, 'is_active': True},
    ]
    
    for default in defaults:
        PlatformSettings.objects.get_or_create(
            platform=default['platform'],
            defaults={
                'minimum_followers': default['minimum_followers'],
                'is_active': default['is_active'],
            }
        )


def reverse_populate_platform_settings(apps, schema_editor):
    """Reverse migration - remove platform settings."""
    PlatformSettings = apps.get_model('influencers', 'PlatformSettings')
    PlatformSettings.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('influencers', '0003_platformsettings_influencer_primary_platform'),
    ]

    operations = [
        migrations.RunPython(populate_platform_settings, reverse_populate_platform_settings),
    ]

