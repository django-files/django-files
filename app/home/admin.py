from django.contrib import admin

from .models import Files, FileStats, ShortURLs, SiteSettings, Webhooks

# admin.site.register(SiteSettings)

admin.site.site_header = 'Django Files Administration'

@admin.register(Files)
class FilesAdmin(admin.ModelAdmin):
    model = Files
    list_display = ('id', 'file', 'size', 'expr', 'mime', 'user', 'date',)
    # list_editable = ('expr',)
    list_filter = ('user', 'expr', 'mime',)
    readonly_fields = ('id', 'file', 'size', 'mime', 'user', 'date',)
    search_fields = ('id', 'file', 'size', 'expr', 'mime', 'date',)
    ordering = ('-date',)


@admin.register(FileStats)
class FileStatsAdmin(admin.ModelAdmin):
    model = FileStats
    list_display = ('id', 'user', 'created_at',)
    list_filter = ('user',)
    readonly_fields = ('id', 'user', 'created_at', 'stats')
    search_fields = ('id',)
    ordering = ('-created_at',)

    @admin.display(empty_value="Total")
    def view_user(self, obj):
        return obj.user


@admin.register(ShortURLs)
class ShortURLsAdmin(admin.ModelAdmin):
    model = ShortURLs
    list_display = ('id', 'short', 'views', 'max', 'url', 'user', 'created_at',)
    list_filter = ('user',)
    readonly_fields = ('id', 'short', 'views', 'user', 'created_at',)
    search_fields = ('id', 'short', 'url',)
    ordering = ('-created_at',)


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
    list_display = ('id', 'site_url',)
    readonly_fields = ('id',)
    # search_fields = ('id', 'site_url',)
    # ordering = ('-created_at',)
