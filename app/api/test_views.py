import json
import logging
from datetime import timedelta

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils.timezone import now
from home.models import Albums, ShortURLs, Stream
from home.util.auth import hash_token
from oauth.models import CustomUser

log = logging.getLogger("app")


class UserApiTestCase(TestCase):
    """Test User API endpoints - Simple version to avoid timeouts"""

    def setUp(self):
        """Set up test environment"""
        call_command("loaddata", "settings/fixtures/sitesettings.json", verbosity=0)

        self.superuser = CustomUser.objects.create_superuser(
            username="superuser",
            email="super@test.com",
            password="12345",  # nosec
        )
        self.superuser_token = self.superuser.rotate_authorization()

        self.regular_user = CustomUser.objects.create_user(
            username="regularuser",
            email="regular@test.com",
            password="12345",  # nosec
        )
        self.regular_token = self.regular_user.rotate_authorization()

    def test_current_user_get_with_auth(self):
        """Test GET /api/user/ with valid authorization"""
        response = self.client.get(reverse("api:current-user"), HTTP_AUTHORIZATION=f"Bearer {self.regular_token}")
        self.assertEqual(response.status_code, 200)

    def test_current_user_get_without_auth(self):
        """Test GET /api/user/ without authorization"""
        response = self.client.get(reverse("api:current-user"))
        self.assertEqual(response.status_code, 401)

    def test_current_user_get_with_hash_rejected(self):
        """Presenting the stored hash directly must be rejected (hash-of-hash mismatch)."""
        response = self.client.get(
            reverse("api:current-user"), HTTP_AUTHORIZATION=f"Bearer {self.regular_user.authorization}"
        )
        self.assertEqual(response.status_code, 401)

    def test_users_list_as_superuser(self):
        """Test GET /api/users/ as superuser"""
        response = self.client.get(reverse("api:users"), HTTP_AUTHORIZATION=f"Bearer {self.superuser_token}")
        self.assertEqual(response.status_code, 200)

    def test_users_list_as_regular_user_denied(self):
        """Test GET /api/users/ as regular user (should be denied)"""
        response = self.client.get(reverse("api:users"), HTTP_AUTHORIZATION=f"Bearer {self.regular_token}")
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
        self.auth = self.user.rotate_authorization()

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
        self.auth = self.user.rotate_authorization()

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


# ---------------------------------------------------------------------------
# Auth endpoint tests
# ---------------------------------------------------------------------------


class BearerTokenAuthTestCase(TestCase):
    """Tests for the hashed-at-rest Bearer token authentication scheme."""

    def setUp(self):
        call_command("loaddata", "settings/fixtures/sitesettings.json", verbosity=0)
        self.user = CustomUser.objects.create_user(
            username="authuser",
            email="auth@test.com",
            password="correcthorse",  # nosec
        )
        self.token = self.user.rotate_authorization()

    # --- basic Bearer auth ---

    def test_valid_bearer_token_authenticates(self):
        r = self.client.get(reverse("api:current-user"), HTTP_AUTHORIZATION=f"Bearer {self.token}")
        self.assertEqual(r.status_code, 200)

    def test_missing_auth_header_returns_401(self):
        r = self.client.get(reverse("api:current-user"))
        self.assertEqual(r.status_code, 401)

    def test_wrong_token_returns_401(self):
        r = self.client.get(reverse("api:current-user"), HTTP_AUTHORIZATION="Bearer wrongtoken")
        self.assertEqual(r.status_code, 401)

    def test_stored_hash_presented_as_bearer_is_rejected(self):
        """The DB stores HMAC(token); presenting the hash itself must fail."""
        r = self.client.get(
            reverse("api:current-user"),
            HTTP_AUTHORIZATION=f"Bearer {self.user.authorization}",
        )
        self.assertEqual(r.status_code, 401)

    def test_token_auth_without_bearer_prefix_rejected(self):
        r = self.client.get(reverse("api:current-user"), HTTP_AUTHORIZATION=self.token)
        self.assertEqual(r.status_code, 401)

    # --- hash storage sanity ---

    def test_authorization_field_is_not_plaintext(self):
        """The stored authorization value must differ from the plaintext token."""
        self.assertNotEqual(self.user.authorization, self.token)

    def test_authorization_field_is_64_chars(self):
        """HMAC-SHA256 hex digest is always 64 characters."""
        self.assertEqual(len(self.user.authorization), 64)

    def test_hash_is_hmac_of_plaintext(self):
        expected = hash_token(self.token)
        self.assertEqual(self.user.authorization, expected)


class TokenRotationTestCase(TestCase):
    """Tests for POST /api/token/ token rotation endpoint."""

    def setUp(self):
        call_command("loaddata", "settings/fixtures/sitesettings.json", verbosity=0)
        self.user = CustomUser.objects.create_user(
            username="rotateuser",
            email="rotate@test.com",
            password="12345",  # nosec
        )
        self.token = self.user.rotate_authorization()

    def test_rotate_via_session_returns_new_plaintext(self):
        self.client.login(username="rotateuser", password="12345")  # nosec
        r = self.client.post(reverse("api:token"), HTTP_X_CSRFTOKEN=self.client.cookies.get("csrftoken", ""))
        self.assertEqual(r.status_code, 200)
        new_token = r.content.decode()
        self.assertNotEqual(new_token, self.token)
        self.assertEqual(len(new_token), 32)

    def test_rotate_invalidates_old_token(self):
        self.client.login(username="rotateuser", password="12345")  # nosec
        self.client.post(reverse("api:token"))
        # Fresh client: no session, only Bearer auth is tested.
        from django.test import Client

        c = Client()
        r = c.get(reverse("api:current-user"), HTTP_AUTHORIZATION=f"Bearer {self.token}")
        self.assertEqual(r.status_code, 401)

    def test_rotate_new_token_authenticates(self):
        self.client.login(username="rotateuser", password="12345")  # nosec
        r = self.client.post(reverse("api:token"))
        new_token = r.content.decode()
        # Use a fresh client to ensure no session carries the auth.
        from django.test import Client

        c = Client()
        r2 = c.get(reverse("api:current-user"), HTTP_AUTHORIZATION=f"Bearer {new_token}")
        self.assertEqual(r2.status_code, 200)

    def test_rotate_unauthenticated_returns_401(self):
        r = self.client.post(reverse("api:token"))
        self.assertEqual(r.status_code, 401)

    def test_rotate_updates_authorization_updated_at(self):
        before = self.user.authorization_updated_at
        self.user.rotate_authorization()
        self.user.refresh_from_db()
        self.assertIsNotNone(self.user.authorization_updated_at)
        if before:
            self.assertGreater(self.user.authorization_updated_at, before)


class LocalAuthForNativeClientTestCase(TestCase):
    """Tests for POST /api/auth/token/ — the native-client login endpoint."""

    def setUp(self):
        from django.core.cache import cache as _cache

        call_command("loaddata", "settings/fixtures/sitesettings.json", verbosity=0)
        # Clear rate-limit counters so each test starts with a clean slate.
        _cache.clear()
        self.user = CustomUser.objects.create_user(
            username="nativeuser",
            email="native@test.com",
            password="secret123",  # nosec
        )

    def test_login_with_valid_credentials_returns_token(self):
        r = self.client.post(
            reverse("api:auth-token"),
            data=json.dumps({"username": "nativeuser", "password": "secret123"}),
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("token", data)
        token = data["token"]
        self.assertEqual(len(token), 32)

    def test_returned_token_authenticates_api(self):
        r = self.client.post(
            reverse("api:auth-token"),
            data=json.dumps({"username": "nativeuser", "password": "secret123"}),
            content_type="application/json",
        )
        token = r.json()["token"]
        from django.test import Client

        c = Client()
        r2 = c.get(reverse("api:current-user"), HTTP_AUTHORIZATION=f"Bearer {token}")
        self.assertEqual(r2.status_code, 200)

    def test_wrong_password_returns_401(self):
        r = self.client.post(
            reverse("api:auth-token"),
            data=json.dumps({"username": "nativeuser", "password": "wrong"}),
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 401)

    def test_login_token_is_not_the_stored_hash(self):
        """The returned plaintext must differ from what is stored in the DB."""
        r = self.client.post(
            reverse("api:auth-token"),
            data=json.dumps({"username": "nativeuser", "password": "secret123"}),
            content_type="application/json",
        )
        token = r.json()["token"]
        self.user.refresh_from_db()
        self.assertNotEqual(token, self.user.authorization)

    def test_session_based_call_returns_token_without_rotating(self):
        """When called with an active session and api_token set, token is stable."""
        login_r = self.client.post(
            reverse("api:auth-token"),
            data=json.dumps({"username": "nativeuser", "password": "secret123"}),
            content_type="application/json",
        )
        first_token = login_r.json()["token"]

        # Second call with same session (Android reAuthenticate pattern).
        r2 = self.client.post(
            reverse("api:auth-token"),
            data=json.dumps({"username": "nativeuser", "password": "secret123"}),
            content_type="application/json",
        )
        # Session already authenticated; returns from session, no rotation.
        second_token = r2.json()["token"]
        self.assertEqual(first_token, second_token)


class AuthSessionTestCase(TestCase):
    """Tests for POST /api/auth/session/ — Bearer token → session cookie exchange."""

    def setUp(self):
        call_command("loaddata", "settings/fixtures/sitesettings.json", verbosity=0)
        self.user = CustomUser.objects.create_user(
            username="sessionuser",
            email="session@test.com",
            password="12345",  # nosec
        )
        self.token = self.user.rotate_authorization()

    def test_bearer_token_exchanges_for_session_cookie(self):
        r = self.client.post(
            reverse("api:auth-session"),
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(r.status_code, 204)
        self.assertIn("sessionid", self.client.cookies)

    def test_session_after_exchange_allows_web_access(self):
        self.client.post(
            reverse("api:auth-session"),
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        r = self.client.get(reverse("home:index"))
        self.assertEqual(r.status_code, 200)

    def test_invalid_token_rejected(self):
        r = self.client.post(
            reverse("api:auth-session"),
            HTTP_AUTHORIZATION="Bearer badtoken",
        )
        self.assertEqual(r.status_code, 401)

    def test_no_auth_header_rejected(self):
        r = self.client.post(reverse("api:auth-session"))
        self.assertEqual(r.status_code, 401)


class LogoutTokenRotationTestCase(TestCase):
    """Token must be rotated on logout so previously-leaked tokens are dead."""

    def setUp(self):
        call_command("loaddata", "settings/fixtures/sitesettings.json", verbosity=0)
        self.user = CustomUser.objects.create_user(
            username="logoutuser",
            email="logout@test.com",
            password="12345",  # nosec
        )
        self.token = self.user.rotate_authorization()

    def test_token_rotated_after_logout(self):
        self.client.login(username="logoutuser", password="12345")  # nosec
        old_auth = self.user.authorization

        self.client.post(reverse("oauth:logout"))

        self.user.refresh_from_db()
        self.assertNotEqual(self.user.authorization, old_auth)

    def test_old_token_rejected_after_logout(self):
        self.client.login(username="logoutuser", password="12345")  # nosec
        self.client.post(reverse("oauth:logout"))

        from django.test import Client

        c = Client()
        r = c.get(reverse("api:current-user"), HTTP_AUTHORIZATION=f"Bearer {self.token}")
        self.assertEqual(r.status_code, 401)
