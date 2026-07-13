import logging
import os
from typing import Optional

log = logging.getLogger("app")

# Must match nginx/record.conf's record_path — the shared media_dir volume
# mounted at /data/media in the nginx, app, and worker containers.
RECORD_DIR = "/data/media/record"


def validate_recording_path(path: str) -> Optional[str]:
    """Resolve `path` and confirm it is confined to RECORD_DIR before it's opened
    or deleted. `path` originates from nginx's on_record_done HTTP callback."""
    if not path:
        return None
    resolved = os.path.realpath(path)
    record_dir = os.path.realpath(RECORD_DIR) + os.sep
    if not resolved.startswith(record_dir):
        log.warning("validate_recording_path: rejected path outside RECORD_DIR: %s", path)
        return None
    return resolved


def delete_recording_file(path: str) -> None:
    resolved = validate_recording_path(path)
    if resolved and os.path.exists(resolved):
        try:
            os.remove(resolved)
        except OSError:
            log.exception("delete_recording_file: failed to remove %s", resolved)
