import logging

log = logging.getLogger("app")


def extract_xmp_tags(exif: dict) -> list:
    """Walk the nested XMP structure and return a flat list of tag strings."""
    if not isinstance(exif, dict):
        return []
    ptr = exif
    try:
        for key in ["xmpmeta", "RDF", "Description", "subject", "Bag", "li"]:
            if isinstance(ptr, dict):
                ptr = ptr[key]
            elif isinstance(ptr, list):
                ptr = {k: v for d in ptr for k, v in d.items()}[key]
    except KeyError, IndexError, TypeError:
        return []
    if isinstance(ptr, list):
        return [t for t in ptr if isinstance(t, str) and t.strip()]
    return []


def sync_file_tags(file) -> None:
    """Sync FileTag rows for *file* to match the XMP tags in file.exif."""
    from home.models import FileTag

    try:
        tags = extract_xmp_tags(file.exif)
        existing = set(FileTag.objects.filter(file=file).values_list("tag", flat=True))
        new_tags = set(tags) - existing
        removed = existing - set(tags)
        if removed:
            FileTag.objects.filter(file=file, tag__in=removed).delete()
        if new_tags:
            FileTag.objects.bulk_create(
                [FileTag(file=file, tag=t) for t in new_tags],
                ignore_conflicts=True,
            )
        log.debug("sync_file_tags: file=%s added=%d removed=%d", file.pk, len(new_tags), len(removed))
    except Exception:
        log.exception("sync_file_tags: failed for file=%s", file.pk)
