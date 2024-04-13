from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from oauth.models import CustomUser, Discord, Github, UserInvites

admin.site.register(Discord)
admin.site.register(Github)


@admin.register(UserInvites)
class UserInvitesAdmin(admin.ModelAdmin):
    list_display = ('invite', 'max_uses', 'uses', 'super_user', 'owner',)
    list_filter = ('owner', 'super_user',)
    readonly_fields = ('uses', 'user_ids',)


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'first_name', 'is_staff', 'is_superuser',)
    list_filter = ('is_superuser',)
    search_fields = ('username',)
    ordering = ('first_name',)
    readonly_fields = ('last_name', 'storage_usage')
    fieldsets = UserAdmin.fieldsets + (
        ('OAuth', {'fields': (
            'timezone', 'default_color', 'default_expire', 'nav_color_1', 'nav_color_2',
            'remove_exif_geo', 'remove_exif', 'show_exif_preview', 'default_file_private',
            'default_file_password', 'default_upload_name_format', 'storage_quota', 'storage_usage'
        )}),
    )
