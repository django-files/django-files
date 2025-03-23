# Generated by Django 4.2.5 on 2024-06-25 22:46

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("settings", "0011_sitesettings_local_auth_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="sitesettings",
            name="background_picture",
            field=models.CharField(
                default="https://picsum.photos/1920/1080", max_length=255
            ),
        ),
        migrations.AddField(
            model_name="sitesettings",
            name="background_video",
            field=models.CharField(default="/static/video/loop.mp4", max_length=255),
        ),
        migrations.AddField(
            model_name="sitesettings",
            name="login_background",
            field=models.CharField(default="video", max_length=16),
        ),
    ]
