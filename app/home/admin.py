from django.contrib import admin

from .models import Files, Webhooks


admin.site.register(Webhooks)


@admin.register(Files)
class FilesAdmin(admin.ModelAdmin):
    model = Files
    list_display = ('id', 'file', 'date',)
    readonly_fields = ('id', 'file', 'date',)
    search_fields = ('id', 'file', 'date',)
    ordering = ('-date',)
