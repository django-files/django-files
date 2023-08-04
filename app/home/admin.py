from django.contrib import admin

from .models import Files, Webhooks, SiteSettings


admin.site.register(Webhooks)
admin.site.register(SiteSettings)


@admin.register(Files)
class FilesAdmin(admin.ModelAdmin):
    model = Files
    list_display = ('id', 'name', 'size', 'mime', 'date', 'user',)
    readonly_fields = ('id', 'name', 'size', 'mime', 'date', 'user',)
    search_fields = ('id', 'name', 'size', 'mime', 'date', 'user',)
    ordering = ('-date',)
