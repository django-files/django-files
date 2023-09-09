from django.contrib import admin
from django.utils.html import format_html

from home.models import Files, FileStats, ShortURLs

admin.site.site_header = 'Django Files Administration'


@admin.register(Files)
class FilesAdmin(admin.ModelAdmin):
    model = Files
    list_display = ('id', 'show_file', 'size', 'expr', 'mime', 'user', 'date',)
    list_filter = ('user', 'expr', 'mime',)
    readonly_fields = ('id', 'show_file', 'size', 'user', 'date',)
    search_fields = ('id', 'show_file', 'size', 'expr', 'mime', 'date',)
    ordering = ('-date',)

    @staticmethod
    def show_file(obj):
        return format_html('<a href="{0}">{1}</a>', obj.get_gallery_url(), obj.file.name)


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
