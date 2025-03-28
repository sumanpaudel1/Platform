# Generated by Django 4.2.17 on 2025-03-09 06:16

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0014_remove_notification_accounts_no_vendor__e0238f_idx_and_more'),
        ('products', '0009_order_is_active'),
    ]

    operations = [
        migrations.AlterField(
            model_name='deliveryaddress',
            name='customer',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='addresses', to='accounts.customer'),
        ),
    ]
