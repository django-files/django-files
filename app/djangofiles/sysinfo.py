"""
Container/system introspection helpers used by settings.py at import time.
Must stay free of Django imports — settings are not configured yet.
"""

_CGROUP_V2_LIMIT = "/sys/fs/cgroup/memory.max"
_CGROUP_V1_LIMIT = "/sys/fs/cgroup/memory/memory.limit_in_bytes"
# cgroup v1 reports "no limit" as a page-rounded huge number instead of a
# sentinel string; anything at or above 1 PiB is treated as unlimited.
_UNLIMITED_BYTES = 1 << 50

_SIZE_UNITS = {"K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4}


def parse_size(value) -> int:
    """
    Parse a human size string ("5G", "512M", "1048576") into bytes.
    Accepts the same digits + single K/M/G/T suffix form that nginx's
    client_max_body_size does, so one env var can feed both.
    """
    text = str(value).strip().upper()
    if text and text[-1] in _SIZE_UNITS:
        return int(text[:-1]) * _SIZE_UNITS[text[-1]]
    return int(text)


def cgroup_memory_limit() -> int:
    """
    Return the container's memory limit in bytes, or 0 when the container is
    unlimited, the limit is unreadable, or we are not in a container.
    """
    for path in (_CGROUP_V2_LIMIT, _CGROUP_V1_LIMIT):
        try:
            with open(path) as f:
                raw = f.read().strip()
        except OSError, ValueError:
            continue
        if raw == "max":
            return 0
        try:
            limit = int(raw)
        except ValueError:
            continue
        return 0 if limit >= _UNLIMITED_BYTES else limit
    return 0
