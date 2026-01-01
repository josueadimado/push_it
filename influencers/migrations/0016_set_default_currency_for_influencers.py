from django.db import migrations


def set_default_currency_for_influencers(apps, schema_editor):
    """Set default currency for existing influencers."""
    Influencer = apps.get_model('influencers', 'Influencer')
    Currency = apps.get_model('brands', 'Currency')
    
    # Get default currency (GHS or first default)
    default_currency = Currency.objects.filter(is_default=True).first()
    if not default_currency:
        default_currency = Currency.objects.filter(code='GHS').first()
    if not default_currency:
        default_currency = Currency.objects.filter(code='USD').first()
    
    if default_currency:
        Influencer.objects.filter(currency__isnull=True).update(currency=default_currency)


def reverse_set_currency(apps, schema_editor):
    """Reverse migration - remove currency from influencers."""
    Influencer = apps.get_model('influencers', 'Influencer')
    Influencer.objects.all().update(currency=None)


class Migration(migrations.Migration):

    dependencies = [
        ('influencers', '0015_add_currency_to_influencer'),
        ('brands', '0010_set_default_currency_for_brands'),  # Ensure currencies exist
    ]

    operations = [
        migrations.RunPython(set_default_currency_for_influencers, reverse_set_currency),
    ]

