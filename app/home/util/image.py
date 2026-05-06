import logging
import os
import tempfile
from io import BytesIO

import av
from django.core.files import File
from home.models import Files
from home.util.geolocation import city_state_from_exif
from PIL import ExifTags, Image, ImageOps, TiffImagePlugin

log = logging.getLogger("app")


class ImageProcessor(object):
    def __init__(
        self, local_path: str, default_remove_exif: bool, default_exif_geo: bool, ctx, detected_extension: str = None
    ):
        self.local_path = local_path
        if ctx.get("strip_exif") is not None:
            self.remove_exif = ctx.get("strip_exif")
        else:
            self.remove_exif = default_remove_exif
        if ctx.get("strip_gps") is not None:
            self.remove_exif_geo = ctx.get("strip_gps")
        else:
            self.remove_exif_geo = default_exif_geo
        self.exif = {}
        self.meta = {}
        self.tmp_thumb = os.path.splitext(self.local_path)[0] + "_thumb" + os.path.splitext(self.local_path)[1]
        self.detected_extension = detected_extension

    def process_file(self) -> None:
        # TODO: Concatenate Logic to This Function
        # processes image files, collects or strips exif, sets metadata
        with Image.open(self.local_path) as image:
            self.meta["PILImageWidth"], self.meta["PILImageHeight"] = image.size
            if self.remove_exif:
                return self.strip_exif(image, self.local_path)
            log.info("Parsing and storing EXIF: %s", self.local_path)
            image, exif_clean, exif = self._handle_exif(image)
            # write exif in case exif modified
            image_kwargs = {"format": self.detected_extension, "exif": exif}
            if image.format == "JPEG":
                image_kwargs["quality"] = "keep"
            image.save(self.local_path, **image_kwargs)
            # determine photo area from gps and store in metadata
            if area := city_state_from_exif(exif_clean.get("GPSInfo")):
                self.meta["GPSArea"] = area
            self.exif = self.cast(exif_clean)

    def _handle_exif(self, image: Image) -> tuple:
        # TODO: Remove Basic Logic from here and put it all in one function
        # takes an image, returns image, dictionary of exif data, and modified exif data
        # does not collect gps data if strip_gps true
        exif_clean = {}
        exif = image.getexif()
        if self.remove_exif_geo:
            image, exif = self.strip_gps_raw_exif(image, exif)
        try:
            # get_exif tends to not have all data we need, so we call _get_exif, if that fails
            # we fail back to get_exif for all exif attrs
            _getexif = image._getexif() if hasattr(image, "_getexif") else {}
            exif_data = {ExifTags.TAGS[k]: v for k, v in _getexif.items() if k in ExifTags.TAGS}
            for k, v in exif_data.items():
                exif_clean[k] = v.decode() if isinstance(v, bytes) else str(v)
        except Exception as error:
            log.info("Error processing exif, using fallback: %s", error)
            for tag, value in exif.items():
                exif_clean[ExifTags.TAGS.get(tag, tag)] = value
        exif_clean["GPSInfo"] = exif.get_ifd(ExifTags.IFD.GPSInfo)
        try:
            exif_clean["xmpmeta"] = image.getxmp()["xmpmeta"]
        except Exception as error:
            log.debug(f"Failed to read xmp metadata: {error}")
        return image, exif_clean, exif

    @classmethod
    def cast(cls, v):
        # casts exif nested json into nested dictionary
        if isinstance(v, TiffImagePlugin.IFDRational):
            try:
                return float(v)
            except ZeroDivisionError as error:
                log.debug("error: %s", error)
                return 0
        elif isinstance(v, tuple):
            return tuple(cls.cast(t) for t in v)
        elif isinstance(v, bytes):
            return v.decode(errors="replace").replace("\u0000", "")
        elif isinstance(v, dict):
            for kk, vv in v.items():
                v[kk] = cls.cast(vv)
            return v
        elif isinstance(v, str):
            # this is needed because with postgres the null unicode characters are not filtered when writing the object
            return v.replace("\u0000", "")
        else:
            return v

    @staticmethod
    def strip_gps_raw_exif(image: Image, exif: dict) -> tuple:
        # accepts raw exif object from PIL, returns object with no GPS data
        log.info("Stripping EXIF GPS")
        if 0x8825 in exif:
            del exif[0x8825]
        return image, exif

    @staticmethod
    def strip_exif(image: Image, local_path: str) -> None:
        # accepts image and file, rewrites image file without exif
        log.info("Stripping EXIF: %s", local_path)
        with Image.new(image.mode, image.size) as new:
            new.putdata(image.getdata())
            if "P" in image.mode:
                new.putpalette(image.getpalette())
            new.save(local_path)


def thumbnail_processor(file: Files, file_bytes: bytes = None, extension: str = None):
    # generate thumbnail via bytes object or file object
    # prefer bytes object if file is still local to avoid wasteful redownload of file
    tmp_file = f"/tmp/thumb_{file.name}"  # nosec
    file_bytes = BytesIO(file_bytes) if file_bytes else BytesIO(file.file.read())
    with Image.open(file_bytes) as image:
        image = ImageOps.exif_transpose(image)
        # TODO: check resolution is not already small, if it is don't bother generating a thumbnail
        image.thumbnail((512, 512))
        image.save(tmp_file, format=extension)
    with open(tmp_file, "rb") as thumb:
        # we cannot call update, we must explicitly save, here since the hooks that upload the file will not happen
        file.thumb = File(thumb, name=file.name)
        file.save()
    os.remove(tmp_file)


def video_thumbnail_processor(file: Files, max_bytes: int) -> bool:
    """
    Extract a single keyframe at ~1 s from a video and save it as a thumbnail.

    Uses PyAV. The video is first written to a local NamedTemporaryFile so PyAV
    always gets a fully seekable path on disk.
    This is required for two reasons:
      1. Non-faststart MP4s have the moov atom at the end; PyAV must seek backward
         after reading the header, which is impossible on a forward-only S3 stream.
      2. S3-backed FieldFile objects do not support arbitrary backward seeks.

    max_bytes: Hard cap on how many bytes are written to the local temp file.
      Streaming is done via file.file.chunks() so memory usage stays low; if the
      running total exceeds the cap a ValueError is raised and the temp file is
      cleaned up in the finally block. This is a second layer of defence — the
      primary check happens in generate_video_thumb before this function is called.
      Default matches the VIDEO_THUMB_MAX_BYTES default of 2 GB.

    Returns True on success, False if the video cannot be processed.
    """
    # Normalise both Unix and Windows path separators before extracting the
    # basename so that a name like "../../etc/shadow.mp4" cannot escape the
    # thumbs directory when the resulting File is saved by the storage backend.
    basename = os.path.basename(file.name.replace("\\", "/"))
    stem = os.path.splitext(basename)[0]
    suffix = os.path.splitext(basename)[1] or ".mp4"

    # Reject frames whose decoded area exceeds 4 K (≈ 8 MP). This check runs
    # against codec-context metadata before any pixel data is decompressed,
    # preventing codec-bomb and Pillow decompression-bomb attacks.
    MAX_VIDEO_PIXELS = 3840 * 2160

    tmp_video = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as vf:
            # Stream chunks rather than loading the whole file into memory at
            # once. The running total is checked against max_bytes so an
            # unexpectedly large file (e.g. the size field is stale or missing)
            # cannot exhaust /tmp on the worker.
            written = 0
            for chunk in file.file.chunks():
                written += len(chunk)
                if written > max_bytes:
                    raise ValueError(f"Video exceeds {max_bytes // (1024 * 1024)} MB size limit during download")
                vf.write(chunk)
            tmp_video = vf.name

        with av.open(tmp_video) as container:
            if not container.streams.video:
                log.warning("video_thumbnail_processor: no video stream in %s", file.name)
                return False

            stream = container.streams.video[0]

            # Guard against oversized frames before touching the decoder.
            w = stream.codec_context.width or 0
            h = stream.codec_context.height or 0
            if w * h > MAX_VIDEO_PIXELS:
                log.warning(
                    "video_thumbnail_processor: %s frame %dx%d exceeds 4K pixel limit",
                    file.name,
                    w,
                    h,
                )
                return False

            # Seek to 1 s (AV_TIME_BASE units = µs). For videos shorter than
            # 1 s the seek raises AVError; fall back to an explicit seek to 0
            # so the decode position is always well-defined.
            # skip_frame is intentionally left at DEFAULT: after a backward
            # seek (which lands on the nearest preceding keyframe), the decoder
            # returns that keyframe immediately rather than skipping forward to
            # the next one, which risks overshooting end-of-stream on large-GOP
            # or very short files.
            try:
                container.seek(1_000_000)
            except av.AVError:
                try:
                    container.seek(0)
                except av.AVError:
                    pass

            image = None
            for frame in container.decode(stream):
                image = frame.to_image()
                break  # one frame is all we need

        # container is now closed; image is an independent Pillow object.
        if image is None:
            log.warning("video_thumbnail_processor: no frame decoded for %s", file.name)
            return False

        # Resize to fit within 512×512 while preserving aspect ratio.
        # A 1920×1080 frame becomes 512×288; a 1080×1920 becomes 288×512.
        image.thumbnail((512, 512))

        # Write to BytesIO — avoids a second on-disk temp file and eliminates
        # the TOCTOU window that a NamedTemporaryFile open→close→reopen creates.
        buf = BytesIO()
        image.save(buf, format="JPEG")
        buf.seek(0)

        file.thumb = File(buf, name=f"{stem}.jpg")
        # update_fields prevents the post_save signal handler from receiving
        # update_fields=None, which triggers TypeError: 'NoneType' is not iterable.
        file.save(update_fields=["thumb"])

        log.info("video_thumbnail_processor: saved thumbnail for %s", file.name)
        return True

    except Exception:
        log.exception("video_thumbnail_processor: failed for %s", file.name)
        return False
    finally:
        if tmp_video:
            try:
                os.remove(tmp_video)
            except OSError:
                pass
