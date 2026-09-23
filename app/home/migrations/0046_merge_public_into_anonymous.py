from django.db import migrations
from django.db.models import Sum


def merge_public_into_anonymous(apps, schema_editor):
    """
    The legacy /public/ upload endpoint (home.views.pub_uppy_view) used to
    attach anonymous uploads to a separate "public" CustomUser, while every
    other anonymous upload path (XHR /upload/, tus) uses "anonymous". That
    view now uses "anonymous" too, so fold any pre-existing "public" account
    and its data into "anonymous" rather than leaving two owner accounts for
    the same shared identity.
    """
    CustomUser = apps.get_model("oauth", "CustomUser")
    Files = apps.get_model("home", "Files")
    Albums = apps.get_model("home", "Albums")
    ShortURLs = apps.get_model("home", "ShortURLs")
    FileStats = apps.get_model("home", "FileStats")
    ApiToken = apps.get_model("oauth", "ApiToken")
    PasskeyCredential = apps.get_model("oauth", "PasskeyCredential")
    Webhook = apps.get_model("home", "Webhook")
    Stream = apps.get_model("home", "Stream")
    StreamDiscordWebhooks = apps.get_model("home", "StreamDiscordWebhooks")
    PushInformation = apps.get_model("webpush", "PushInformation")

    public = CustomUser.objects.filter(username="public").first()
    if not public:
        return

    anonymous, _ = CustomUser.objects.get_or_create(username="anonymous", defaults={"first_name": "Anonymous"})

    moved_size = Files.objects.filter(user=public).aggregate(total=Sum("size"))["total"] or 0
    Files.objects.filter(user=public).update(user=anonymous)
    Albums.objects.filter(user=public).update(user=anonymous)
    ShortURLs.objects.filter(user=public).update(user=anonymous)
    FileStats.objects.filter(user=public).update(user=anonymous)
    CustomUser.objects.filter(pk=anonymous.pk).update(storage_usage=anonymous.storage_usage + moved_size)

    # The anonymous upload flow never creates ApiTokens, passkeys, webhooks,
    # streams, or push subscriptions for this account, but on_delete=CASCADE
    # would silently destroy any that exist (e.g. from manual admin setup) if
    # we deleted "public" underneath them. Only delete once nothing is left.
    other_refs = (
        ApiToken.objects.filter(user=public).exists()
        or PasskeyCredential.objects.filter(user=public).exists()
        or Webhook.objects.filter(owner=public).exists()
        or Stream.objects.filter(user=public).exists()
        or StreamDiscordWebhooks.objects.filter(owner=public).exists()
        or PushInformation.objects.filter(user=public).exists()
    )
    if not other_refs:
        public.delete()


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("home", "0045_stream_record_stream_recording_retention_count_and_more"),
        ("oauth", "0027_delete_discordwebhooks"),
        ("webpush", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(merge_public_into_anonymous, noop_reverse),
    ]
