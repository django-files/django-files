from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html

from home.util.storage import use_s3
from oauth.models import CustomUser, Discord, Github, UserInvites, UserBackups

# admin.site.register(UserBackups)
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
    readonly_fields = ('last_name',)
    fieldsets = UserAdmin.fieldsets + (
        ('OAuth', {'fields': (
            'timezone', 'default_color', 'default_expire', 'nav_color_1', 'nav_color_2',
            'remove_exif_geo', 'remove_exif', 'show_exif_preview', 'default_file_private',
            'default_file_password', 'default_upload_name_format'
        )}),
    )


@admin.register(UserBackups)
class UserBackupsAdmin(admin.ModelAdmin):
    model = UserBackups
    list_display = ('id', 'show_file', 'user', 'finished',)
    list_filter = ('user', 'finished',)
    readonly_fields = ('id', 'file', 'finished',)
    search_fields = ('id', 'file',)
    ordering = ('-created_at',)

    @staticmethod
    def show_file(obj):
        print(f'obj.file.name: {obj.file.name}')
        print(f'obj.get_gallery_url(): {obj.get_gallery_url()}')
        return format_html('<a href="{0}">{1}</a>', obj.get_gallery_url(), obj.file.name)
