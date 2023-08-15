# Generated by Django 4.2.3 on 2023-08-15 02:03

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("home", "0013_files_maxv_files_view"),
    ]

    operations = [
        migrations.AddField(
            model_name="files",
            name="meta",
            field=models.JSONField(
                default=dict,
                help_text="JSON formatted metadata.",
                verbose_name="Metadata",
            ),
        ),
    ]
