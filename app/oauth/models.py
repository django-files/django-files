from django.contrib.auth.models import AbstractUser
from django.db import models
from django.templatetags.static import static

# from oauth.providers.discord import DiscordProfile
from home.util.rand import rand_string, rand_color_hex


class CustomUser(AbstractUser):
    id = models.AutoField(primary_key=True)
    # discord = models.ForeignKey(DiscordProfile, on_delete=models.CASCADE)
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
        if self.discord.avatar:
            return f'https://cdn.discordapp.com/avatars/' \
                   f'{ self.discord.id }/{ self.discord.avatar }.png'
        return static('images/assets/default.png')

    def __str__(self):
        return self.first_name or self.username

    def __repr__(self):
        return f'<CustomUser(id={self.id}, username={self.username}>'


class Discord(models.Model):
    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        primary_key=True,
    )
    id = models.IntegerField()
    profile = models.JSONField(null=True, blank=True)
    avatar = models.CharField(null=True, blank=True, max_length=32)
    access_token = models.CharField(null=True, blank=True, max_length=32)
    refresh_token = models.CharField(null=True, blank=True, max_length=32)
    expires_in = models.DateTimeField(null=True, blank=True)
