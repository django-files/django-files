import os
from django.db import models
from packaging import version

from home.util.rand import rand_color_hex
from settings.managers import SiteSettingsManager


class SiteSettings(models.Model):
    id = models.AutoField(primary_key=True)
    site_url = models.URLField(max_length=128, blank=True, null=True, verbose_name='Site URL')
    site_title = models.CharField(max_length=64, default='Django Files', verbose_name='Site Title')
    site_description = models.TextField(max_length=155, verbose_name='Site Description',
                                        default=('A Feature Packed Self-Hosted Django/Docker File Manager for '
                                                 'Sharing Files with ShareX, Flameshot and Much more...'))
    site_color = models.CharField(default=rand_color_hex, max_length=7, verbose_name='Site Color',
                                  help_text='Site Theme Color for Site Embeds')
    pub_load = models.BooleanField(default=False, verbose_name='Public Upload',
                                   help_text='Allow Public Uploads')
    oauth_reg = models.BooleanField(default=False, verbose_name='Oauth Reg',
                                    help_text='Allow Oauth Auto Registration')
    two_factor = models.BooleanField(default=False, verbose_name='Two-Factor',
                                     help_text='Require Two-Factor Authentication')
    duo_auth = models.BooleanField(default=False, verbose_name='Duo AUth',
                                   help_text='Require Duo Authentication')
    oauth_redirect_url = models.URLField(max_length=128, blank=True, null=True)
    discord_client_id = models.CharField(max_length=32, default='')
    discord_client_secret = models.CharField(max_length=128, default='')
    github_client_id = models.CharField(max_length=32, default='')
    github_client_secret = models.CharField(max_length=128, default='')
    s3_region = models.CharField(max_length=16, default='')
    s3_secret_key = models.CharField(max_length=128, default='')
    s3_secret_key_id = models.CharField(max_length=128, default='')
    # TODO: we should gate actually saving this fields on verifying we can list bucket with the credentials
    s3_bucket_name = models.CharField(max_length=128, default='')
    s3_cdn = models.CharField(max_length=128, default='',
                              help_text='Replaces s3 hostname on urls to allow cdn use in front of s3 bucket.')
    latest_version = models.CharField(max_length=32, default='0.0.0')
    objects = SiteSettingsManager()

    def __str__(self):
        return f'<SiteSettings(site_url={self.site_url})>'

    class Meta:
        verbose_name = 'Setting'
        verbose_name_plural = 'Settings'

    def save(self, *args, **kwargs):
        if self.__class__.objects.count():
            self.pk = self.__class__.objects.first().pk
        super().save(*args, **kwargs)

    def update_available(self, latest_version=None):
        try:
            app_version = version.parse(os.environ.get('APP_VERSION'))
            latest_version = version.parse(latest_version or self.latest_version)
            if latest_version > app_version:
                return True
            return False
        except version.InvalidVersion:
            return False
