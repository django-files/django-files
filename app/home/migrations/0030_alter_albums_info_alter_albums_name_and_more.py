# Generated by Django 4.2.5 on 2024-06-28 07:33

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("home", "0029_alter_albums_name"),
    ]

    operations = [
        migrations.AlterField(
            model_name="albums",
            name="info",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Album Information.",
                max_length=255,
                verbose_name="Info",
            ),
        ),
        migrations.AlterField(
            model_name="albums",
            name="name",
            field=models.CharField(
                help_text="Album Name.", max_length=255, verbose_name="Name"
            ),
        ),
        migrations.AlterField(
            model_name="albums",
            name="password",
            field=models.CharField(
                blank=True, default="", max_length=255, verbose_name="Album Password"
            ),
        ),
        migrations.AlterField(
            model_name="files",
            name="albums",
            field=models.ManyToManyField(blank=True, to="home.albums"),
        ),
        migrations.AlterField(
            model_name="files",
            name="info",
            field=models.CharField(
                blank=True,
                default="",
                help_text="File Information.",
                max_length=255,
                verbose_name="Info",
            ),
        ),
        migrations.AlterField(
            model_name="files",
            name="mime",
            field=models.CharField(
                blank=True,
                default="",
                help_text="File MIME Type.",
                max_length=255,
                verbose_name="MIME",
            ),
        ),
        migrations.AlterField(
            model_name="files",
            name="name",
            field=models.CharField(
                blank=True,
                default="",
                help_text="File Name.",
                max_length=255,
                verbose_name="Name",
            ),
        ),
        migrations.AlterField(
            model_name="files",
            name="password",
            field=models.CharField(
                blank=True, default="", max_length=255, verbose_name="File Password"
            ),
        ),
        migrations.AlterUniqueTogether(
            name="albums",
            unique_together={("user", "name")},
        ),
    ]
