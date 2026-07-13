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


def clean_tag_names(value) -> list:
    """Normalize a tags payload (list or comma-separated string) to stripped names."""
    if isinstance(value, str):
        value = value.split(",")
    if not isinstance(value, list):
        return []
    names = [str(name).strip() for name in value]
    return [name for name in names if name and len(name) <= 255]


def tag_names(entity) -> list:
    """Tag names for a Files/Albums/Stream row.

    Reads the prefetch cache when the queryset used prefetch_related("tags__tag")
    (zero queries in list endpoints); otherwise issues a single values_list query
    instead of one query per tag row.
    """
    if "tags" in getattr(entity, "_prefetched_objects_cache", {}):
        return [link.tag.name for link in entity.tags.all()]
    return list(entity.tags.values_list("tag__name", flat=True))


def add_entity_tag(entity, name: str, **defaults) -> tuple:
    """Link canonical Tag *name* to entity.tags. Returns (canonical_name, created)."""
    from home.models import Tag

    tag = Tag.objects.get_or_create_tag(name)
    _, created = entity.tags.get_or_create(tag=tag, defaults=defaults)
    return tag.name, created


def remove_entity_tag(entity, name: str, **filters) -> bool:
    """Unlink tag *name* from entity.tags, pruning the vocabulary if orphaned."""
    from home.models import Tag

    removed_qs = entity.tags.filter(tag__name=name, **filters)
    removed_pks = list(removed_qs.values_list("tag_id", flat=True))
    deleted, _ = removed_qs.delete()
    if not deleted:
        return False
    Tag.objects.prune_orphans(removed_pks)
    return True


def attach_file_tags(file, tags) -> None:
    """Attach user tags (xmp=False) to *file* from a list or comma-separated string."""
    for name in clean_tag_names(tags):
        add_entity_tag(file, name, xmp=False)


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
            add_entity_tag(file, name, xmp=True)
        log.debug("sync_file_tags: file=%s added=%d removed=%d", file.pk, len(new_tags), len(removed))
    except Exception:
        log.exception("sync_file_tags: failed for file=%s", file.pk)
