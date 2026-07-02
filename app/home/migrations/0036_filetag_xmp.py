from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("home", "0035_file_tags"),
    ]

    operations = [
        migrations.AddField(
            model_name="filetag",
            name="xmp",
            field=models.BooleanField(default=False),
        ),
    ]
