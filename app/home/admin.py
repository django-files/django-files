from django.contrib import admin
from django.utils.html import format_html
from home.models import (
    Albums,
    Files,
    FileStats,
    ShortURLs,
    Stream,
    StreamDiscordWebhooks,
    StreamHistory,
)


admin.site.site_header = "Django Files Administration"


@admin.register(Albums)
class AlbumAdmin(admin.ModelAdmin):
    model = Albums
    list_display = ("id", "name")


@admin.register(Files)
class FilesAdmin(admin.ModelAdmin):
    model = Files
    list_display = (
        "id",
        "show_file",
        "size",
        "expr",
        "mime",
        "user",
        "date",
    )
    list_filter = (
        "user",
        "expr",
        "mime",
    )
    readonly_fields = ("id", "show_file", "size", "user", "date", "avatar")
    search_fields = (
        "id",
        "show_file",
        "size",
        "expr",
        "mime",
        "date",
    )
    ordering = ("-date",)

    @staticmethod
    def show_file(obj):
        return format_html('<a href="{0}">{1}</a>', obj.get_gallery_url(), obj.file.name)


@admin.register(FileStats)
class FileStatsAdmin(admin.ModelAdmin):
    model = FileStats
    list_display = (
        "id",
        "user",
        "created_at",
    )
    list_filter = ("user",)
    readonly_fields = ("id", "user", "created_at", "stats")
    search_fields = ("id",)
    ordering = ("-created_at",)

    @admin.display(empty_value="Total")
    def view_user(self, obj):
        return obj.user

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(ShortURLs)
class ShortURLsAdmin(admin.ModelAdmin):
    model = ShortURLs
    list_display = (
        "id",
        "short",
        "views",
        "max",
        "url",
        "user",
        "created_at",
    )
    list_filter = ("user",)
    readonly_fields = (
        "id",
        "short",
        "views",
        "user",
        "created_at",
    )
    search_fields = (
        "id",
        "short",
        "url",
    )
    ordering = ("-created_at",)


@admin.register(Stream)
class StreamAdmin(admin.ModelAdmin):
    model = Stream
    list_display = (
        "name",
        "title",
        "user",
        "is_live",
        "started_at",
        "ended_at",
        "unique_views",
        "public",
        "viewer_limit",
    )
    list_filter = (
        "user",
        "is_live",
        "public",
        "started_at",
        "ended_at",
    )
    readonly_fields = (
        "name",
        "started_at",
        "unique_views",
    )
    search_fields = (
        "name",
        "title",
        "description",
        "user__username",
    )
    ordering = ("-started_at",)
    list_editable = ("is_live", "public", "viewer_limit")


@admin.register(StreamHistory)
class StreamHistoryAdmin(admin.ModelAdmin):
    model = StreamHistory
    list_display = (
        "id",
        "stream",
        "started_at",
        "ended_at",
        "peak_viewers",
        "avg_viewers",
        "title",
        "recording",
    )
    list_filter = (
        "stream",
        "started_at",
        "ended_at",
    )
    readonly_fields = (
        "id",
        "started_at",
    )
    search_fields = (
        "stream__name",
        "title",
        "description",
    )
    ordering = ("-started_at",)
    raw_id_fields = ("stream", "recording")


@admin.register(StreamDiscordWebhooks)
class StreamDiscordWebhooksAdmin(admin.ModelAdmin):
    model = StreamDiscordWebhooks
    list_display = (
        "id",
        "url",
        "hook_id",
        "guild_id",
        "channel_id",
        "active",
        "owner",
        "stream",
        "created_at",
        "updated_at",
    )
    list_filter = (
        "active",
        "owner",
        "stream",
        "created_at",
        "updated_at",
    )
    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
    )
    search_fields = (
        "url",
        "hook_id",
        "guild_id",
        "channel_id",
        "owner__username",
        "stream__name",
    )
    ordering = ("-created_at",)
    list_editable = ("active",)
    raw_id_fields = ("owner", "stream")
