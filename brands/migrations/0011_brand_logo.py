# Generated manually
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('brands', '0010_set_default_currency_for_brands'),
    ]

    operations = [
        migrations.AddField(
            model_name='brand',
            name='logo',
            field=models.ImageField(blank=True, help_text='Company logo (recommended size: 400x400px)', null=True, upload_to='brands/logos/'),
        ),
    ]

