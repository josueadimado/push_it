from django.db import migrations


def populate_default_industries(apps, schema_editor):
    """Populate default industries."""
    Industry = apps.get_model('brands', 'Industry')
    
    default_industries = [
        {'name': 'Fashion & Apparel', 'icon': 'lucide:shirt', 'description': 'Fashion brands, clothing, and apparel'},
        {'name': 'Technology', 'icon': 'lucide:smartphone', 'description': 'Tech companies, software, and hardware'},
        {'name': 'Food & Beverage', 'icon': 'lucide:utensils', 'description': 'Food brands, restaurants, and beverages'},
        {'name': 'Beauty & Cosmetics', 'icon': 'lucide:sparkles', 'description': 'Beauty products, skincare, and cosmetics'},
        {'name': 'Health & Fitness', 'icon': 'lucide:dumbbell', 'description': 'Health, fitness, and wellness brands'},
        {'name': 'Travel & Tourism', 'icon': 'lucide:map-pin', 'description': 'Travel agencies, hotels, and tourism'},
        {'name': 'E-commerce & Retail', 'icon': 'lucide:shopping-bag', 'description': 'Online stores and retail businesses'},
        {'name': 'Entertainment & Media', 'icon': 'lucide:music', 'description': 'Entertainment, media, and content creation'},
        {'name': 'Education & E-learning', 'icon': 'lucide:book', 'description': 'Educational platforms and courses'},
        {'name': 'Finance & Banking', 'icon': 'lucide:trending-up', 'description': 'Financial services and banking'},
        {'name': 'Automotive', 'icon': 'lucide:car', 'description': 'Car brands and automotive services'},
        {'name': 'Real Estate', 'icon': 'lucide:home', 'description': 'Real estate and property management'},
        {'name': 'Healthcare & Medical', 'icon': 'lucide:heart', 'description': 'Healthcare services and medical products'},
        {'name': 'Sports & Recreation', 'icon': 'lucide:trophy', 'description': 'Sports brands and recreational activities'},
        {'name': 'Gaming & Esports', 'icon': 'lucide:gamepad-2', 'description': 'Gaming companies and esports organizations'},
        {'name': 'Non-profit & Charity', 'icon': 'lucide:heart-handshake', 'description': 'Non-profit organizations and charities'},
    ]
    
    for industry_data in default_industries:
        Industry.objects.get_or_create(
            name=industry_data['name'],
            defaults={
                'description': industry_data['description'],
                'icon': industry_data['icon'],
                'is_active': True,
            }
        )


def reverse_populate_industries(apps, schema_editor):
    """Reverse migration - remove default industries."""
    Industry = apps.get_model('brands', 'Industry')
    Industry.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('brands', '0005_industry_brand_industry_legacy_alter_brand_industry'),
    ]

    operations = [
        migrations.RunPython(populate_default_industries, reverse_populate_industries),
    ]

