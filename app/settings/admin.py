from django.contrib import admin
from oauth.models import DiscordWebhooks
from settings.models import SiteSettings


admin.site.site_header = "Django Files Administration"


@admin.register(DiscordWebhooks)
class DiscordWebhooksAdmin(admin.ModelAdmin):
    model = DiscordWebhooks
    list_display = (
        "id",
        "hook_id",
        "guild_id",
        "channel_id",
        "owner",
        "created_at",
    )
    list_filter = ("owner",)
    readonly_fields = (
        "id",
        "hook_id",
        "guild_id",
        "channel_id",
        "owner",
        "created_at",
    )
    search_fields = (
        "id",
        "hook_id",
        "guild_id",
        "channel_id",
        "owner",
    )
    ordering = ("-created_at",)


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    model = SiteSettings
    list_display = (
        "id",
        "site_url",
        "oauth_reg",
        "duo_auth",
    )
    exclude = (
        "latest_version",
        "id",
    )
    readonly_fields = ("global_storage_usage",)

    def has_add_permission(self, request, obj=None):
        return False
