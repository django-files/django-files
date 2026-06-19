import logging
from datetime import timedelta

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils.timezone import now
from home.models import Albums, ShortURLs, Stream
from oauth.models import CustomUser

log = logging.getLogger("app")


class UserApiTestCase(TestCase):
    """Test User API endpoints - Simple version to avoid timeouts"""

    def setUp(self):
        """Set up test environment"""
        call_command("loaddata", "settings/fixtures/sitesettings.json", verbosity=0)

        # Create test users
        self.superuser = CustomUser.objects.create_superuser(
            username="superuser",
            email="super@test.com",
            password="12345",  # nosec
        )

        self.regular_user = CustomUser.objects.create_user(
            username="regularuser",
            email="regular@test.com",
            password="12345",  # nosec
        )

    def test_current_user_get_with_auth(self):
        """Test GET /api/user/ with valid authorization"""
        response = self.client.get(
            reverse("api:current-user"), HTTP_AUTHORIZATION=f"Bearer {self.regular_user.authorization}"
        )
        self.assertEqual(response.status_code, 200)

    def test_current_user_get_without_auth(self):
        """Test GET /api/user/ without authorization"""
        response = self.client.get(reverse("api:current-user"))
        self.assertEqual(response.status_code, 401)

    def test_users_list_as_superuser(self):
        """Test GET /api/users/ as superuser"""
        response = self.client.get(reverse("api:users"), HTTP_AUTHORIZATION=f"Bearer {self.superuser.authorization}")
        self.assertEqual(response.status_code, 200)

    def test_users_list_as_regular_user_denied(self):
        """Test GET /api/users/ as regular user (should be denied)"""
        response = self.client.get(
            reverse("api:users"), HTTP_AUTHORIZATION=f"Bearer {self.regular_user.authorization}"
        )
        self.assertEqual(response.status_code, 403)


class OrderingApiTestCase(TestCase):
    """Validate the ?ordering= query param on paginated list endpoints."""

    def setUp(self):
        call_command("loaddata", "settings/fixtures/sitesettings.json", verbosity=0)
        self.user = CustomUser.objects.create_user(
            username="orderuser",
            email="order@test.com",
            password="12345",  # nosec
        )
        self.auth = self.user.authorization

        # Albums: names "bravo", "alpha", "charlie"; backdate to give them
        # distinct created times since `date` is auto_now_add.
        self.album_alpha = Albums.objects.create(user=self.user, name="alpha")
        self.album_bravo = Albums.objects.create(user=self.user, name="bravo")
        self.album_charlie = Albums.objects.create(user=self.user, name="charlie")
        # Force a known creation ordering: charlie newest, bravo middle, alpha oldest.
        for offset, album in enumerate([self.album_alpha, self.album_bravo, self.album_charlie]):
            Albums.objects.filter(pk=album.pk).update(date=now() - timedelta(days=10 - offset))

        # Shorts
        ShortURLs.objects.create(url="https://example.com/a", short="zzz", user=self.user, views=5)
        ShortURLs.objects.create(url="https://example.com/b", short="aaa", user=self.user, views=42)
        ShortURLs.objects.create(url="https://example.com/c", short="mmm", user=self.user, views=1)

        # Streams
        Stream.objects.create(name="zeta", title="z", user=self.user, unique_views=7)
        Stream.objects.create(name="alpha", title="a", user=self.user, unique_views=99)
        Stream.objects.create(name="mike", title="m", user=self.user, unique_views=3)

    def _get(self, url):
        return self.client.get(url, HTTP_AUTHORIZATION=f"Bearer {self.auth}")

    # ----- albums -----

    def test_albums_default_order_is_newest_first(self):
        r = self._get(reverse("api:albums-amount", kwargs={"page": 1, "count": 100}))
        self.assertEqual(r.status_code, 200)
        names = [a["name"] for a in r.json()["albums"]]
        self.assertEqual(names, ["charlie", "bravo", "alpha"])

    def test_albums_ordering_by_name_asc(self):
        r = self._get(reverse("api:albums-amount", kwargs={"page": 1, "count": 100}) + "?ordering=name")
        names = [a["name"] for a in r.json()["albums"]]
        self.assertEqual(names, ["alpha", "bravo", "charlie"])

    def test_albums_ordering_by_name_desc(self):
        r = self._get(reverse("api:albums-amount", kwargs={"page": 1, "count": 100}) + "?ordering=-name")
        names = [a["name"] for a in r.json()["albums"]]
        self.assertEqual(names, ["charlie", "bravo", "alpha"])

    def test_albums_unknown_ordering_falls_back_to_default(self):
        r = self._get(reverse("api:albums-amount", kwargs={"page": 1, "count": 100}) + "?ordering=password")
        names = [a["name"] for a in r.json()["albums"]]
        self.assertEqual(names, ["charlie", "bravo", "alpha"])

    # ----- shorts -----

    def test_shorts_ordering_by_name(self):
        r = self._get(reverse("api:shorts-amount", kwargs={"page": 1, "count": 100}) + "?ordering=name")
        slugs = [s["short"] for s in r.json()["shorts"]]
        self.assertEqual(slugs, ["aaa", "mmm", "zzz"])

    def test_shorts_ordering_by_views_desc(self):
        r = self._get(reverse("api:shorts-amount", kwargs={"page": 1, "count": 100}) + "?ordering=-views")
        slugs = [s["short"] for s in r.json()["shorts"]]
        self.assertEqual(slugs, ["aaa", "zzz", "mmm"])

    # ----- streams -----

    def test_streams_ordering_by_name(self):
        r = self._get(reverse("api:streams-amount", kwargs={"page": 1, "count": 100}) + "?ordering=name")
        names = [s["name"] for s in r.json()["streams"]]
        self.assertEqual(names, ["alpha", "mike", "zeta"])

    def test_streams_ordering_by_views_desc(self):
        r = self._get(reverse("api:streams-amount", kwargs={"page": 1, "count": 100}) + "?ordering=-views")
        names = [s["name"] for s in r.json()["streams"]]
        self.assertEqual(names, ["alpha", "zeta", "mike"])


class StreamLifecycleTestCase(TestCase):
    """View stream list, create a stream, open the stream page."""

    def setUp(self):
        call_command("loaddata", "settings/fixtures/sitesettings.json", verbosity=0)
        self.user = CustomUser.objects.create_user(
            username="streamuser",
            email="stream@test.com",
            password="12345",  # nosec
        )
        self.auth = self.user.authorization

    def _get(self, url):
        return self.client.get(url, HTTP_AUTHORIZATION=f"Bearer {self.auth}")

    def test_stream_list_empty(self):
        r = self._get(reverse("api:streams"))
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("streams", data)
        self.assertEqual(data["streams"], [])

    def test_create_stream(self):
        self.client.login(username="streamuser", password="12345")  # nosec
        r = self.client.post(
            reverse("api:stream-create"),
            data={"name": "teststream", "title": "Test Stream"},
        )
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["name"], "teststream")
        self.assertIn("stream_token", data)

    def test_create_stream_idempotent(self):
        self.client.login(username="streamuser", password="12345")  # nosec
        self.client.post(reverse("api:stream-create"), data={"name": "mystream", "title": "My Stream"})
        r = self.client.post(reverse("api:stream-create"), data={"name": "mystream", "title": "My Stream"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["name"], "mystream")

    def test_create_stream_missing_name(self):
        self.client.login(username="streamuser", password="12345")  # nosec
        r = self.client.post(reverse("api:stream-create"), data={"title": "No Name"})
        self.assertEqual(r.status_code, 400)

    def test_stream_list_after_create(self):
        Stream.objects.create(name="listed", title="Listed", user=self.user, public=True)
        r = self._get(reverse("api:streams"))
        self.assertEqual(r.status_code, 200)
        names = [s["name"] for s in r.json()["streams"]]
        self.assertIn("listed", names)

    def test_open_public_stream_page(self):
        Stream.objects.create(name="publicstream", title="Public", user=self.user, public=True)
        r = self.client.get(reverse("home:live", kwargs={"key": "publicstream"}))
        self.assertEqual(r.status_code, 200)

    def test_open_private_stream_page_unauthenticated(self):
        Stream.objects.create(name="privatestream", title="Private", user=self.user, public=False)
        r = self.client.get(reverse("home:live", kwargs={"key": "privatestream"}))
        self.assertEqual(r.status_code, 404)

    def test_open_private_stream_page_authenticated(self):
        Stream.objects.create(name="mystream", title="Mine", user=self.user, public=False)
        self.client.login(username="streamuser", password="12345")  # nosec
        r = self.client.get(reverse("home:live", kwargs={"key": "mystream"}))
        self.assertEqual(r.status_code, 200)
