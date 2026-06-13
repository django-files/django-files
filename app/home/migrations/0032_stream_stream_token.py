import home.util.rand
from django.db import migrations, models


def populate_stream_tokens(apps, schema_editor):
    Stream = apps.get_model("home", "Stream")
    for stream in Stream.objects.filter(stream_token=""):  # nosec B106
        stream.stream_token = home.util.rand.rand_string()
        stream.save(update_fields=["stream_token"])


class Migration(migrations.Migration):

    dependencies = [
        ("home", "0031_stream_streamdiscordwebhooks_streamhistory"),
    ]

    operations = [
        # Step 1: add as nullable so existing rows get NULL, not a shared default
        migrations.AddField(
            model_name="stream",
            name="stream_token",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Per-stream RTMP authentication token. Scoped only to this stream.",
                max_length=32,
                verbose_name="Stream Token",
            ),
        ),
        # Step 2: fill unique tokens for all existing rows
        migrations.RunPython(populate_stream_tokens, migrations.RunPython.noop),
        # Step 3: add the unique constraint now that every row has a distinct value
        migrations.AlterField(
            model_name="stream",
            name="stream_token",
            field=models.CharField(
                default=home.util.rand.rand_string,
                help_text="Per-stream RTMP authentication token. Scoped only to this stream.",
                max_length=32,
                unique=True,
                verbose_name="Stream Token",
            ),
        ),
    ]
