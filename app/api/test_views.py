import json
import logging
from datetime import timedelta

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils.timezone import now
from home.models import Albums, ShortURLs, Stream
from home.util.auth import create_api_token, hash_token
from oauth.models import ApiToken, CustomUser

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
        self.superuser_token = create_api_token(self.superuser, name="Test Token")

        self.regular_user = CustomUser.objects.create_user(
            username="regularuser",
            email="regular@test.com",
            password="12345",  # nosec
        )
        self.regular_token = create_api_token(self.regular_user, name="Test Token")

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
        # Get the token hash from the ApiToken object
        token_obj = ApiToken.objects.filter(user=self.regular_user).first()
        if token_obj:
            response = self.client.get(
                reverse("api:current-user"), HTTP_AUTHORIZATION=f"Bearer {token_obj.token_hash}"
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
        self.auth = create_api_token(self.user, name="Test Token")

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
        self.auth = create_api_token(self.user, name="Test Token")

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
        self.token = create_api_token(self.user, name="Test Token")

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
        token_obj = ApiToken.objects.filter(user=self.user).first()
        if token_obj:
            r = self.client.get(
                reverse("api:current-user"),
                HTTP_AUTHORIZATION=f"Bearer {token_obj.token_hash}",
            )
            self.assertEqual(r.status_code, 401)

    def test_token_auth_without_bearer_prefix_accepted(self):
        # Older iOS clients send the raw token as the Authorization value
        # without the Bearer prefix; server accepts this for backward compat.
        r = self.client.get(reverse("api:current-user"), HTTP_AUTHORIZATION=self.token)
        self.assertEqual(r.status_code, 200)

    # --- hash storage sanity ---

    def test_token_hash_is_not_plaintext(self):
        """The stored token_hash value must differ from the plaintext token."""
        token_obj = ApiToken.objects.filter(user=self.user).first()
        if token_obj:
            self.assertNotEqual(token_obj.token_hash, self.token)

    def test_token_hash_is_64_chars(self):
        """HMAC-SHA256 hex digest is always 64 characters."""
        token_obj = ApiToken.objects.filter(user=self.user).first()
        if token_obj:
            self.assertEqual(len(token_obj.token_hash), 64)

    def test_hash_is_hmac_of_plaintext(self):
        expected = hash_token(self.token)
        token_obj = ApiToken.objects.filter(user=self.user).first()
        if token_obj:
            self.assertEqual(token_obj.token_hash, expected)


class TokenRotationTestCase(TestCase):
    """Tests for POST /api/token/ token creation endpoint."""

    def setUp(self):
        call_command("loaddata", "settings/fixtures/sitesettings.json", verbosity=0)
        self.user = CustomUser.objects.create_user(
            username="rotateuser",
            email="rotate@test.com",
            password="12345",  # nosec
        )
        self.token = create_api_token(self.user, name="Test Token")

    def test_create_via_session_returns_new_plaintext(self):
        self.client.login(username="rotateuser", password="12345")  # nosec
        r = self.client.post(reverse("api:token"), HTTP_X_CSRFTOKEN=self.client.cookies.get("csrftoken", ""))
        self.assertEqual(r.status_code, 200)
        new_token = r.json()["token"]
        self.assertNotEqual(new_token, self.token)
        self.assertEqual(len(new_token), 32)

    def test_create_new_token_does_not_invalidate_old(self):
        self.client.login(username="rotateuser", password="12345")  # nosec
        initial_count = ApiToken.objects.filter(user=self.user).count()
        self.client.post(reverse("api:token"))
        # Fresh client: no session, only Bearer auth is tested.
        from django.test import Client

        c = Client()
        r = c.get(reverse("api:current-user"), HTTP_AUTHORIZATION=f"Bearer {self.token}")
        self.assertEqual(r.status_code, 200)
        # Verify that a new token was created
        new_count = ApiToken.objects.filter(user=self.user).count()
        self.assertEqual(new_count, initial_count + 1)

    def test_create_new_token_authenticates(self):
        self.client.login(username="rotateuser", password="12345")  # nosec
        r = self.client.post(reverse("api:token"))
        new_token = r.json()["token"]
        # Use a fresh client to ensure no session carries the auth.
        from django.test import Client

        c = Client()
        r2 = c.get(reverse("api:current-user"), HTTP_AUTHORIZATION=f"Bearer {new_token}")
        self.assertEqual(r2.status_code, 200)

    def test_create_unauthenticated_redirects_or_rejects(self):
        r = self.client.post(reverse("api:token"))
        self.assertIn(r.status_code, [302, 401, 403])

    def test_create_adds_new_api_token(self):
        initial_count = ApiToken.objects.filter(user=self.user).count()
        self.client.login(username="rotateuser", password="12345")  # nosec
        self.client.post(reverse("api:token"))
        self.user.refresh_from_db()
        new_count = ApiToken.objects.filter(user=self.user).count()
        self.assertEqual(new_count, initial_count + 1)


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
        token_obj = ApiToken.objects.filter(user=self.user).first()
        if token_obj:
            self.assertNotEqual(token, token_obj.token_hash)

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
        self.token = create_api_token(self.user, name="Test Token")

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
    """Logout must NOT touch ApiToken rows — only the session is flushed."""

    def setUp(self):
        call_command("loaddata", "settings/fixtures/sitesettings.json", verbosity=0)
        self.user = CustomUser.objects.create_user(
            username="logoutuser",
            email="logout@test.com",
            password="12345",  # nosec
        )
        self.token = create_api_token(self.user, name="Test Token")

    def test_token_remains_active_after_logout(self):
        """Logout must leave ApiToken rows untouched."""
        self.client.login(username="logoutuser", password="12345")  # nosec
        self.client.post(reverse("oauth:logout"))

        token_obj = ApiToken.objects.filter(user=self.user).first()
        self.assertIsNotNone(token_obj)
        self.assertTrue(token_obj.is_active)

    def test_bearer_token_still_works_after_logout(self):
        """A Bearer token must remain valid after its owner logs out of the web session."""
        self.client.login(username="logoutuser", password="12345")  # nosec
        self.client.post(reverse("oauth:logout"))

        from django.test import Client

        c = Client()
        r = c.get(reverse("api:current-user"), HTTP_AUTHORIZATION=f"Bearer {self.token}")
        self.assertEqual(r.status_code, 200)


class ApiTokenListCreateTestCase(TestCase):
    """GET /api/token/ and POST /api/token/"""

    def setUp(self):
        call_command("loaddata", "settings/fixtures/sitesettings.json", verbosity=0)
        self.user = CustomUser.objects.create_user(username="tokenuser", password="pass")
        self.client.login(username="tokenuser", password="pass")

    def test_list_tokens_empty(self):
        response = self.client.get("/api/token/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["tokens"], [])
        self.assertEqual(data["count"], 0)

    def test_list_tokens_returns_user_tokens(self):
        ApiToken.objects.create(user=self.user, token_hash=hash_token("tok1"), name="Token 1")
        ApiToken.objects.create(user=self.user, token_hash=hash_token("tok2"), name="Token 2")
        response = self.client.get("/api/token/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["count"], 2)

    def test_list_tokens_excludes_other_users(self):
        other = CustomUser.objects.create_user(username="other", password="pass")
        ApiToken.objects.create(user=other, token_hash=hash_token("othertoken"), name="Other")
        response = self.client.get("/api/token/")
        data = response.json()
        self.assertEqual(data["count"], 0)

    def test_create_token(self):
        response = self.client.post(
            "/api/token/",
            data='{"name": "My Device"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("token", data)
        self.assertTrue(ApiToken.objects.filter(user=self.user).exists())

    def test_create_token_does_not_invalidate_existing(self):
        ApiToken.objects.create(user=self.user, token_hash=hash_token("existing"), name="Existing")
        self.client.post(
            "/api/token/",
            data='{"name": "New Token"}',
            content_type="application/json",
        )
        self.assertEqual(ApiToken.objects.filter(user=self.user).count(), 2)

    def test_create_requires_login(self):
        self.client.logout()
        response = self.client.post("/api/token/", data="{}", content_type="application/json")
        self.assertIn(response.status_code, [302, 401, 403])


class ApiTokenDeleteTestCase(TestCase):
    """DELETE /api/token/<uuid>/"""

    def setUp(self):
        call_command("loaddata", "settings/fixtures/sitesettings.json", verbosity=0)
        self.user = CustomUser.objects.create_user(username="deluser", password="pass")
        self.client.login(username="deluser", password="pass")
        self.token = ApiToken.objects.create(user=self.user, token_hash=hash_token("mytoken"), name="My Token")

    def test_delete_token(self):
        response = self.client.delete(f"/api/token/{self.token.pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(ApiToken.objects.filter(pk=self.token.pk).exists())

    def test_disable_token(self):
        response = self.client.patch(f"/api/token/{self.token.pk}/")
        self.assertEqual(response.status_code, 200)
        self.token.refresh_from_db()
        self.assertFalse(self.token.is_active)

    def test_cannot_disable_other_users_token(self):
        other = CustomUser.objects.create_user(username="other2", password="pass")
        other_token = ApiToken.objects.create(user=other, token_hash=hash_token("othertoken2"), name="Other")
        response = self.client.delete(f"/api/token/{other_token.pk}/")
        self.assertEqual(response.status_code, 404)
        other_token.refresh_from_db()
        self.assertTrue(other_token.is_active)


class ApiTokenAuthTestCase(TestCase):
    """auth_from_token middleware with ApiToken model"""

    def setUp(self):
        call_command("loaddata", "settings/fixtures/sitesettings.json", verbosity=0)
        self.user = CustomUser.objects.create_user(username="authuser", password="pass")
        self.plaintext = "testbearertoken12345678"
        self.token = ApiToken.objects.create(
            user=self.user,
            token_hash=hash_token(self.plaintext),
            name="Test",
        )

    def test_bearer_token_authenticates(self):
        response = self.client.get(
            reverse("api:current-user"),
            HTTP_AUTHORIZATION=f"Bearer {self.plaintext}",
        )
        self.assertEqual(response.status_code, 200)

    def test_inactive_token_rejected(self):
        self.token.is_active = False
        self.token.save()
        response = self.client.get(
            reverse("api:current-user"),
            HTTP_AUTHORIZATION=f"Bearer {self.plaintext}",
        )
        self.assertEqual(response.status_code, 401)
        self.assertFalse(self.token.is_valid())

    def test_expired_token_rejected(self):
        from datetime import timedelta

        self.token.expires_at = now() - timedelta(hours=1)
        self.token.save()
        response = self.client.get(
            reverse("api:current-user"),
            HTTP_AUTHORIZATION=f"Bearer {self.plaintext}",
        )
        self.assertEqual(response.status_code, 401)
        self.assertFalse(self.token.is_valid())

    def test_valid_token_passes(self):
        self.assertTrue(self.token.is_valid())
        response = self.client.get(
            reverse("api:current-user"),
            HTTP_AUTHORIZATION=f"Bearer {self.plaintext}",
        )
        self.assertEqual(response.status_code, 200)
