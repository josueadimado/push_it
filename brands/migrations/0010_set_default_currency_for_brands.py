from django.db import migrations


def set_default_currency_for_brands(apps, schema_editor):
    """Set default currency (NGN) for all existing brands that don't have one."""
    Brand = apps.get_model('brands', 'Brand')
    Currency = apps.get_model('brands', 'Currency')
    
    # Get Naira currency
    naira = Currency.objects.filter(code='NGN').first()
    if naira:
        # Set Naira as currency for all brands without a currency
        Brand.objects.filter(currency__isnull=True).update(currency=naira)


def reverse_set_currency(apps, schema_editor):
    """Reverse migration - remove currency from brands."""
    Brand = apps.get_model('brands', 'Brand')
    Brand.objects.all().update(currency=None)


class Migration(migrations.Migration):

    dependencies = [
        ('brands', '0009_populate_default_currencies'),
    ]

    operations = [
        migrations.RunPython(set_default_currency_for_brands, reverse_set_currency),
    ]

