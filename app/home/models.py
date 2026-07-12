from django.conf import settings
from django.core.cache import cache
from django.db import models
from django.db.models import F
from django.shortcuts import reverse
from home.managers import (
    AlbumsManager,
    FilesManager,
    ShortURLsManager,
    TagManager,
)
from home.util.nginx import sign_nginx_urls
from home.util.rand import rand_string
from home.util.storage import StoragesRouterFileField, use_s3
from home.util.webhooks import WEBHOOK_SCOPE_SITE as HOOK_SCOPE_SITE
from home.util.webhooks import WEBHOOK_SCOPE_USER as HOOK_SCOPE_USER
from home.util.webhooks import WEBHOOK_TYPE_CUSTOM as HOOK_TYPE_CUSTOM
from home.util.webhooks import WEBHOOK_TYPE_DISCORD as HOOK_TYPE_DISCORD
from oauth.managers import DiscordWebhooksManager
from oauth.models import CustomUser


class Albums(models.Model):
    class Meta:
        ordering = ["-date"]
        verbose_name = "Album"
        verbose_name_plural = "Albums"
        unique_together = ["user", "name"]

    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    name = models.CharField(max_length=255, blank=False, verbose_name="Name", help_text="Album Name.")
    password = models.CharField(default="", max_length=255, blank=True, verbose_name="Album Password")
    private = models.BooleanField(default=False, verbose_name="Private Album")
    info = models.CharField(
        default="", max_length=255, blank=True, verbose_name="Info", help_text="Album Information."
    )
    view = models.IntegerField(default=0, verbose_name="Views", help_text="Album Views.")
    maxv = models.IntegerField(default=0, verbose_name="Max", help_text="Max Views.")
    expr = models.CharField(
        default="", max_length=32, blank=True, verbose_name="Expiration", help_text="Album Expire."
    )
    date = models.DateTimeField(auto_now_add=True, verbose_name="Created", help_text="Album Created Date.")

    objects = AlbumsManager()


class Files(models.Model):
    upload_to = "."
    id = models.AutoField(primary_key=True)
    albums = models.ManyToManyField(Albums, blank=True)
    file = StoragesRouterFileField(upload_to=upload_to)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    size = models.IntegerField(default=0, verbose_name="Size", help_text="File Size in Bytes.")
    mime = models.CharField(default="", max_length=255, blank=True, verbose_name="MIME", help_text="File MIME Type.")
    name = models.CharField(default="", max_length=255, blank=True, verbose_name="Name", help_text="File Name.")
    info = models.CharField(default="", max_length=255, blank=True, verbose_name="Info", help_text="File Information.")
    expr = models.CharField(default="", max_length=32, blank=True, verbose_name="Expiration", help_text="File Expire.")
    view = models.IntegerField(default=0, verbose_name="Views", help_text="File Views.")
    maxv = models.IntegerField(default=0, verbose_name="Max", help_text="Max Views.")
    exif = models.JSONField(
        default=dict, blank=True, verbose_name="EXIF Metadata", help_text="JSON formatted exif metadata."
    )
    date = models.DateTimeField(auto_now_add=True, verbose_name="Created", help_text="File Created Date.")
    edit = models.DateTimeField(auto_now=True, verbose_name="Edited", help_text="File Edited Date.")
    meta = models.JSONField(default=dict, blank=True, verbose_name="Metadata", help_text="JSON formatted metadata.")
    meta_preview = models.BooleanField(default=True, help_text="Show metadata on previews.")
    password = models.CharField(default="", max_length=255, blank=True, verbose_name="File Password")
    private = models.BooleanField(default=False, verbose_name="Private File")
    objects = FilesManager()
    avatar = models.BooleanField(default=False, help_text="Determines file is a user avatar.")
    thumb = StoragesRouterFileField(upload_to=f"{upload_to}/thumbs/", null=True, blank=True)

    # def save(self, *args, **kwargs):
    #     return super(Files, self).save(*args, **kwargs)

    def __str__(self):
        return f"<File(id={self.id} size={self.size} name={self.name})>"

    class Meta:
        ordering = ["-date"]
        verbose_name = "File"
        verbose_name_plural = "Files"

    def get_url(self, view: bool = False, download: bool = False, abs_url: str = "") -> str:
        """Gets a static url to a file object.
        view counts url retrieval as a view
        download makes the static url force download
        """
        if view:
            Files.objects.filter(pk=self.pk).update(view=F("view") + 1)
        # ######## Download Static URL ########
        if download:
            # check if download url cached, if not serve new one
            if use_s3():
                if (download_url := cache.get(f"file.urlcache.download.{self.pk}")) is None:
                    # TODO: access protected member, look into how to better handle this
                    download_url = self.file.file._storage.url(
                        self.file.file.name,
                        parameters={"ResponseContentDisposition": f"attachment; filename={self.file.file.name}"},
                        expire=settings.SIGNED_DOWNLOAD_URL_TTL_SECONDS,
                    )
                    cache.set(
                        f"file.urlcache.download.{self.pk}",
                        download_url,
                        settings.SIGNED_DOWNLOAD_URL_TTL_SECONDS - 60,
                    )
                return download_url
            url = self.file.url + "?download=true"
            return abs_url + url + self._sign_nginx_url(self.file.url).replace("?", "&")
        # ######## Generic Static URL ########
        if use_s3():
            if (url := cache.get(f"file.urlcache.raw.{self.pk}")) is None:
                # TODO: access protected member, look into how to better handle this
                url = self.file.file._storage.url(self.file.file.name, expire=settings.SIGNED_URL_TTL_SECONDS)
                cache.set(
                    f"file.urlcache.raw.{self.pk}",
                    url,
                    int(settings.SIGNED_URL_TTL_SECONDS * settings.SIGNED_URL_REFRESH_RATIO),
                )
            return url
        # Cache the nginx-signed URL so repeated renders (e.g. re-opening the
        # gallery panel) return the same URL string and the browser can cache
        # the image response instead of treating each signed URL as a new resource.
        if (signed := cache.get(f"file.urlcache.raw.{self.pk}")) is None:
            signed = self.file.url + self._sign_nginx_url(self.file.url)
            cache.set(
                f"file.urlcache.raw.{self.pk}",
                signed,
                int(settings.SIGNED_URL_TTL_SECONDS * settings.SIGNED_URL_REFRESH_RATIO),
            )
        return abs_url + signed

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
                        self.file.file.name, expire=settings.SIGNED_META_URL_TTL_SECONDS
                    )
                except FileNotFoundError:
                    return ""
                cache.set(
                    f"file.urlcache.meta_static.{self.pk}",
                    meta_static_url,
                    int(settings.SIGNED_META_URL_TTL_SECONDS * settings.SIGNED_URL_REFRESH_RATIO),
                )
            return meta_static_url
        return self.get_url(False)

    def get_gallery_url(self, abs_url: str = "") -> str:
        """Generates a static url for use on a gallery page."""
        use = self.thumb if self.thumb else self.file
        # cache the signed url so the browser cache key stays stable across renders;
        # intentionally expire before the signature does so urls don't 403 mid-page
        if (gallery_url := cache.get(f"file.urlcache.gallery.{self.pk}")) is None:
            try:
                if use_s3():
                    # TODO: access protected member, look into how to better handle this
                    gallery_url = self.file.file._storage.url(use.file.name, expire=settings.SIGNED_URL_TTL_SECONDS)
                else:
                    gallery_url = use.url + self._sign_nginx_url(use.url)
            except FileNotFoundError:
                return ""
            cache.set(
                f"file.urlcache.gallery.{self.pk}",
                gallery_url,
                int(settings.SIGNED_URL_TTL_SECONDS * settings.SIGNED_URL_REFRESH_RATIO),
            )
        return gallery_url if use_s3() else abs_url + gallery_url

    def _sign_nginx_url(self, uri: str) -> str:
        return sign_nginx_urls(uri)

    def _get_password_query_string(self) -> str:
        if self.password:
            return f"?password={self.password}"
        return ""

    def preview_uri(self) -> str:
        return reverse("home:url-route", kwargs={"filename": self.file.name}) + self._get_password_query_string()

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
        return "/raw/" + self.name

    @property
    def thumb_path(self) -> str:
        return "/raw/" + self.name + "?thumb=true"


class Tag(models.Model):
    """Canonical tag vocabulary shared by files and albums.

    Names are deduplicated case-insensitively in TagManager.get_or_create_tag;
    the DB unique constraint only guarantees exact uniqueness so it stays
    portable across sqlite/mysql/mariadb/postgres collations.
    """

    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255, unique=True, verbose_name="Name", help_text="Tag Name.")

    objects = TagManager()

    class Meta:
        ordering = ["name"]
        verbose_name = "Tag"
        verbose_name_plural = "Tags"

    def __str__(self):
        return self.name


class FileTag(models.Model):
    file = models.ForeignKey(Files, on_delete=models.CASCADE, related_name="tags")
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE, related_name="file_tags")
    xmp = models.BooleanField(default=False)

    class Meta:
        unique_together = ["file", "tag"]
        verbose_name = "File Tag"
        verbose_name_plural = "File Tags"

    def __str__(self):
        return f"<FileTag(file={self.file_id} tag={self.tag_id})>"


class AlbumTag(models.Model):
    album = models.ForeignKey(Albums, on_delete=models.CASCADE, related_name="tags")
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE, related_name="album_tags")

    class Meta:
        unique_together = ["album", "tag"]
        verbose_name = "Album Tag"
        verbose_name_plural = "Album Tags"

    def __str__(self):
        return f"<AlbumTag(album={self.album_id} tag={self.tag_id})>"


class FileStats(models.Model):
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(CustomUser, blank=True, null=True, on_delete=models.CASCADE)
    stats = models.JSONField(verbose_name="Stats JSON", help_text="Stats JSON Data.")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created", help_text="Stats Updated Date.")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Updated", help_text="Stats Updated Date.")

    def __str__(self):
        return f"<FileStat(id={self.id}, user_id={self.user_id})>"

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "FileStat"
        verbose_name_plural = "FileStats"
        indexes = [models.Index(fields=["user", "-created_at"], name="home_filest_user_id_75c054_idx")]


class ShortURLs(models.Model):
    id = models.AutoField(primary_key=True)
    short = models.CharField(max_length=255, unique=True, verbose_name="Short", help_text="Short Link ID.")
    url = models.URLField(verbose_name="Destination URL", help_text="Target URL for the ShortURL.")
    max = models.IntegerField(default=0, verbose_name="Max", help_text="Max ShortURL Views")
    views = models.IntegerField(default=0, verbose_name="Views", help_text="Total ShortURL Views")
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created", help_text="ShortURL Created Date.")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Updated", help_text="ShortURL Updated Date.")
    objects = ShortURLsManager()

    def __str__(self):
        return f"<ShortURL(id={self.id}, user_id={self.user_id})>"

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Short URL"
        verbose_name_plural = "Short URLs"


class Stream(models.Model):
    class Meta:
        ordering = ["-started_at"]
        verbose_name = "Stream"
        verbose_name_plural = "Streams"

    name = models.CharField(
        max_length=255, primary_key=True, unique=True, verbose_name="Name", help_text="Stream Name"
    )
    title = models.CharField(max_length=255, blank=False, verbose_name="Title", help_text="Stream Title")
    description = models.TextField(default="", blank=True, verbose_name="Description", help_text="Stream Description")
    is_live = models.BooleanField(default=False, verbose_name="Live Status", help_text="Stream Live Status")
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        verbose_name="User",
    )
    started_at = models.DateTimeField(
        auto_now_add=True, verbose_name="Started At", help_text="Stream Started DateTime"
    )
    ended_at = models.DateTimeField(null=True, blank=True, verbose_name="Ended At", help_text="Stream Ended DateTime")
    unique_views = models.IntegerField(default=0, verbose_name="Unique Views", help_text="Unique stream impressions")
    public = models.BooleanField(default=True, verbose_name="Public", help_text="Stream Public Boolean")
    password = models.CharField(
        default="", max_length=255, blank=True, verbose_name="Password", help_text="Stream Password"
    )
    viewer_limit = models.IntegerField(default=0, verbose_name="Viewer Limit", help_text="Max stream viewers")
    live_chat = models.BooleanField(default=False, verbose_name="Live Chat", help_text="Stream Live Chat Enabled")
    anonymous_chat = models.BooleanField(
        default=False, verbose_name="Anonymous Chat", help_text="Stream Anonymous Chat Enabled"
    )
    stream_token = models.CharField(
        default=rand_string,
        max_length=32,
        unique=True,
        verbose_name="Stream Token",
        help_text="Per-stream RTMP authentication token. Scoped only to this stream.",
    )
    playback_token = models.CharField(
        default="",
        blank=True,
        max_length=32,
        verbose_name="Playback Token",
        help_text="Per-stream raw-link token used by HLS players (VLC, ffmpeg, etc.) "
        "to fetch the stream via /hls/?token=. Empty = raw-link playback disabled. "
        "Independent of stream_token (RTMP ingest).",
    )

    def __str__(self):
        return f"<Stream(name={self.name}, title={self.title}, user_id={self.user_id})>"


class StreamHistory(models.Model):
    class Meta:
        ordering = ["-started_at"]
        verbose_name = "Stream History"
        verbose_name_plural = "Streams History"

    id = models.AutoField(primary_key=True)
    stream = models.ForeignKey(Stream, on_delete=models.CASCADE, verbose_name="Stream", help_text="Stream Object")
    started_at = models.DateTimeField(auto_now_add=True, verbose_name="Started At", help_text="Stream Start Datetime.")
    ended_at = models.DateTimeField(null=True, blank=True, verbose_name="Ended At", help_text="Stream End Datetime.")
    peak_viewers = models.IntegerField(default=0, verbose_name="Peak Viewers", help_text="Peak View Count")
    avg_viewers = models.IntegerField(default=0, verbose_name="Average Viewers", help_text="Average View Count")
    title = models.CharField(
        max_length=255, blank=True, verbose_name="Title", help_text="Stream title at time of recording."
    )
    description = models.TextField(
        default="", blank=True, verbose_name="Description", help_text="Stream description at time of recording."
    )
    recording = models.OneToOneField(
        Files,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Recording",
        help_text="Link to recording as a file object.",
    )

    def __str__(self):
        return (
            f"<StreamHistory(id={self.id}, stream={self.stream.name}, "
            f"started_at={self.started_at}, ended_at={self.ended_at})>"
        )


class Webhook(models.Model):
    WEBHOOK_TYPE_CUSTOM = HOOK_TYPE_CUSTOM
    WEBHOOK_TYPE_DISCORD = HOOK_TYPE_DISCORD
    TYPE_CHOICES = [
        (WEBHOOK_TYPE_CUSTOM, "Custom"),
        (WEBHOOK_TYPE_DISCORD, "Discord"),
    ]
    SCOPE_USER = HOOK_SCOPE_USER
    SCOPE_SITE = HOOK_SCOPE_SITE
    SCOPE_CHOICES = [
        (SCOPE_USER, "User"),
        (SCOPE_SITE, "Site"),
    ]

    id = models.AutoField(primary_key=True)
    owner = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="webhooks")
    name = models.CharField(max_length=128, verbose_name="Name", help_text="Webhook Name.")
    webhook_type = models.CharField(
        max_length=16, choices=TYPE_CHOICES, default=WEBHOOK_TYPE_CUSTOM, verbose_name="Type"
    )
    scope = models.CharField(
        max_length=16,
        choices=SCOPE_CHOICES,
        default=SCOPE_USER,
        verbose_name="Scope",
        help_text="Site-scoped hooks receive events for all users; superuser only.",
    )
    url = models.URLField(verbose_name="Webhook URL")
    secret = models.CharField(
        max_length=128, blank=True, verbose_name="Secret", help_text="HMAC-SHA256 signing secret for custom hooks."
    )
    active = models.BooleanField(default=True)
    events = models.JSONField(default=list, blank=True, verbose_name="Events", help_text="Subscribed event keys.")
    filters = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Filters",
        help_text="Event filters, e.g. {'tags': ['work', '!private']} to filter file events by tag.",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created", help_text="Hook Created Date.")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Updated", help_text="Hook Updated Date.")

    def __str__(self):
        return f"<Webhook(id={self.id} type={self.webhook_type} owner={self.owner_id})>"

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Webhook"
        verbose_name_plural = "Webhooks"


class StreamDiscordWebhooks(models.Model):
    id = models.AutoField(primary_key=True)
    url = models.URLField(unique=True, verbose_name="Webhook URL")
    hook_id = models.CharField(max_length=32, blank=True)
    guild_id = models.CharField(max_length=32, blank=True)
    channel_id = models.CharField(max_length=32, blank=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created", help_text="Hook Created Date.")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Updated", help_text="Hook Updated Date.")
    owner = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    stream = models.ForeignKey(Stream, on_delete=models.CASCADE, verbose_name="Stream", help_text="Stream Object")
    objects = DiscordWebhooksManager()

    def __str__(self):
        return f"<Webhook(id={self.id} hook_id={self.hook_id} owner={self.owner.id})>"

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Discord Webhooks for Streams"
        verbose_name_plural = "Discord Webhooks for Streams"
