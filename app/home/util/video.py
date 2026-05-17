import datetime
import logging
import os
import re
import tempfile
from io import BytesIO

import av
from django.core.files import File
from home.models import Files
from home.util.geolocation import city_state_from_exif

log = logging.getLogger("app")

# Matches decimal-degree ISO 6709 strings written by iOS, Android, and GoPro:
# e.g. "+37.3323-122.0312+010.000/" or "+48.8566+002.3522/"
_ISO6709_RE = re.compile(r"^([+-]\d{1,3}(?:\.\d+)?)([+-]\d{1,3}(?:\.\d+)?)([+-]\d+(?:\.\d+)?)?/?$")


def _parse_iso6709(location: str):
    """Return (lat, lon, alt) from an ISO 6709 string, or None. alt may be None."""
    m = _ISO6709_RE.match(location.strip())
    if not m:
        return None
    lat, lon = float(m.group(1)), float(m.group(2))
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    alt = float(m.group(3)) if m.group(3) else None
    return lat, lon, alt


def _decimal_to_dms_ifd(lat: float, lon: float, alt: float = None) -> dict:
    """
    Convert decimal-degree coordinates to a GPSInfo IFD dict with the same
    integer-key / DMS-tuple structure that PIL produces for JPEG EXIF.

    Keys: 1=LatRef  2=Lat(D,M,S)  3=LonRef  4=Lon(D,M,S)
          5=AltitudeRef (0=above, 1=below)  6=Altitude (metres, optional)
    """

    def _split(deg):
        deg = abs(deg)
        d = int(deg)
        m = int((deg - d) * 60)
        s = round((deg - d - m / 60) * 3600, 4)
        return (d, m, s)

    ifd = {
        1: "N" if lat >= 0 else "S",
        2: _split(lat),
        3: "E" if lon >= 0 else "W",
        4: _split(lon),
    }
    if alt is not None:
        ifd[5] = 0 if alt >= 0 else 1
        ifd[6] = abs(alt)
    return ifd


def _normalize_dt(value: str) -> str:
    """
    Normalise a datetime string to the EXIF format "YYYY:MM:DD HH:MM:SS" that
    the convert_str_date template filter expects.

    Handles two common sources:
      • Apple QuickTime / EXIF already-formatted: "2025:11:02 12:23:58"  (returned as-is)
      • Android / GoPro / ffmpeg ISO 8601:        "2025-11-02T20:24:04.000000Z"
    """
    value = value.strip()
    # Already in EXIF format
    if len(value) >= 19 and value[4] == ":" and value[7] == ":":
        return value
    # Try ISO 8601 (with or without fractional seconds and Z/offset)
    for fmt in (
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
    ):
        try:
            return datetime.datetime.strptime(value, fmt).strftime("%Y:%m:%d %H:%M:%S")
        except ValueError:
            continue
    return value


def _extract_container_info(cm: dict, exif: dict) -> None:
    """Populate exif with device/camera fields from container metadata."""

    def _pick(*keys):
        return next((cm[k].strip() for k in keys if cm.get(k, "").strip()), "")

    if make := _pick("com.apple.quicktime.make"):
        exif["Make"] = make
    if model := _pick("com.apple.quicktime.model"):
        exif["Model"] = model
    if software := _pick("com.apple.quicktime.software", "com.android.version", "firmware", "encoder", "software"):
        exif["Software"] = software
    if dt := _pick("com.apple.quicktime.creationdate", "creation_time"):
        exif["DateTimeOriginal"] = _normalize_dt(dt)
        exif["DateTime"] = exif["DateTimeOriginal"]


def _extract_fps(vs, cm: dict):
    """Return frame-rate as a rounded float, or None if unavailable."""
    # Prefer declared capture FPS from container metadata (Android embeds this as
    # com.android.capture.fps; stream average_rate can drift due to VFR encoding).
    if raw_fps := cm.get("com.android.capture.fps", "").strip():
        try:
            return round(float(raw_fps), 3)
        except ValueError:
            pass
    if avg_rate := vs.average_rate:
        try:
            return round(float(avg_rate), 3)
        except (ValueError, ZeroDivisionError):
            pass
    return None


def _extract_stream_meta(container, cm: dict, meta: dict) -> None:
    """Populate meta with stream-level fields (dimensions, codec, FPS, duration)."""
    video_streams = container.streams.video
    if video_streams:
        vs = video_streams[0]
        w = getattr(vs.codec_context, "width", None)
        h = getattr(vs.codec_context, "height", None)
        if w and h:
            meta["PILImageWidth"] = w
            meta["PILImageHeight"] = h
        if codec_name := getattr(vs.codec_context, "name", None):
            meta["VideoCodec"] = codec_name
        if fps := _extract_fps(vs, cm):
            meta["FrameRate"] = fps
    if container.duration and container.duration > 0:
        meta["Duration"] = round(container.duration / 1_000_000, 3)


def _extract_gps_meta(cm: dict, exif: dict, meta: dict, local_path: str) -> None:
    """Populate exif/meta with GPS fields parsed from container location tags."""
    raw_location = next(
        filter(
            None,
            [
                cm.get("com.apple.quicktime.location.ISO6709"),  # iPhone/iPad MOV
                cm.get("location"),  # Android MP4, GoPro
                cm.get("location-eng"),  # some ffmpeg-muxed files
            ],
        ),
        "",
    )
    if not raw_location:
        log.debug("video_metadata_processor: no location tag found in %s", local_path)
        return
    coords = _parse_iso6709(raw_location)
    if not coords:
        log.debug("video_metadata_processor: unparseable location tag %r in %s", raw_location, local_path)
        return
    lat, lon, alt = coords
    exif["GPSInfo"] = _decimal_to_dms_ifd(lat, lon, alt)
    if area := city_state_from_exif(exif["GPSInfo"]):
        meta["GPSArea"] = area
    log.info("video_metadata_processor: GPS %.6f, %.6f alt=%s from %s", lat, lon, alt, local_path)


def video_metadata_processor(local_path: str, strip_gps: bool = False) -> tuple:
    """
    Extract metadata from a video file using PyAV and return (exif_dict, meta_dict)
    using the same field keys as ImageProcessor so the existing sidebar template
    and OpenGraph tags render without any changes.

    Container metadata (device/camera info) — best-effort across formats:
      exif["Make"]             iPhone: com.apple.quicktime.make
      exif["Model"]            iPhone: com.apple.quicktime.model
      exif["Software"]         iPhone: com.apple.quicktime.software
                               GoPro: firmware  |  edited: encoder / software
      exif["DateTimeOriginal"] iPhone: com.apple.quicktime.creationdate
                               Android/GoPro/other: creation_time
      exif["DateTime"]         same source — template checks this key to decide
                               whether to show the "Captured On" row

    Stream metadata (available for every container format):
      meta["PILImageWidth"]    video width  — renders in sidebar header
      meta["PILImageHeight"]   video height — renders in sidebar header
      meta["Duration"]         duration in seconds (float)
      meta["VideoCodec"]       codec short name, e.g. "h264", "hevc"

    GPS (skipped when strip_gps=True):
      exif["GPSInfo"]          DMS dict compatible with gpsToDecimal() / extract_gps_decimal()
      meta["GPSArea"]          reverse-geocoded "City, State, Country" string
    """
    exif: dict = {}
    meta: dict = {}
    try:
        with av.open(local_path) as container:
            cm = dict(container.metadata)
            log.debug("video_metadata_processor: container metadata for %s: %s", local_path, list(cm))
            _extract_container_info(cm, exif)
            _extract_stream_meta(container, cm, meta)
            if not strip_gps:
                _extract_gps_meta(cm, exif, meta, local_path)
    except Exception:
        log.debug("video_metadata_processor: failed for %s", local_path, exc_info=True)
    return exif, meta


def _seek_container(container) -> None:
    """Seek to 1 s; fall back to 0 for videos shorter than 1 s."""
    try:
        container.seek(1_000_000)
    except av.AVError:
        try:
            container.seek(0)
        except av.AVError:
            pass


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
            _seek_container(container)

            image = None
            rotation = 0
            for frame in container.decode(stream):
                rotation = frame.rotation or 0
                image = frame.to_image()
                break  # one frame is all we need

        # container is now closed; image is an independent Pillow object.
        if image is None:
            log.warning("video_thumbnail_processor: no frame decoded for %s", file.name)
            return False

        # frame.rotation is the display matrix rotation PyAV reads from the container.
        # Applying it directly (same direction, expand=True) corrects the orientation
        # so portrait videos stored as landscape frames get the right aspect ratio.
        if rotation:
            image = image.rotate(rotation, expand=True)

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
