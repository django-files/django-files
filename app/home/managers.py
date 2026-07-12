from django.db import IntegrityError, models, transaction


class TagManager(models.Manager):
    def get_or_create_tag(self, name: str):
        """Return the canonical Tag for *name*, creating it if needed.

        Matching is case-insensitive so "Vacation" and "vacation" resolve to
        one Tag; the first writer's casing is kept for display. The unique
        constraint on name backstops exact-duplicate races.
        """
        name = name.strip()
        if tag := self.filter(name__iexact=name).first():
            return tag
        try:
            with transaction.atomic():
                return self.create(name=name)
        except IntegrityError:
            return self.get(name=name)

    def prune_orphans(self, pks) -> None:
        """Delete Tags in *pks* that no longer tag any file or album."""
        self.filter(pk__in=pks, file_tags__isnull=True, album_tags__isnull=True).delete()


class FilesManager(models.Manager):
    def get_request(self, request, **kwargs):
        return self.filter(user=request.user, avatar=False, **kwargs)

    def get_all_request(self, **kwargs):
        return self.all(avatar=False, **kwargs)

    def filtered_request(self, request, **kwargs):
        return self.filter(avatar=False, **kwargs)


class ShortURLsManager(models.Manager):
    def get_request(self, request, **kwargs):
        return self.filter(user=request.user, **kwargs)


class AlbumsManager(models.Manager):
    def get_request(self, request, **kwargs):
        return self.filter(user=request.user, **kwargs)

    def get_all_request(self, **kwargs):
        return self.all(**kwargs)

    def filtered_request(self, request, **kwargs):
        return self.filter(**kwargs)
