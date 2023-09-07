from django.contrib.auth.models import AbstractUser
from django.db import models
from django.templatetags.static import static

from home.util.rand import rand_string, rand_color_hex
from oauth.managers import DiscordWebhooksManager


class CustomUser(AbstractUser):
    id = models.AutoField(primary_key=True)
    show_setup = models.BooleanField(default=False)
    authorization = models.CharField(default=rand_string, max_length=32)
    default_expire = models.CharField(default='', blank=True, max_length=32)
    default_color = models.CharField(default=rand_color_hex, max_length=7)
    nav_color_1 = models.CharField(default='#130e36', max_length=7)
    nav_color_2 = models.CharField(default='#1e1c21', max_length=7)
    remove_exif_geo = models.BooleanField(
        default=False, verbose_name='No EXIF Geo',
        help_text='Removes geo exif data from images on upload.')
    remove_exif = models.BooleanField(
        default=False, verbose_name='No EXIF',
        help_text='Removes exif data from images on upload.')
    show_exif_preview = models.BooleanField(
        default=False, verbose_name='EXIF Preview',
        help_text='Shows exif data on previews and unfurls.')

    def get_avatar(self):
        # TODO: Let User Choose Profile Icon or Chose by Active Login
        if hasattr(self, 'discord') and getattr(self.discord, 'avatar'):
            return f'https://cdn.discordapp.com/avatars/' \
                   f'{ self.discord.id }/{ self.discord.avatar }.png'
        if hasattr(self, 'github') and getattr(self.github, 'avatar'):
            return self.github.avatar
        return static('images/assets/default.png')

    def __str__(self):
        return self.first_name or self.username

    def __repr__(self):
        return f'<CustomUser(id={self.id}, username={self.username}>'


class UserInvites(models.Model):
    id = models.AutoField(primary_key=True)
    invite = models.CharField(default=rand_string(16), max_length=16)
    expire = models.IntegerField(default=0)
    super_user = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Created', help_text='Invite Created Date.')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Updated', help_text='Invite Updated Date.')
    owner = models.ForeignKey(CustomUser, on_delete=models.CASCADE)

    def __repr__(self):
        return f'<UserInvites(id={self.id}, owner={self.owner}>'

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'User Invite'
        verbose_name_plural = 'User Invites'

    # def get_url(self):
    #     # not implemented
    #     pass


class Discord(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, primary_key=True)
    id = models.IntegerField()
    profile = models.JSONField(null=True, blank=True)
    avatar = models.CharField(null=True, blank=True, max_length=32)
    access_token = models.CharField(null=True, blank=True, max_length=32)
    refresh_token = models.CharField(null=True, blank=True, max_length=32)
    expires_in = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Discord'
        verbose_name_plural = 'Discords'


class DiscordWebhooks(models.Model):
    id = models.AutoField(primary_key=True)
    url = models.URLField(unique=True, verbose_name='Webhook URL')
    hook_id = models.CharField(max_length=32, blank=True, null=True)
    guild_id = models.CharField(max_length=32, blank=True, null=True)
    channel_id = models.CharField(max_length=32, blank=True, null=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Created', help_text='Hook Created Date.')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Updated', help_text='Hook Updated Date.')
    owner = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    objects = DiscordWebhooksManager()

    def __str__(self):
        return f'<Webhook(id={self.id} hook_id={self.hook_id} owner={self.owner.id})>'

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Discord Webhook'
        verbose_name_plural = 'Discord Webhooks'


class Github(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, primary_key=True)
    id = models.IntegerField()
    profile = models.JSONField(null=True, blank=True)
    avatar = models.CharField(null=True, blank=True, max_length=32)
    access_token = models.CharField(null=True, blank=True, max_length=32)

    class Meta:
        verbose_name = 'Github'
        verbose_name_plural = 'Githubs'
