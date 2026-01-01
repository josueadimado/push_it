from django.db import migrations


def populate_default_niches(apps, schema_editor):
    """Populate default niches."""
    Niche = apps.get_model('influencers', 'Niche')
    
    default_niches = [
        {'name': 'Fashion & Style', 'icon': 'lucide:shirt', 'description': 'Fashion, clothing, style, and beauty'},
        {'name': 'Fitness & Health', 'icon': 'lucide:dumbbell', 'description': 'Fitness, workout, health, and wellness'},
        {'name': 'Technology', 'icon': 'lucide:smartphone', 'description': 'Tech reviews, gadgets, and software'},
        {'name': 'Food & Cooking', 'icon': 'lucide:utensils', 'description': 'Food, recipes, cooking, and restaurants'},
        {'name': 'Travel', 'icon': 'lucide:map-pin', 'description': 'Travel, destinations, and tourism'},
        {'name': 'Gaming', 'icon': 'lucide:gamepad-2', 'description': 'Video games, gaming content, and esports'},
        {'name': 'Beauty & Skincare', 'icon': 'lucide:sparkles', 'description': 'Beauty products, skincare, and makeup'},
        {'name': 'Lifestyle', 'icon': 'lucide:home', 'description': 'Daily life, home decor, and lifestyle content'},
        {'name': 'Entertainment', 'icon': 'lucide:music', 'description': 'Music, movies, and entertainment'},
        {'name': 'Education', 'icon': 'lucide:book', 'description': 'Educational content and tutorials'},
        {'name': 'Business & Finance', 'icon': 'lucide:trending-up', 'description': 'Business tips, finance, and entrepreneurship'},
        {'name': 'Sports', 'icon': 'lucide:trophy', 'description': 'Sports, athletics, and sports commentary'},
    ]
    
    for niche_data in default_niches:
        Niche.objects.get_or_create(
            name=niche_data['name'],
            defaults={
                'description': niche_data['description'],
                'icon': niche_data['icon'],
                'is_active': True,
            }
        )


def reverse_populate_niches(apps, schema_editor):
    """Reverse migration - remove default niches."""
    Niche = apps.get_model('influencers', 'Niche')
    Niche.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('influencers', '0006_niche_influencer_niche_legacy_alter_influencer_niche'),
    ]

    operations = [
        migrations.RunPython(populate_default_niches, reverse_populate_niches),
    ]

