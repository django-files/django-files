from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("home", "0033_filestats_user_created_idx"),
    ]

    operations = [
        # Disabled by default: empty token = raw-link playback disabled until the
        # owner explicitly enables it. Not unique because the empty value can
        # repeat across rows; lookups always join on stream name + token.
        migrations.AddField(
            model_name="stream",
            name="playback_token",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Per-stream raw-link token used by HLS players (VLC, ffmpeg, etc.) "
                "to fetch the stream via /hls-token/. Empty = raw-link playback disabled. "
                "Independent of stream_token (RTMP ingest).",
                max_length=32,
                verbose_name="Playback Token",
            ),
        ),
    ]
