from django.db import models

from home.util.rand import rand_color_hex
from oauth.models import CustomUser
from settings.managers import WebhooksManager


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
    discord_client_id = models.CharField(max_length=32, blank=True, null=True)
    discord_client_secret = models.CharField(max_length=128, blank=True, null=True)
    github_client_id = models.CharField(max_length=32, blank=True, null=True)
    github_client_secret = models.CharField(max_length=128, blank=True, null=True)
    s3_region = models.CharField(max_length=16, blank=True, null=True)
    s3_secret_key = models.CharField(max_length=128, blank=True, null=True)
    s3_secret_key_id = models.CharField(max_length=128, blank=True, null=True)
    # TODO: we should gate actually saving this fields on verifying we can list bucket with the credentials
    s3_bucket_name = models.CharField(max_length=128, blank=True, null=True)
    s3_cdn = models.CharField(
        max_length=128, blank=True, null=True,
        help_text='Replaces s3 hostname on urls to allow cdn use in front of s3 bucket.')

    def __str__(self):
        return f'<SiteSettings(site_url={self.site_url})>'

    def save(self, *args, **kwargs):
        if self.__class__.objects.count():
            self.pk = self.__class__.objects.first().pk
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = 'Setting'
        verbose_name_plural = 'Settings'


class Webhooks(models.Model):
    id = models.AutoField(primary_key=True)
    url = models.URLField(unique=True, verbose_name='Webhook URL')
    hook_id = models.CharField(max_length=32, blank=True, null=True)
    guild_id = models.CharField(max_length=32, blank=True, null=True)
    channel_id = models.CharField(max_length=32, blank=True, null=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Created', help_text='Hook Created Date.')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Updated', help_text='Hook Updated Date.')
    owner = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    objects = WebhooksManager()

    def __str__(self):
        return f'<Webhook(id={self.id} hook_id={self.hook_id} owner={self.owner.id})>'

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Webhook'
        verbose_name_plural = 'Webhooks'
