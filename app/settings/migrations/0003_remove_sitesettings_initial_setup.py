# Generated by Django 4.2.4 on 2023-09-06 07:17

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("settings", "0002_sitesettings_initial_setup"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="sitesettings",
            name="initial_setup",
        ),
    ]
