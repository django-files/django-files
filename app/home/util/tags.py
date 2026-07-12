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
    """Sync FileTag rows for *file* to match the XMP tags in file.exif.

    Only removes rows that were previously XMP-synced (xmp=True) and are no
    longer present in the image metadata. User-added tags (xmp=False) are
    never touched by this function.
    """
    from home.models import FileTag, Tag

    try:
        tags = extract_xmp_tags(file.exif)
        xmp_existing = set(FileTag.objects.filter(file=file, xmp=True).values_list("tag__name", flat=True))
        new_tags = set(tags) - xmp_existing
        removed = xmp_existing - set(tags)
        if removed:
            removed_qs = FileTag.objects.filter(file=file, tag__name__in=removed, xmp=True)
            removed_pks = list(removed_qs.values_list("tag_id", flat=True))
            removed_qs.delete()
            Tag.objects.prune_orphans(removed_pks)
        for name in new_tags:
            FileTag.objects.get_or_create(file=file, tag=Tag.objects.get_or_create_tag(name), defaults={"xmp": True})
        log.debug("sync_file_tags: file=%s added=%d removed=%d", file.pk, len(new_tags), len(removed))
    except Exception:
        log.exception("sync_file_tags: failed for file=%s", file.pk)
