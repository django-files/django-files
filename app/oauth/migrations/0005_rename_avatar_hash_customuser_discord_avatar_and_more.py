# Generated by Django 4.2.4 on 2023-08-29 23:30

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("oauth", "0004_customuser_remove_exif"),
    ]

    operations = [
        migrations.RenameField(
            model_name="customuser",
            old_name="avatar_hash",
            new_name="discord_avatar",
        ),
        migrations.AddField(
            model_name="customuser",
            name="oauth_id",
            field=models.IntegerField(default=0),
        ),
    ]
