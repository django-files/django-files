# Generated by Django 5.1.6 on 2025-06-06 03:32

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("oauth", "0023_alter_customuser_timezone"),
    ]

    operations = [
        migrations.AlterField(
            model_name="discord",
            name="access_token",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AlterField(
            model_name="discord",
            name="avatar",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AlterField(
            model_name="discord",
            name="refresh_token",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
