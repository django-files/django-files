from django.contrib import admin

from settings.models import SiteSettings, Webhooks

admin.site.site_header = 'Django Files Administration'


@admin.register(Webhooks)
class WebhooksAdmin(admin.ModelAdmin):
    model = Webhooks
    list_display = ('id', 'hook_id', 'guild_id', 'channel_id', 'owner', 'created_at',)
    list_filter = ('owner',)
    readonly_fields = ('id', 'hook_id', 'guild_id', 'channel_id', 'owner', 'created_at',)
    search_fields = ('id', 'hook_id', 'guild_id', 'channel_id', 'owner',)
    ordering = ('-created_at',)


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    model = SiteSettings
    list_display = ('id', 'site_url', 'oauth_reg', 'duo_auth',)
    readonly_fields = ('id',)
