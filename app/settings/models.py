import zoneinfo
from django.db import models

from home.util.rand import rand_color_hex
from home.util.misc import bytes_to_human_read
from settings.managers import SiteSettingsManager


class SiteSettings(models.Model):
    TIMEZONE_CHOICES = zip(sorted(zoneinfo.available_timezones()), sorted(zoneinfo.available_timezones()))

    id = models.AutoField(primary_key=True)
    site_url = models.URLField(max_length=128, blank=True, null=True, verbose_name='Site URL')
    site_title = models.CharField(max_length=64, default='Django Files', verbose_name='Site Title')
    timezone = models.CharField(max_length=255, choices=TIMEZONE_CHOICES, default='America/Los_Angeles')
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
    discord_client_id = models.CharField(max_length=32, blank=True, default='')
    discord_client_secret = models.CharField(max_length=128, blank=True, default='')
    github_client_id = models.CharField(max_length=32, blank=True, default='')
    github_client_secret = models.CharField(max_length=128, blank=True, default='')
    google_client_id = models.CharField(max_length=75, blank=True, default='')
    google_client_secret = models.CharField(max_length=128, blank=True, default='')
    local_auth = models.BooleanField(default=True)
    s3_region = models.CharField(max_length=16, blank=True, default='')
    s3_secret_key = models.CharField(max_length=128, blank=True, default='')
    s3_secret_key_id = models.CharField(max_length=128, blank=True, default='')
    # TODO: we should gate actually saving this fields on verifying we can list bucket with the credentials
    s3_bucket_name = models.CharField(max_length=128, blank=True, default='')
    s3_cdn = models.CharField(max_length=128, blank=True, default='',
                              help_text='Replaces s3 hostname on urls to allow cdn use in front of s3 bucket.')
    latest_version = models.CharField(max_length=32, blank=True, default='')
    default_user_storage_quota = models.PositiveBigIntegerField(
        default=0,
        help_text="Default storage capacity for new users in bytes."
        )
    global_storage_quota = models.PositiveBigIntegerField(
        default=0,
        help_text="Total storage capacity for entire django files deployment in bytes."
        )
    global_storage_usage = models.PositiveBigIntegerField(default=0,
                                                          help_text="Current global storage usage in bytes.")
    show_setup = models.BooleanField(default=True)
    objects = SiteSettingsManager()

    def __str__(self):
        return self.site_url

    def __repr__(self):
        return f'<SiteSettings(site_url={self.site_url})>'

    class Meta:
        verbose_name = 'Site Setting'
        verbose_name_plural = 'Site Settings'

    def save(self, *args, **kwargs):
        if self.__class__.objects.count():
            self.pk = self.__class__.objects.first().pk
        super().save(*args, **kwargs)

    def get_remaining_global_storage_quota_bytes(self):
        if self.global_storage_quota:
            return self.global_storage_quota - self.global_storage_usage
        return 0

    def get_global_storage_quota_usage_pct(self) -> int:
        return int((self.global_storage_usage / self.global_storage_quota) * 100)

    def get_global_storage_usage_human_read(self):
        return bytes_to_human_read(self.global_storage_usage)

    def get_global_storage_quota_human_read(self):
        return bytes_to_human_read(self.global_storage_quota)

    def get_default_user_storage_quota_human_read(self):
        return bytes_to_human_read(self.default_user_storage_quota)

    def get_local_auth(self):
        # We want to fail safe, where if oauth is not configured we keep local auth enabled
        if self.google_client_id == self.discord_client_id == self.github_client_id == '':
            return True
        return self.local_auth
