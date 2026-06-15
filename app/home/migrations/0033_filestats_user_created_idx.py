from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("home", "0032_stream_stream_token"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddIndex(
            model_name="filestats",
            index=models.Index(fields=["user", "-created_at"], name="home_filest_user_id_created_idx"),
        ),
    ]
