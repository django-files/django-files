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
    expr = models.CharField(default='', max_length=32,  verbose_name='Expire Time', help_text='File Expire Time.')
    objects = FilesManager()

    def __str__(self):
        return f'<Files(id={self.id} size={self.size} name={self.name})>'

    class Meta:
        ordering = ['-date']
        verbose_name = 'Files'
        verbose_name_plural = 'Files'

    def get_url(self):
        return settings.SITE_URL + self.file.url

    def get_size(self):
        num = self.size
        for unit in ["", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"]:
            if abs(num) < 1024.0:
                return f"{num:3.1f} {unit}B"
            num /= 1024.0
        return f"{num:.1f} YiB"


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

    def __str__(self):
        return f'<Webhook(id={self.id} hook_id={self.hook_id} owner={self.owner.id})>'

    class Meta:
        verbose_name = 'Webhook'
        verbose_name_plural = 'Webhooks'


class SiteSettings(models.Model):
    id = models.AutoField(primary_key=True)
    site_url = models.URLField(max_length=128, unique=True, verbose_name='Site URL')

    def __str__(self):
        return f'<Settings(site_url={self.site_url})>'

    def save(self, *args, **kwargs):
        if self.__class__.objects.count():
            self.pk = self.__class__.objects.first().pk
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = 'Settings'
        verbose_name_plural = 'Settings'
