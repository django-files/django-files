# Generated by Django 4.2.4 on 2023-08-05 09:22

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("home", "0008_shorturls_max_alter_shorturls_views"),
    ]

    operations = [
        migrations.AlterField(
            model_name="files",
            name="name",
            field=models.CharField(
                blank=True,
                help_text="File Name.",
                max_length=255,
                null=True,
                verbose_name="Name",
            ),
        ),
    ]
