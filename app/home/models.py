from django.db import models
from django.conf import settings
from oauth.models import CustomUser

from .managers import FilesManager


class Files(models.Model):
    upload_to = '.'
    id = models.AutoField(primary_key=True)
    file = models.FileField(upload_to=upload_to)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    size = models.IntegerField(default=0, verbose_name='File Size', help_text='File Size in Bytes.')
    mime = models.CharField(max_length=255, null=True, blank=True,
                            verbose_name='File MIME', help_text='File MIME Type.')
    name = models.CharField(max_length=255, null=True, blank=True,
                            verbose_name='File Name', help_text='File Name Basename.')
    info = models.CharField(max_length=255, null=True, blank=True,
                            verbose_name='File Info', help_text='File Information.')
    date = models.DateTimeField(auto_now_add=True, verbose_name='Date Created', help_text='File Created Date.')
    edit = models.DateTimeField(auto_now=True, verbose_name='Date Edited', help_text='File Edited Date.')
    expr = models.CharField(default='', max_length=32, blank=True,
                            verbose_name='Expire Time', help_text='File Expire Time.')
    objects = FilesManager()

    def __str__(self):
        return f'<Files(id={self.id} size={self.size} name={self.name})>'

    class Meta:
        ordering = ['-date']
        verbose_name = 'File'
        verbose_name_plural = 'Files'

    def get_url(self):
        site_settings = SiteSettings.objects.get(pk=1)
        return site_settings.site_url + self.file.url

    def get_size(self):
        num = self.size
        return self.get_size_of(num)

    @staticmethod
    def get_size_of(num):
        for unit in ["", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"]:
            if abs(num) < 1024.0:
                return f"{num:3.1f} {unit}B"
            num /= 1024.0
        return f"{num:.1f} YiB"


class FileStats(models.Model):
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(CustomUser, blank=True, null=True, on_delete=models.CASCADE)
    stats = models.JSONField(verbose_name='Stats JSON')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Stats Created', help_text='Stats Created Date.')
    # objects = FileStatsManager()

    def __str__(self):
        return f'<FileStats(id={self.id}, user_id={self.user_id})>'

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'FileStat'
        verbose_name_plural = 'FileStats'


class ShortURLs(models.Model):
    id = models.AutoField(primary_key=True)
    url = models.URLField(unique=True, verbose_name='Short URL', help_text='ShortURL Short URL.')
    views = models.IntegerField(verbose_name='ShortURL Views')
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='ShortURL Created',
                                      help_text='ShortURL Created Date.')

    def __str__(self):
        return f'<ShortURLs(id={self.id}, user_id={self.user_id})>'

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Short URL'
        verbose_name_plural = 'Short URLs'


class SiteSettings(models.Model):
    id = models.AutoField(primary_key=True)
    site_url = models.URLField(default=settings.SITE_URL, max_length=128, verbose_name='Site URL')

    def __str__(self):
        return f'<Settings(site_url={self.site_url})>'

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
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Date Created', help_text='Hook Created Date.')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Date Edited', help_text='Hook Edited Date.')
    owner = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    # objects = WebhooksManager()

    def __str__(self):
        return f'<Webhook(id={self.id} hook_id={self.hook_id} owner={self.owner.id})>'

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Webhook'
        verbose_name_plural = 'Webhooks'
