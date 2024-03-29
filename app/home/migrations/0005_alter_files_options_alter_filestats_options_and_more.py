# Generated by Django 4.2.4 on 2023-08-05 05:24

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("home", "0004_alter_webhooks_options_filestats"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="files",
            options={
                "ordering": ["-date"],
                "verbose_name": "File",
                "verbose_name_plural": "Files",
            },
        ),
        migrations.AlterModelOptions(
            name="filestats",
            options={
                "ordering": ["-created_at"],
                "verbose_name": "FileStat",
                "verbose_name_plural": "FileStats",
            },
        ),
        migrations.AlterModelOptions(
            name="sitesettings",
            options={"verbose_name": "Setting", "verbose_name_plural": "Settings"},
        ),
        migrations.CreateModel(
            name="ShortURLs",
            fields=[
                ("id", models.AutoField(primary_key=True, serialize=False)),
                (
                    "url",
                    models.URLField(
                        help_text="ShortURL Short URL.",
                        unique=True,
                        verbose_name="Short URL",
                    ),
                ),
                (
                    "views",
                    models.IntegerField(
                        default=0,
                        help_text="ShortURL Max Views",
                        verbose_name="ShortURL Views",
                    ),
                ),
                (
                    "updated_at",
                    models.DateTimeField(
                        auto_now=True,
                        help_text="ShortURL Edited Date.",
                        verbose_name="ShortURL Edited",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(
                        auto_now_add=True,
                        help_text="ShortURL Created Date.",
                        verbose_name="ShortURL Created",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Short URL",
                "verbose_name_plural": "Short URLs",
                "ordering": ["-created_at"],
            },
        ),
    ]
