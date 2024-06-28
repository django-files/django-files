from django.db import models
from django.db.models import F
from django.shortcuts import reverse
from django.conf import settings
from django.core.cache import cache

from home.managers import FilesManager, FileStatsManager, ShortURLsManager, AlbumsManager
from home.util.storage import StoragesRouterFileField, use_s3
from home.util.nginx import sign_nginx_urls
from oauth.models import CustomUser


class Albums(models.Model):
    class Meta:
        ordering = ['-date']
        verbose_name = 'Album'
        verbose_name_plural = 'Albums'

    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    name = models.CharField(max_length=255, blank=False, unique=True, verbose_name='Name', help_text='Album Name.')
    password = models.CharField(default='', max_length=255, blank=True, verbose_name='Album Password')
    private = models.BooleanField(default=False, verbose_name='Private Album')
    info = models.CharField(default='', max_length=255, blank=True, verbose_name='Info', help_text='Album Information.')
    view = models.IntegerField(default=0, verbose_name='Views', help_text='Album Views.')
    maxv = models.IntegerField(default=0, verbose_name='Max', help_text='Max Views.')
    expr = models.CharField(default='', max_length=32, blank=True, verbose_name='Expiration', help_text='Album Expire.')
    date = models.DateTimeField(auto_now_add=True, verbose_name='Created', help_text='Album Created Date.')

    objects = AlbumsManager()


class Files(models.Model):
    upload_to = '.'
    id = models.AutoField(primary_key=True)
    albums = models.ManyToManyField(Albums, blank=True)
    file = StoragesRouterFileField(upload_to=upload_to)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    size = models.IntegerField(default=0, verbose_name='Size', help_text='File Size in Bytes.')
    mime = models.CharField(default='', max_length=255, blank=True, verbose_name='MIME', help_text='File MIME Type.')
    name = models.CharField(default='', max_length=255, blank=True, verbose_name='Name', help_text='File Name.')
    info = models.CharField(default='', max_length=255, blank=True, verbose_name='Info', help_text='File Information.')
    expr = models.CharField(default='', max_length=32, blank=True, verbose_name='Expiration', help_text='File Expire.')
    view = models.IntegerField(default=0, verbose_name='Views', help_text='File Views.')
    maxv = models.IntegerField(default=0, verbose_name='Max', help_text='Max Views.')
    exif = models.JSONField(default=dict, blank=True, verbose_name="EXIF Metadata",
                            help_text="JSON formatted exif metadata.")
    date = models.DateTimeField(auto_now_add=True, verbose_name='Created', help_text='File Created Date.')
    edit = models.DateTimeField(auto_now=True, verbose_name='Edited', help_text='File Edited Date.')
    meta = models.JSONField(default=dict, blank=True, verbose_name="Metadata", help_text="JSON formatted metadata.")
    meta_preview = models.BooleanField(default=True, help_text="Show metadata on previews.")
    password = models.CharField(default='', max_length=255, blank=True, verbose_name='File Password')
    private = models.BooleanField(default=False, verbose_name='Private File')
    objects = FilesManager()
    avatar = models.BooleanField(default=False, help_text="Determines file is a user avatar.")
    thumb = StoragesRouterFileField(upload_to=f'{upload_to}/thumbs/', null=True, blank=True)

    # def save(self, *args, **kwargs):
    #     return super(Files, self).save(*args, **kwargs)

    def __str__(self):
        return f'<File(id={self.id} size={self.size} name={self.name})>'

    class Meta:
        ordering = ['-date']
        verbose_name = 'File'
        verbose_name_plural = 'Files'

    def get_url(self, view: bool = False, download: bool = False, expire: int = None, abs_url: str = '') -> str:
        """Gets a static url to a file object.
        view counts url retrieval as a view
        download makes the static url force download
        expire overrides the signing expire time for cloud storage urls
        """
        if view:
            Files.objects.filter(pk=self.pk).update(view=F('view') + 1)
        # ######## Download Static URL ########
        if download:
            # check if download url cached, if not serve new one
            if use_s3():
                if (download_url := cache.get(f"file.urlcache.download.{self.pk}", )) is None:
                    # TODO: access protected member, look into how to better handle this
                    download_url = self.file.file._storage.url(
                        self.file.file.name,
                        parameters={'ResponseContentDisposition': f'attachment; filename={self.file.file.name}'})
                    cache.set(f"file.urlcache.download.{self.pk}", download_url,
                              (settings.STATIC_QUERYSTRING_EXPIRE - 60))
                return download_url
                # skip cache behavior for local file storage
            url = self.file.url + '?download=true'
            return abs_url + url + self._sign_nginx_url(self.file.url).replace('?', '&')
        # ######## Custom Expire Generic Static URL (cloud only) ########
        if expire is not None:
            # we cant cache this since it will be a custom value
            # if expire is overridden set expire via url method
            return self.file.file._storage.url(
                self.file.file.name,
                expire=86400)
        # ######## Generic Static URL ########
        if use_s3():
            # check if generic static url is cached if not generate and cache, honors AWS settings sign expire time
            if (url := cache.get(f"file.urlcache.raw.{self.pk}", )) is None:
                url = self.file.url
                cache.set(f"file.urlcache.raw.{self.pk}", url, (settings.STATIC_QUERYSTRING_EXPIRE - 60))
            return url
        return abs_url + self.file.url + self._sign_nginx_url(self.file.url)

    def get_meta_static_url(self) -> str:
        """
        Otherwise some clients may cache an old meta url and it will fail to display when using signed urls.
        There may also be future cases where we dont want to issue this url for private/pw protected files.
        """
        if use_s3():
            if (meta_static_url := cache.get(f"file.urlcache.meta_static.{self.pk}")) is None:
                # TODO: access protected member, look into how to better handle this
                try:
                    meta_static_url = self.file.file._storage.url(
                        self.file.file.name,
                        expire=86400
                    )
                except FileNotFoundError:
                    return ''
                cache.set(f"file.urlcache.meta_static.{self.pk}", meta_static_url, 10800)
            return meta_static_url
        return self.get_url(False)

    def get_gallery_url(self, abs_url: str = '') -> str:
        """Generates a static url for use on a gallery page."""
        use = self.thumb if self.thumb else self.file
        if use_s3():
            # only want cache for s3
            # override signing expire on gallery urls to avoid cached gallery pages from failing to load
            # TODO: access protected member, look into how to better handle this
            if (gallery_url := cache.get(f"file.urlcache.gallery.{self.pk}")) is None:
                try:
                    print("Gallery url cache is empty")
                    gallery_url = self.file.file._storage.url(
                        use.file.name,
                        expire=86400
                    )
                except FileNotFoundError:
                    return ''
                # intentionally expire cache before gallery url signing expires
                cache.set(f"file.urlcache.gallery.{self.pk}", gallery_url, 72000)
            return gallery_url
        return abs_url + use.url + self._sign_nginx_url(use.url)

    def _sign_nginx_url(self, uri: str) -> str:
        if use_s3():
            # guard against using this in cloud settings, or at least not s3 for now
            return ''
        return sign_nginx_urls(uri)

    def _get_password_query_string(self) -> str:
        if self.password:
            return f'?password={self.password}'
        return ''

    def preview_uri(self) -> str:
        return reverse('home:url-route', kwargs={'filename': self.file.name}) + self._get_password_query_string()

    def get_size(self) -> str:
        num = self.size
        return self.get_size_of(num)

    @staticmethod
    def get_size_of(num: int) -> str:
        for unit in ["", "K", "M", "G", "T", "P", "E", "Z"]:
            if abs(num) < 1000.0:
                return f"{num:3.1f} {unit}B"
            num /= 1000.0
        return f"{num:.1f} YB"

    @property
    def raw_path(self) -> str:
        return '/raw/' + self.name

    @property
    def thumb_path(self) -> str:
        return '/raw/' + self.name + '?thumb=true'


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
