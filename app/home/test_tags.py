import json
import logging
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from djangofiles.test_utils import TEST_PASSWORD
from home.consumers import HomeConsumer
from home.models import Albums, AlbumTag, Files, FileTag, Tag
from home.util.tags import sync_file_tags
from oauth.models import CustomUser

log = logging.getLogger("app")


def _xmp_exif(tags: list) -> dict:
    return {"xmpmeta": {"RDF": {"Description": {"subject": {"Bag": {"li": tags}}}}}}


class TagBaseTestCase(TestCase):
    def setUp(self):
        call_command("loaddata", "settings/fixtures/sitesettings.json", verbosity=0)
        self.user = CustomUser.objects.create_user(
            username="taguser",
            email="tag@test.com",
            password=TEST_PASSWORD,  # nosec  # NOSONAR
        )

    def create_file(self, name="tagged.txt"):
        return Files.objects.create(user=self.user, name=name, file=name, mime="text/plain")


class TagManagerTests(TagBaseTestCase):
    def test_get_or_create_tag_case_insensitive(self):
        first = Tag.objects.get_or_create_tag("Vacation")
        second = Tag.objects.get_or_create_tag("vacation")
        self.assertEqual(first.pk, second.pk)
        # first writer's casing is canonical
        self.assertEqual(second.name, "Vacation")
        self.assertEqual(Tag.objects.count(), 1)

    def test_get_or_create_tag_strips(self):
        tag = Tag.objects.get_or_create_tag("  work  ")
        self.assertEqual(tag.name, "work")

    def test_prune_orphans(self):
        used = Tag.objects.get_or_create_tag("used")
        orphan = Tag.objects.get_or_create_tag("orphan")
        FileTag.objects.create(file=self.create_file(), tag=used)
        Tag.objects.prune_orphans([used.pk, orphan.pk])
        self.assertTrue(Tag.objects.filter(pk=used.pk).exists())
        self.assertFalse(Tag.objects.filter(pk=orphan.pk).exists())

    def test_prune_orphans_keeps_album_tags(self):
        tag = Tag.objects.get_or_create_tag("albumonly")
        album = Albums.objects.create(user=self.user, name="A")
        AlbumTag.objects.create(album=album, tag=tag)
        Tag.objects.prune_orphans([tag.pk])
        self.assertTrue(Tag.objects.filter(pk=tag.pk).exists())


class SyncFileTagsTests(TagBaseTestCase):
    def test_sync_adds_and_removes_xmp_tags(self):
        file = self.create_file()
        file.exif = _xmp_exif(["alpha", "beta"])
        sync_file_tags(file)
        self.assertEqual(
            sorted(file.tags.values_list("tag__name", flat=True)),
            ["alpha", "beta"],
        )
        file.exif = _xmp_exif(["beta"])
        sync_file_tags(file)
        self.assertEqual(list(file.tags.values_list("tag__name", flat=True)), ["beta"])
        # the removed tag was orphaned and pruned from the vocabulary
        self.assertFalse(Tag.objects.filter(name="alpha").exists())

    def test_sync_preserves_user_tags(self):
        file = self.create_file()
        FileTag.objects.create(file=file, tag=Tag.objects.get_or_create_tag("manual"), xmp=False)
        file.exif = _xmp_exif([])
        sync_file_tags(file)
        self.assertEqual(list(file.tags.values_list("tag__name", flat=True)), ["manual"])

    def test_sync_reuses_canonical_tag(self):
        existing = Tag.objects.get_or_create_tag("Nature")
        file = self.create_file()
        file.exif = _xmp_exif(["nature"])
        sync_file_tags(file)
        self.assertEqual(list(file.tags.values_list("tag_id", flat=True)), [existing.pk])


@patch("home.consumers.dispatch_webhook_event.delay")
@patch("home.consumers.album_tag_websocket.apply_async")
@patch("home.consumers.file_tag_websocket.apply_async")
class ConsumerTagTests(TagBaseTestCase):
    """The tag consumer methods are synchronous, so they are invoked directly
    on a consumer with a stubbed scope instead of through a channels client."""

    def _consumer(self, user=None):
        consumer = HomeConsumer()
        consumer.scope = {"user": user or self.user}
        return consumer

    def test_add_and_remove_album_tag(self, _mock_file_ws, mock_album_ws, mock_dispatch):
        album = Albums.objects.create(user=self.user, name="A")
        # album creation fires album.created through the shared task object
        mock_dispatch.reset_mock()
        consumer = self._consumer()
        result = consumer.add_album_tag(user_id=self.user.id, pk=album.pk, tag=" Work ")
        self.assertIsNone(result)
        self.assertEqual(list(album.tags.values_list("tag__name", flat=True)), ["Work"])
        event = mock_album_ws.call_args.kwargs["args"][0]
        self.assertEqual(event["event"], "set-album-tags")
        self.assertEqual(event["added"], ["Work"])
        # tag changes never save the album row, so the webhook fires here
        self.assertEqual(mock_dispatch.call_count, 1)
        result = consumer.remove_album_tag(user_id=self.user.id, pk=album.pk, tag="Work")
        self.assertIsNone(result)
        self.assertEqual(album.tags.count(), 0)
        self.assertFalse(Tag.objects.filter(name="Work").exists())

    def test_album_tag_permission(self, _mock_file_ws, _mock_album_ws, _mock_dispatch):
        album = Albums.objects.create(user=self.user, name="A")
        other = CustomUser.objects.create_user(username="other", password=TEST_PASSWORD)  # nosec  # NOSONAR
        consumer = self._consumer(other)
        result = consumer.add_album_tag(user_id=other.id, pk=album.pk, tag="x")
        self.assertFalse(result["success"])
        self.assertEqual(album.tags.count(), 0)

    def test_bulk_edit_file_tags(self, mock_file_ws, _mock_album_ws, _mock_dispatch):
        first, second = self.create_file("a.txt"), self.create_file("b.txt")
        consumer = self._consumer()
        result = consumer.bulk_edit_file_tags(
            user_id=self.user.id, pks=[first.pk, second.pk], tags=[" work "], action="add"
        )
        self.assertIsNone(result)
        for file in (first, second):
            self.assertEqual(list(file.tags.values_list("tag__name", flat=True)), ["work"])
        event = mock_file_ws.call_args.kwargs["args"][0]
        self.assertEqual(event["event"], "bulk-set-file-tags")
        self.assertEqual(sorted(event["pks"]), sorted([first.pk, second.pk]))
        self.assertEqual(event["added"], ["work"])
        consumer.bulk_edit_file_tags(user_id=self.user.id, pks=[first.pk], tags=["work"], action="remove")
        self.assertEqual(first.tags.count(), 0)
        # still used by the second file, so the vocabulary keeps it
        self.assertTrue(Tag.objects.filter(name="work").exists())
        consumer.bulk_edit_file_tags(user_id=self.user.id, pks=[second.pk], tags=["work"], action="remove")
        self.assertFalse(Tag.objects.filter(name="work").exists())

    def test_bulk_edit_file_tags_validation(self, _mock_file_ws, _mock_album_ws, _mock_dispatch):
        consumer = self._consumer()
        self.assertFalse(consumer.bulk_edit_file_tags(user_id=self.user.id, pks=[], tags=[], action="add")["success"])
        result = consumer.bulk_edit_file_tags(user_id=self.user.id, pks=[], tags=["x"], action="bogus")
        self.assertFalse(result["success"])

    def test_bulk_edit_file_tags_skips_other_users(self, _mock_file_ws, _mock_album_ws, _mock_dispatch):
        file = self.create_file()
        other = CustomUser.objects.create_user(username="other2", password=TEST_PASSWORD)  # nosec  # NOSONAR
        consumer = self._consumer(other)
        consumer.bulk_edit_file_tags(user_id=other.id, pks=[file.pk], tags=["x"], action="add")
        self.assertEqual(file.tags.count(), 0)

    def test_bulk_edit_album_tags(self, _mock_file_ws, mock_album_ws, mock_dispatch):
        first = Albums.objects.create(user=self.user, name="A1")
        second = Albums.objects.create(user=self.user, name="A2")
        # album creation fires album.created through the shared task object
        mock_dispatch.reset_mock()
        consumer = self._consumer()
        result = consumer.bulk_edit_album_tags(
            user_id=self.user.id, pks=[first.pk, second.pk], tags=["Trip"], action="add"
        )
        self.assertIsNone(result)
        for album in (first, second):
            self.assertEqual(list(album.tags.values_list("tag__name", flat=True)), ["Trip"])
        # one set-album-tags broadcast and one album.updated per changed album
        self.assertEqual(mock_album_ws.call_count, 2)
        self.assertEqual(mock_dispatch.call_count, 2)
        consumer.bulk_edit_album_tags(user_id=self.user.id, pks=[first.pk, second.pk], tags=["Trip"], action="remove")
        self.assertEqual(first.tags.count(), 0)
        self.assertEqual(second.tags.count(), 0)
        self.assertFalse(Tag.objects.filter(name="Trip").exists())


class AlbumCreateTagsTests(TagBaseTestCase):
    def _create_album(self, body):
        self.client.force_login(self.user)
        return self.client.post(reverse("api:album"), json.dumps(body), content_type="application/json")

    @patch("home.signals.dispatch_webhook_event.delay")
    def test_create_album_with_tags(self, mock_dispatch):
        response = self._create_album({"name": "Trip", "tags": " travel , Iceland ,"})
        self.assertEqual(response.status_code, 200)
        album = Albums.objects.get(user=self.user, name="Trip")
        self.assertEqual(
            sorted(album.tags.values_list("tag__name", flat=True)),
            ["Iceland", "travel"],
        )
        # the album.created payload must carry the tags or include-filters
        # could never match this event
        payload = mock_dispatch.call_args.args[2]
        self.assertEqual(sorted(payload["tags"]), ["Iceland", "travel"])

    def test_create_album_with_tags_list(self):
        response = self._create_album({"name": "ListTags", "tags": ["one", "two"]})
        self.assertEqual(response.status_code, 200)
        album = Albums.objects.get(user=self.user, name="ListTags")
        self.assertEqual(sorted(album.tags.values_list("tag__name", flat=True)), ["one", "two"])

    def test_create_album_without_tags(self):
        response = self._create_album({"name": "Bare"})
        self.assertEqual(response.status_code, 200)
        album = Albums.objects.get(user=self.user, name="Bare")
        self.assertEqual(album.tags.count(), 0)
