# Generated by Django 4.2.17 on 2025-04-28 13:52

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0011_alter_order_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='productimage',
            name='image_url',
            field=models.URLField(blank=True, max_length=500, null=True),
        ),
        migrations.AddField(
            model_name='productimage',
            name='public_id',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
