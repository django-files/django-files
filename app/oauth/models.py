import datetime
import zoneinfo
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.shortcuts import reverse
from django.templatetags.static import static
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from home.util.rand import rand_string, rand_color_hex
from oauth.managers import DiscordWebhooksManager, UserInvitesManager
from settings.models import SiteSettings


def rand_invite():
    return rand_string(16)


class CustomUser(AbstractUser):
    TIMEZONE_CHOICES = zip(sorted(zoneinfo.available_timezones()), sorted(zoneinfo.available_timezones()))

    class UploadNameFormats(models.TextChoices):
        NAME = "name", _("name")
        RAND = "rand", _("random")
        DATE = "date", _("date")
        UUID = "uuid", _("uuid")

    id = models.AutoField(primary_key=True)
    authorization = models.CharField(default=rand_string, max_length=32)
    timezone = models.CharField(max_length=255, choices=TIMEZONE_CHOICES, default='America/Los_Angeles')
    default_expire = models.CharField(default='', blank=True, max_length=32)
    default_color = models.CharField(default=rand_color_hex, max_length=7)
    nav_color_1 = models.CharField(default='#130e36', max_length=7)
    nav_color_2 = models.CharField(default='#1e1c21', max_length=7)
    remove_exif_geo = models.BooleanField(default=False, verbose_name='No EXIF Geo',
                                          help_text='Removes geo exif data from images on upload.')
    remove_exif = models.BooleanField(default=False, verbose_name='No EXIF',
                                      help_text='Removes exif data from images on upload.')
    show_exif_preview = models.BooleanField(default=True, verbose_name='EXIF Preview',
                                            help_text='Default value if to show exif data on previews and unfurls.')
    default_upload_name_format = models.CharField(max_length=4, choices=UploadNameFormats.choices,
                                                  default=UploadNameFormats.NAME)
    default_file_private = models.BooleanField(default=False, verbose_name='Default File Private',
                                               help_text="If enabled file default to private when not specified.")
    default_file_password = models.BooleanField(default=False, verbose_name='Auto File Password',
                                                help_text='Generates file password on upload.')
    show_setup = models.BooleanField(default=False)

    def __str__(self):
        return self.get_name()

    def __repr__(self):
        return f'<CustomUser(id={self.id}, username={self.username}>'

    def get_name(self):
        return self.first_name or self.username

    def get_avatar(self):
        # TODO: Let User Choose Profile Icon or Chose by Active Login
        if hasattr(self, 'discord') and getattr(self.discord, 'avatar'):
            return f'https://cdn.discordapp.com/avatars/' \
                   f'{ self.discord.id }/{ self.discord.avatar }.png'
        if hasattr(self, 'github') and getattr(self.github, 'avatar'):
            return self.github.avatar
        # TODO: Let User Upload an Avatar
        return static('images/assets/default.png')


class UserInvites(models.Model):
    id = models.AutoField(primary_key=True)
    invite = models.CharField(default=rand_invite, max_length=16)
    owner = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    expire = models.IntegerField(default=0, verbose_name='Expire', help_text='Expiration Seconds.')
    max_uses = models.IntegerField(default=1, verbose_name='Max', help_text='Max Uses.')
    uses = models.IntegerField(default=0, verbose_name='Uses', help_text='Total Uses.')
    user_ids = models.JSONField(default=list, verbose_name='User IDs', help_text='Users who Used Invite.')
    super_user = models.BooleanField(default=False, verbose_name='Super', help_text='Invited Users are Super Users.')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Created', help_text='Invite Created Date.')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Updated', help_text='Invite Updated Date.')
    objects = UserInvitesManager()

    def __str__(self):
        return self.invite

    def __repr__(self):
        return f'<UserInvites(id={self.id}, owner={self.owner}, valid={self.is_valid()}>'

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'User Invite'
        verbose_name_plural = 'User Invites'

    def use_invite(self, user_id):
        if not self.is_valid():
            return False
        self.user_ids.append(user_id)
        self.uses += 1
        self.save()
        return True

    def is_valid(self):
        if self.max_uses:
            if not self.uses < self.max_uses:
                return False
        if self.expire:
            delta = timezone.now() - self.created_at
            if self.expire <= delta.seconds:
                return False
        return True

    def expire_date(self):
        if self.expire:
            return self.created_at + datetime.timedelta(seconds=self.expire)
        return None

    def get_uri(self):
        return reverse('home:invite', kwargs={'invite': self.invite})

    def get_url(self, site_url):
        uri = reverse('home:invite', kwargs={'invite': self.invite})
        return site_url + uri

    def build_url(self):
        uri = reverse('home:invite', kwargs={'invite': self.invite})
        return SiteSettings.objects.settings().site_url + uri


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
