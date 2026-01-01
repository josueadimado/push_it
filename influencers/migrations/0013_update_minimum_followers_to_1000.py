from django.db import migrations


def update_minimum_followers_to_1000(apps, schema_editor):
    """Update all platform minimum followers to 1000."""
    PlatformSettings = apps.get_model('influencers', 'PlatformSettings')
    
    # Update all platforms to 1000 minimum followers
    PlatformSettings.objects.all().update(minimum_followers=1000)


def reverse_update_minimum_followers(apps, schema_editor):
    """Reverse migration - restore original values."""
    PlatformSettings = apps.get_model('influencers', 'PlatformSettings')
    
    # Restore original values (5000 for most, 1000 for YouTube)
    defaults = {
        'tiktok': 5000,
        'instagram': 5000,
        'youtube': 1000,
        'twitter': 5000,
        'snapchat': 5000,
        'facebook': 5000,
    }
    
    for platform, min_followers in defaults.items():
        PlatformSettings.objects.filter(platform=platform).update(minimum_followers=min_followers)


class Migration(migrations.Migration):

    dependencies = [
        ('influencers', '0012_add_facebook_platform'),
    ]

    operations = [
        migrations.RunPython(update_minimum_followers_to_1000, reverse_update_minimum_followers),
    ]

