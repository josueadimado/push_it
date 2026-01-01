from django.db import migrations


def populate_default_currencies(apps, schema_editor):
    """Populate default currencies with Naira as default."""
    Currency = apps.get_model('brands', 'Currency')
    
    default_currencies = [
        {
            'code': 'NGN',
            'name': 'Nigerian Naira',
            'symbol': '₦',
            'is_default': True,
            'is_active': True,
            'exchange_rate': 1.0000,
        },
        {
            'code': 'USD',
            'name': 'US Dollar',
            'symbol': '$',
            'is_default': False,
            'is_active': True,
            'exchange_rate': 0.0012,  # Approximate rate (will need to be updated)
        },
        {
            'code': 'EUR',
            'name': 'Euro',
            'symbol': '€',
            'is_default': False,
            'is_active': True,
            'exchange_rate': 0.0011,  # Approximate rate (will need to be updated)
        },
        {
            'code': 'GBP',
            'name': 'British Pound',
            'symbol': '£',
            'is_default': False,
            'is_active': True,
            'exchange_rate': 0.0009,  # Approximate rate (will need to be updated)
        },
    ]
    
    for currency_data in default_currencies:
        Currency.objects.get_or_create(
            code=currency_data['code'],
            defaults=currency_data
        )


def reverse_populate_currencies(apps, schema_editor):
    """Reverse migration - remove default currencies."""
    Currency = apps.get_model('brands', 'Currency')
    Currency.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('brands', '0008_currency_brand_currency'),
    ]

    operations = [
        migrations.RunPython(populate_default_currencies, reverse_populate_currencies),
    ]

