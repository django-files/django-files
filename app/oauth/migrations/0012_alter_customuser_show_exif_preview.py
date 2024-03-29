# Generated by Django 4.2.3 on 2023-09-09 16:58

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("oauth", "0011_customuser_timezone"),
    ]

    operations = [
        migrations.AlterField(
            model_name="customuser",
            name="show_exif_preview",
            field=models.BooleanField(
                default=True,
                help_text="Default value if to show exif data on previews and unfurls.",
                verbose_name="EXIF Preview",
            ),
        ),
    ]
