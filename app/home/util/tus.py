import logging
import os
import shutil
import time
from typing import Optional

from django.conf import settings

log = logging.getLogger("app")


def tus_dir() -> str:
    # settings.TUS_UPLOAD_DIR — the tusd sidecar's -upload-dir on the shared
    # media volume mounted in the tusd, app, and worker containers.
    return settings.TUS_UPLOAD_DIR


def has_disk_space(declared_size: int) -> bool:
    """
    True if the media volume has enough free space for a declared upload
    size plus TUS_DISK_HEADROOM_MB of margin. Checked in the pre-create hook
    so one user's declared size can't run the shared volume to empty before
    quota/max-size even come into play — SQLite, thumbnails, and every other
    user's uploads live on that same volume.

    Best-effort, not exact: concurrent in-flight uploads aren't accounted
    for (tusd doesn't expose that), so this catches the common case (volume
    already low, or one clearly-oversized request) rather than perfectly
    reserving space under heavy concurrency.
    """
    try:
        free = shutil.disk_usage(tus_dir()).free
    except OSError:
        log.exception("has_disk_space: could not stat %s", tus_dir())
        return True  # fail open — a stat failure shouldn't block all uploads
    headroom = settings.TUS_DISK_HEADROOM_MB * 1024 * 1024
    return declared_size + headroom <= free


def validate_tus_path(path: str) -> Optional[str]:
    """Resolve `path` and confirm it is confined to the tus upload dir before
    it's opened or deleted. `path` originates from tusd's post-finish hook."""
    if not path:
        return None
    resolved = os.path.realpath(path)
    upload_dir = os.path.realpath(tus_dir()) + os.sep
    if not resolved.startswith(upload_dir):
        log.warning("validate_tus_path: rejected path outside TUS_UPLOAD_DIR: %s", path)
        return None
    return resolved


def delete_tus_files(path: str) -> None:
    """Remove a tus upload's data file and its .info sidecar."""
    resolved = validate_tus_path(path)
    if not resolved:
        return
    for target in (resolved, resolved + ".info"):
        if os.path.exists(target):
            try:
                os.remove(target)
            except OSError:
                log.exception("delete_tus_files: failed to remove %s", target)


def sweep_expired_tus_files(max_age_seconds: int) -> int:
    """
    Delete tus upload files whose mtime is older than max_age_seconds.
    tusd updates the data file's mtime on every PATCH, so active-but-slow
    uploads stay fresh; only abandoned transfers go stale. Returns the
    number of files removed.
    """
    upload_dir = tus_dir()
    if not os.path.isdir(upload_dir):
        return 0
    cutoff = time.time() - max_age_seconds
    removed = 0
    for entry in os.scandir(upload_dir):
        if not entry.is_file(follow_symlinks=False):
            continue
        try:
            if entry.stat(follow_symlinks=False).st_mtime < cutoff:
                os.remove(entry.path)
                removed += 1
                log.info("sweep_expired_tus_files: removed stale %s", entry.path)
        except OSError:
            log.exception("sweep_expired_tus_files: failed on %s", entry.path)
    return removed
