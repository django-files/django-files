from django.contrib import admin
from settings.models import SiteSettings

admin.site.site_header = "Django Files Administration"


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
