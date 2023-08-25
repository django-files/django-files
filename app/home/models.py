import validators
from django.db import models
from django.shortcuts import reverse

from home.managers import FilesManager, FileStatsManager, ShortURLsManager, WebhooksManager
from oauth.models import CustomUser
from home.util.storage import StoragesRouterFileField


class Files(models.Model):
    upload_to = '.'
    id = models.AutoField(primary_key=True)
    file = StoragesRouterFileField(upload_to=upload_to)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    size = models.IntegerField(default=0, verbose_name='Size', help_text='File Size in Bytes.')
    mime = models.CharField(max_length=255, null=True, blank=True, verbose_name='MIME', help_text='File MIME Type.')
    name = models.CharField(max_length=255, null=True, blank=True, verbose_name='Name', help_text='File Name.')
    info = models.CharField(max_length=255, null=True, blank=True, verbose_name='Info', help_text='File Information.')
    expr = models.CharField(default='', max_length=32, blank=True, verbose_name='Expiration', help_text='File Expire.')
    view = models.IntegerField(default=0, verbose_name='Views', help_text='File Views.')
    maxv = models.IntegerField(default=0, verbose_name='Max', help_text='Max Views.')
    exif = models.JSONField(default=dict, verbose_name="EXIF Metadata", help_text="JSON formatted exif metadata.")
    date = models.DateTimeField(auto_now_add=True, verbose_name='Created', help_text='File Created Date.')
    edit = models.DateTimeField(auto_now=True, verbose_name='Edited', help_text='File Edited Date.')
    meta = models.JSONField(default=dict, verbose_name="Metadata", help_text="JSON formatted metadata.")
    objects = FilesManager()

    def __str__(self):
        return f'<File(id={self.id} size={self.size} name={self.name})>'

    class Meta:
        ordering = ['-date']
        verbose_name = 'File'
        verbose_name_plural = 'Files'

    def get_url(self, view: bool = False, download: bool = False) -> str:
        site_settings = SiteSettings.objects.get(pk=1)
        if view:
            self.view += 1
            self.save()
        if not validators.url(self.file.url):
            return site_settings.site_url + self.file.url
        if not download:
            return self.file.url
        # TODO: access protected member, look into how to better handle this
        return self.file.file._storage.url(
            self.file.file.name,
            parameters={'ResponseContentDisposition': f'attachment; filename={self.file.file.name}'})

    def preview_url(self) -> str:
        site_settings = SiteSettings.objects.get(pk=1)
        uri = reverse('home:url-route', kwargs={'filename': self.file.name})
        return site_settings.site_url + uri

    def preview_uri(self) -> str:
        return reverse('home:url-route', kwargs={'filename': self.file.name})

    def get_size(self) -> str:
        num = self.size
        return self.get_size_of(num)

    @staticmethod
    def get_size_of(num: int) -> str:
        for unit in ["", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"]:
            if abs(num) < 1024.0:
                return f"{num:3.1f} {unit}B"
            num /= 1024.0
        return f"{num:.1f} YiB"


class FileStats(models.Model):
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(CustomUser, blank=True, null=True, on_delete=models.CASCADE)
    stats = models.JSONField(verbose_name='Stats JSON', help_text='Stats JSON Data.')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Created', help_text='Stats Updated Date.')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Updated', help_text='Stats Updated Date.')
    objects = FileStatsManager()

    def __str__(self):
        return f'<FileStat(id={self.id}, user_id={self.user_id})>'

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'FileStat'
        verbose_name_plural = 'FileStats'


class ShortURLs(models.Model):
    id = models.AutoField(primary_key=True)
    short = models.CharField(max_length=255, unique=True, verbose_name='Short', help_text='Short Link ID.')
    url = models.URLField(verbose_name='Destination URL', help_text='Target URL for the ShortURL.')
    max = models.IntegerField(default=0, verbose_name='Max', help_text='Max ShortURL Views')
    views = models.IntegerField(default=0, verbose_name='Views', help_text='Total ShortURL Views')
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Created', help_text='ShortURL Created Date.')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Updated', help_text='ShortURL Updated Date.')
    objects = ShortURLsManager()

    def __str__(self):
        return f'<ShortURL(id={self.id}, user_id={self.user_id})>'

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Short URL'
        verbose_name_plural = 'Short URLs'


class SiteSettings(models.Model):
    id = models.AutoField(primary_key=True)
    site_url = models.URLField(max_length=128, blank=True, null=True, verbose_name='Site URL')
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
