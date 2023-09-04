from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from oauth.models import CustomUser, Discord, Github

admin.site.register(Discord)
admin.site.register(Github)


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'first_name', 'is_staff', 'is_superuser',)
    list_filter = ('is_superuser',)
    search_fields = ('username',)
    ordering = ('first_name',)
    readonly_fields = ('last_name',)
    fieldsets = UserAdmin.fieldsets + (
        ('OAuth', {'fields': (
            'default_color', 'default_expire', 'nav_color_1', 'nav_color_2',
            'remove_exif_geo', 'remove_exif', 'show_exif_preview',
        )}),
    )
