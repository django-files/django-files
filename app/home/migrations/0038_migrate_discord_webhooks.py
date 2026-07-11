from django.db import migrations


def copy_discord_webhooks(apps, schema_editor):
    DiscordWebhooks = apps.get_model("oauth", "DiscordWebhooks")
    Webhook = apps.get_model("home", "Webhook")
    hooks = []
    for hook in DiscordWebhooks.objects.all():
        hooks.append(
            Webhook(
                owner_id=hook.owner_id,
                name=f"Discord {hook.hook_id or hook.id}",
                webhook_type="discord",
                url=hook.url,
                active=hook.active,
                events=["file.upload"],
            )
        )
    Webhook.objects.bulk_create(hooks)


def uncopy_discord_webhooks(apps, schema_editor):
    Webhook = apps.get_model("home", "Webhook")
    Webhook.objects.filter(webhook_type="discord").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("home", "0037_webhook"),
        ("oauth", "0026_passkeycredential"),
    ]

    operations = [
        migrations.RunPython(copy_discord_webhooks, uncopy_discord_webhooks),
    ]
