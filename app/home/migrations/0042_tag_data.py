from django.db import migrations

BATCH = 500


def forwards(apps, schema_editor):
    """Build the canonical Tag vocabulary from existing FileTag strings.

    Names are deduplicated case-insensitively (first occurrence's casing wins,
    matching TagManager.get_or_create_tag). If a file carried two case-variants
    of one tag, the extra rows are dropped so the (file, tag) unique constraint
    added in 0043 holds.
    """
    FileTag = apps.get_model("home", "FileTag")
    Tag = apps.get_model("home", "Tag")
    tag_pks = {}
    rows = list(FileTag.objects.order_by("pk").only("pk", "tag", "file_id"))
    for row in rows:
        key = row.tag.strip().lower()
        if key not in tag_pks:
            tag_pks[key] = Tag.objects.create(name=row.tag.strip()).pk
    seen, keep, drop = set(), [], []
    for row in rows:
        pair = (row.file_id, tag_pks[row.tag.strip().lower()])
        if pair in seen:
            drop.append(row.pk)
            continue
        seen.add(pair)
        row.tag_ref_id = pair[1]
        keep.append(row)
    if drop:
        FileTag.objects.filter(pk__in=drop).delete()
    FileTag.objects.bulk_update(keep, ["tag_ref"], batch_size=BATCH)


class Migration(migrations.Migration):

    dependencies = [
        ("home", "0041_tag_model"),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
