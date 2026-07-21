import json
import logging
import tempfile
from datetime import timedelta

from api.utils import remote_url_error
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils.timezone import now
from djangofiles.test_utils import TEST_PASSWORD, WRONG_PASSWORD
from home.models import Albums, Files, ShortURLs, Stream
from home.util.auth import create_api_token, hash_token
from oauth.models import ApiToken, CustomUser

log = logging.getLogger("app")


class UserApiTestCase(TestCase):
    """Test User API endpoints - Simple version to avoid timeouts"""

    @classmethod
    def setUpTestData(cls):
        """Set up test environment"""
        call_command("loaddata", "settings/fixtures/sitesettings.json", verbosity=0)

        cls.superuser = CustomUser.objects.create_superuser(
            username="superuser",
            email="super@test.com",
            password=TEST_PASSWORD,  # nosec  # NOSONAR
        )
        cls.superuser_token = create_api_token(cls.superuser, name="Test Token")

        cls.regular_user = CustomUser.objects.create_user(
            username="regularuser",
            email="regular@test.com",
            password=TEST_PASSWORD,  # nosec  # NOSONAR
        )
        cls.regular_token = create_api_token(cls.regular_user, name="Test Token")

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

    @classmethod
    def setUpTestData(cls):
        call_command("loaddata", "settings/fixtures/sitesettings.json", verbosity=0)
        cls.user = CustomUser.objects.create_user(
            username="orderuser",
            email="order@test.com",
            password=TEST_PASSWORD,  # nosec  # NOSONAR
        )
        cls.auth = create_api_token(cls.user, name="Test Token")

        # Albums: names "bravo", "alpha", "charlie"; backdate to give them
        # distinct created times since `date` is auto_now_add.
        cls.album_alpha = Albums.objects.create(user=cls.user, name="alpha")
        cls.album_bravo = Albums.objects.create(user=cls.user, name="bravo")
        cls.album_charlie = Albums.objects.create(user=cls.user, name="charlie")
        # Force a known creation ordering: charlie newest, bravo middle, alpha oldest.
        for offset, album in enumerate([cls.album_alpha, cls.album_bravo, cls.album_charlie]):
            Albums.objects.filter(pk=album.pk).update(date=now() - timedelta(days=10 - offset))

        # Shorts
        ShortURLs.objects.create(url="https://example.com/a", short="zzz", user=cls.user, views=5)
        ShortURLs.objects.create(url="https://example.com/b", short="aaa", user=cls.user, views=42)
        ShortURLs.objects.create(url="https://example.com/c", short="mmm", user=cls.user, views=1)

        # Streams
        Stream.objects.create(name="zeta", title="z", user=cls.user, unique_views=7)
        Stream.objects.create(name="alpha", title="a", user=cls.user, unique_views=99)
        Stream.objects.create(name="mike", title="m", user=cls.user, unique_views=3)

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

    @classmethod
    def setUpTestData(cls):
        call_command("loaddata", "settings/fixtures/sitesettings.json", verbosity=0)
        cls.user = CustomUser.objects.create_user(
            username="streamuser",
            email="stream@test.com",
            password=TEST_PASSWORD,  # nosec  # NOSONAR
        )
        cls.auth = create_api_token(cls.user, name="Test Token")

    def _get(self, url):
        return self.client.get(url, HTTP_AUTHORIZATION=f"Bearer {self.auth}")

    def test_stream_list_empty(self):
        r = self._get(reverse("api:streams"))
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("streams", data)
        self.assertEqual(data["streams"], [])

    def test_create_stream(self):
        self.client.login(username="streamuser", password=TEST_PASSWORD)  # nosec  # NOSONAR
        r = self.client.post(
            reverse("api:stream-create"),
            data={"name": "teststream", "title": "Test Stream"},
        )
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["name"], "teststream")
        self.assertIn("stream_token", data)

    def test_create_stream_idempotent(self):
        self.client.login(username="streamuser", password=TEST_PASSWORD)  # nosec  # NOSONAR
        self.client.post(reverse("api:stream-create"), data={"name": "mystream", "title": "My Stream"})
        r = self.client.post(reverse("api:stream-create"), data={"name": "mystream", "title": "My Stream"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["name"], "mystream")

    def test_create_stream_missing_name(self):
        self.client.login(username="streamuser", password=TEST_PASSWORD)  # nosec  # NOSONAR
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
        self.client.login(username="streamuser", password=TEST_PASSWORD)  # nosec  # NOSONAR
        r = self.client.get(reverse("home:live", kwargs={"key": "mystream"}))
        self.assertEqual(r.status_code, 200)


class HlsAuthRequestTestCase(TestCase):
    """
    Covers the nginx auth_request gate (GET /api/stream/hls-auth/) which decides
    every /hls/ request. Each test exercises one of the three accepted auth
    bundles or one of the rejection paths.
    """

    @classmethod
    def setUpTestData(cls):
        call_command("loaddata", "settings/fixtures/sitesettings.json", verbosity=0)
        cls.user = CustomUser.objects.create_user(
            username="hlsuser",
            email="hls@test.com",
            password=TEST_PASSWORD,  # nosec  # NOSONAR
        )
        cls.public_stream = Stream.objects.create(name="pub", title="Pub", user=cls.user, public=True)
        cls.private_stream = Stream.objects.create(name="priv", title="Priv", user=cls.user, public=False)
        cls.password_stream = Stream.objects.create(
            name="locked", title="Locked", user=cls.user, public=True, password="hunter2"  # nosec  # NOSONAR
        )

    def _auth(self, **params):
        return self.client.get(reverse("api:stream-hls-auth"), params)

    def test_public_stream_allowed_anonymously(self):
        r = self._auth(name="pub")
        self.assertEqual(r.status_code, 204)

    def test_missing_name_rejected(self):
        r = self._auth()
        self.assertEqual(r.status_code, 403)

    def test_unknown_stream_rejected(self):
        r = self._auth(name="does-not-exist")
        self.assertEqual(r.status_code, 403)

    def test_private_stream_rejects_anonymous(self):
        r = self._auth(name="priv")
        self.assertEqual(r.status_code, 403)

    def test_password_protected_public_stream_rejects_bare_request(self):
        # Public + password must NOT be allowed by the "public" shortcut.
        r = self._auth(name="locked")
        self.assertEqual(r.status_code, 403)

    def test_valid_token_allows_private_stream(self):
        self.private_stream.playback_token = "tok-abc"  # nosec B105
        self.private_stream.save(update_fields=["playback_token"])
        r = self._auth(name="priv", token="tok-abc")  # nosec B106
        self.assertEqual(r.status_code, 204)

    def test_wrong_token_rejected(self):
        self.private_stream.playback_token = "tok-abc"  # nosec B105
        self.private_stream.save(update_fields=["playback_token"])
        r = self._auth(name="priv", token="tok-xyz")  # nosec B106
        self.assertEqual(r.status_code, 403)

    def test_empty_token_does_not_match_disabled_stream(self):
        # private_stream.playback_token defaults to "" — empty must not match empty.
        r = self._auth(name="priv", token="")  # nosec B106
        self.assertEqual(r.status_code, 403)

    def test_valid_cookie_allows_private_stream(self):
        from home.util.nginx import sign_hls_cookie

        sig, exp = sign_hls_cookie("priv")
        r = self._auth(name="priv", sig=sig, exp=str(exp))
        self.assertEqual(r.status_code, 204)

    def test_cookie_for_other_stream_rejected(self):
        from home.util.nginx import sign_hls_cookie

        sig, exp = sign_hls_cookie("pub")
        r = self._auth(name="priv", sig=sig, exp=str(exp))
        self.assertEqual(r.status_code, 403)

    def test_valid_cookie_bypasses_password_gate(self):
        # Cookie issuance at live_view implies the password gate was passed.
        from home.util.nginx import sign_hls_cookie

        sig, exp = sign_hls_cookie("locked")
        r = self._auth(name="locked", sig=sig, exp=str(exp))
        self.assertEqual(r.status_code, 204)


# ---------------------------------------------------------------------------
# Auth endpoint tests
# ---------------------------------------------------------------------------


class BearerTokenAuthTestCase(TestCase):
    """Tests for the hashed-at-rest Bearer token authentication scheme."""

    @classmethod
    def setUpTestData(cls):
        call_command("loaddata", "settings/fixtures/sitesettings.json", verbosity=0)
        cls.user = CustomUser.objects.create_user(
            username="authuser",
            email="auth@test.com",
            password=TEST_PASSWORD,
        )
        cls.token = create_api_token(cls.user, name="Test Token")

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

    @classmethod
    def setUpTestData(cls):
        call_command("loaddata", "settings/fixtures/sitesettings.json", verbosity=0)
        cls.user = CustomUser.objects.create_user(
            username="rotateuser",
            email="rotate@test.com",
            password=TEST_PASSWORD,  # nosec  # NOSONAR
        )
        cls.token = create_api_token(cls.user, name="Test Token")

    def test_create_via_session_returns_new_plaintext(self):
        self.client.login(username="rotateuser", password=TEST_PASSWORD)  # nosec  # NOSONAR
        r = self.client.post(reverse("api:token"), HTTP_X_CSRFTOKEN=self.client.cookies.get("csrftoken", ""))
        self.assertEqual(r.status_code, 200)
        new_token = r.json()["token"]
        self.assertNotEqual(new_token, self.token)
        self.assertEqual(len(new_token), 32)

    def test_create_new_token_does_not_invalidate_old(self):
        self.client.login(username="rotateuser", password=TEST_PASSWORD)  # nosec  # NOSONAR
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
        self.client.login(username="rotateuser", password=TEST_PASSWORD)  # nosec  # NOSONAR
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
        self.client.login(username="rotateuser", password=TEST_PASSWORD)  # nosec  # NOSONAR
        self.client.post(reverse("api:token"))
        self.user.refresh_from_db()
        new_count = ApiToken.objects.filter(user=self.user).count()
        self.assertEqual(new_count, initial_count + 1)


class LocalAuthForNativeClientTestCase(TestCase):
    """Tests for POST /api/auth/token/ — the native-client login endpoint."""

    @classmethod
    def setUpTestData(cls):
        call_command("loaddata", "settings/fixtures/sitesettings.json", verbosity=0)
        cls.user = CustomUser.objects.create_user(
            username="nativeuser",
            email="native@test.com",
            password=TEST_PASSWORD,  # nosec  # NOSONAR
        )

    def setUp(self):
        from django.core.cache import cache as _cache

        # Clear rate-limit counters so each test starts with a clean slate.
        _cache.clear()

    def test_login_with_valid_credentials_returns_token(self):
        r = self.client.post(
            reverse("api:auth-token"),
            data=json.dumps({"username": "nativeuser", "password": TEST_PASSWORD}),  # nosec  # NOSONAR
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
            data=json.dumps({"username": "nativeuser", "password": TEST_PASSWORD}),  # nosec  # NOSONAR
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
            data=json.dumps({"username": "nativeuser", "password": WRONG_PASSWORD}),  # nosec  # NOSONAR
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 401)

    def test_login_token_is_not_the_stored_hash(self):
        """The returned plaintext must differ from what is stored in the DB."""
        r = self.client.post(
            reverse("api:auth-token"),
            data=json.dumps({"username": "nativeuser", "password": TEST_PASSWORD}),  # nosec  # NOSONAR
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
            data=json.dumps({"username": "nativeuser", "password": TEST_PASSWORD}),  # nosec  # NOSONAR
            content_type="application/json",
        )
        first_token = login_r.json()["token"]

        # Second call with same session (Android reAuthenticate pattern).
        r2 = self.client.post(
            reverse("api:auth-token"),
            data=json.dumps({"username": "nativeuser", "password": TEST_PASSWORD}),  # nosec  # NOSONAR
            content_type="application/json",
        )
        # Session already authenticated; returns from session, no rotation.
        second_token = r2.json()["token"]
        self.assertEqual(first_token, second_token)


class AuthSessionTestCase(TestCase):
    """Tests for POST /api/auth/session/ — Bearer token → session cookie exchange."""

    @classmethod
    def setUpTestData(cls):
        call_command("loaddata", "settings/fixtures/sitesettings.json", verbosity=0)
        cls.user = CustomUser.objects.create_user(
            username="sessionuser",
            email="session@test.com",
            password=TEST_PASSWORD,  # nosec  # NOSONAR
        )
        cls.token = create_api_token(cls.user, name="Test Token")

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

    @classmethod
    def setUpTestData(cls):
        call_command("loaddata", "settings/fixtures/sitesettings.json", verbosity=0)
        cls.user = CustomUser.objects.create_user(
            username="logoutuser",
            email="logout@test.com",
            password=TEST_PASSWORD,  # nosec  # NOSONAR
        )
        cls.token = create_api_token(cls.user, name="Test Token")

    def test_token_remains_active_after_logout(self):
        """Logout must leave ApiToken rows untouched."""
        self.client.login(username="logoutuser", password=TEST_PASSWORD)  # nosec  # NOSONAR
        self.client.post(reverse("oauth:logout"))

        token_obj = ApiToken.objects.filter(user=self.user).first()
        self.assertIsNotNone(token_obj)
        self.assertTrue(token_obj.is_active)

    def test_bearer_token_still_works_after_logout(self):
        """A Bearer token must remain valid after its owner logs out of the web session."""
        self.client.login(username="logoutuser", password=TEST_PASSWORD)  # nosec  # NOSONAR
        self.client.post(reverse("oauth:logout"))

        from django.test import Client

        c = Client()
        r = c.get(reverse("api:current-user"), HTTP_AUTHORIZATION=f"Bearer {self.token}")
        self.assertEqual(r.status_code, 200)


class SessionManagementTestCase(TestCase):
    """DELETE /api/session/:id"""

    @classmethod
    def setUpTestData(cls):
        call_command("loaddata", "settings/fixtures/sitesettings.json", verbosity=0)
        cls.user_a = CustomUser.objects.create_user(
            username="sessionusera",
            email="sessiona@test.com",
            password=TEST_PASSWORD,  # nosec  # NOSONAR
        )
        cls.user_b = CustomUser.objects.create_user(
            username="sessionuserb",
            email="sessionb@test.com",
            password=TEST_PASSWORD,  # nosec  # NOSONAR
        )
        cls.superuser = CustomUser.objects.create_superuser(
            username="sessionadmin",
            email="sessionadmin@test.com",
            password=TEST_PASSWORD,  # nosec  # NOSONAR
        )

    def setUp(self):
        # sessions live in Redis, not the DB, so TestCase's rollback won't clear them
        from django.core.cache import cache

        cache.clear()

    @staticmethod
    def _login(username):
        from django.test import Client

        client = Client()
        client.login(username=username, password=TEST_PASSWORD)  # nosec  # NOSONAR
        return client

    def test_user_can_delete_own_other_session(self):
        primary = self._login("sessionusera")
        other = self._login("sessionusera")
        response = primary.delete(reverse("api:session", kwargs={"sessionid": other.session.session_key}))
        self.assertEqual(response.status_code, 201)
        self.assertEqual(other.get(reverse("api:current-user")).status_code, 401)

    def test_user_cannot_delete_own_current_session_by_id(self):
        primary = self._login("sessionusera")
        response = primary.delete(reverse("api:session", kwargs={"sessionid": primary.session.session_key}))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(primary.get(reverse("api:current-user")).status_code, 200)

    def test_user_cannot_delete_others_session(self):
        client_a = self._login("sessionusera")
        client_b = self._login("sessionuserb")
        response = client_a.delete(reverse("api:session", kwargs={"sessionid": client_b.session.session_key}))
        self.assertEqual(response.status_code, 403)
        self.assertEqual(client_b.get(reverse("api:current-user")).status_code, 200)

    def test_user_all_only_deletes_own_other_sessions(self):
        primary = self._login("sessionusera")
        secondary = self._login("sessionusera")
        other_user = self._login("sessionuserb")
        response = primary.delete(reverse("api:session", kwargs={"sessionid": "all"}))
        self.assertEqual(response.status_code, 201)
        self.assertEqual(secondary.get(reverse("api:current-user")).status_code, 401)
        self.assertEqual(other_user.get(reverse("api:current-user")).status_code, 200)

    def test_superuser_can_delete_any_users_session(self):
        admin = self._login("sessionadmin")
        client_a = self._login("sessionusera")
        response = admin.delete(reverse("api:session", kwargs={"sessionid": client_a.session.session_key}))
        self.assertEqual(response.status_code, 201)
        self.assertEqual(client_a.get(reverse("api:current-user")).status_code, 401)

    def test_superuser_all_deletes_every_other_session_site_wide(self):
        admin = self._login("sessionadmin")
        client_a = self._login("sessionusera")
        client_b = self._login("sessionuserb")
        response = admin.delete(reverse("api:session", kwargs={"sessionid": "all"}))
        self.assertEqual(response.status_code, 201)
        self.assertEqual(client_a.get(reverse("api:current-user")).status_code, 401)
        self.assertEqual(client_b.get(reverse("api:current-user")).status_code, 401)

    def test_delete_nonexistent_session_returns_404(self):
        client_a = self._login("sessionusera")
        response = client_a.delete(reverse("api:session", kwargs={"sessionid": "doesnotexist1234567890"}))
        self.assertEqual(response.status_code, 404)

    def test_unauthenticated_request_rejected(self):
        from django.test import Client

        response = Client().delete(reverse("api:session", kwargs={"sessionid": "all"}))
        self.assertEqual(response.status_code, 302)


class ApiTokenListCreateTestCase(TestCase):
    """GET /api/token/ and POST /api/token/"""

    @classmethod
    def setUpTestData(cls):
        call_command("loaddata", "settings/fixtures/sitesettings.json", verbosity=0)
        cls.user = CustomUser.objects.create_user(username="tokenuser", password=TEST_PASSWORD)  # nosec  # NOSONAR

    def setUp(self):
        self.client.login(username="tokenuser", password=TEST_PASSWORD)  # nosec  # NOSONAR

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
        other = CustomUser.objects.create_user(username="other", password=TEST_PASSWORD)  # nosec  # NOSONAR
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

    @classmethod
    def setUpTestData(cls):
        call_command("loaddata", "settings/fixtures/sitesettings.json", verbosity=0)
        cls.user = CustomUser.objects.create_user(username="deluser", password=TEST_PASSWORD)  # nosec  # NOSONAR
        cls.token = ApiToken.objects.create(user=cls.user, token_hash=hash_token("mytoken"), name="My Token")

    def setUp(self):
        self.client.login(username="deluser", password=TEST_PASSWORD)  # nosec  # NOSONAR

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
        other = CustomUser.objects.create_user(username="other2", password=TEST_PASSWORD)  # nosec  # NOSONAR
        other_token = ApiToken.objects.create(user=other, token_hash=hash_token("othertoken2"), name="Other")
        response = self.client.delete(f"/api/token/{other_token.pk}/")
        self.assertEqual(response.status_code, 404)
        other_token.refresh_from_db()
        self.assertTrue(other_token.is_active)


class ApiTokenAuthTestCase(TestCase):
    """auth_from_token middleware with ApiToken model"""

    @classmethod
    def setUpTestData(cls):
        call_command("loaddata", "settings/fixtures/sitesettings.json", verbosity=0)
        cls.user = CustomUser.objects.create_user(username="authuser", password=TEST_PASSWORD)  # nosec  # NOSONAR
        cls.plaintext = "testbearertoken12345678"
        cls.token = ApiToken.objects.create(
            user=cls.user,
            token_hash=hash_token(cls.plaintext),
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


AUTO_PASSWORD_OPTION = "auto-password"  # nosec  # NOSONAR - option name, not a credential


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class UploadOptionsTestCase(TestCase):
    """Upload options via POST fields (upload page form) and headers."""

    @classmethod
    def setUpTestData(cls):
        call_command("loaddata", "settings/fixtures/sitesettings.json", verbosity=0)
        cls.user = CustomUser.objects.create_user(
            username="uploader",
            email="uploader@test.com",
            password=TEST_PASSWORD,  # nosec  # NOSONAR
        )

    def setUp(self):
        self.client.force_login(self.user)

    def tearDown(self):
        from django.core.cache import cache as _cache

        # get_url() caches signed URLs by pk in Redis, which survives the
        # test transaction and poisons later tests that reuse the same pks.
        _cache.clear()

    def upload(self, headers=None, **post):
        data = {"file": SimpleUploadedFile("upload.txt", b"hello world", content_type="text/plain")}
        data.update(post)
        response = self.client.post(reverse("api:upload"), data, headers=headers or {})
        self.assertEqual(response.status_code, 200)
        return Files.objects.filter(user=self.user).latest("id")

    def test_post_options_applied(self):
        file = self.upload(private="true", embed="false", info="from the form", **{"Expires-At": "1h"})
        self.assertTrue(file.private)
        self.assertFalse(file.meta_preview)
        self.assertEqual(file.info, "from the form")
        self.assertEqual(file.expr, "1h")

    def test_header_options_applied(self):
        file = self.upload(headers={"private": "true", "embed": "false"})
        self.assertTrue(file.private)
        self.assertFalse(file.meta_preview)

    def test_hyphenated_post_options_do_not_crash(self):
        # POST strip-gps/strip-exif previously reached Files(**kwargs) unmapped
        file = self.upload(**{"strip-gps": "false", "strip-exif": "false"})
        self.assertEqual(file.mime, "text/plain")

    def test_text_only_upload(self):
        # text paste with no file key previously 500'd: the quota check
        # dereferenced f.size before the text-to-BytesIO fallback ran
        response = self.client.post(reverse("api:upload"), {"text": "hello paste"})
        self.assertEqual(response.status_code, 200)
        file = Files.objects.filter(user=self.user).latest("id")
        self.assertEqual(file.size, len(b"hello paste"))
        self.assertEqual(file.mime, "text/plain")

    def test_format_uuid_post(self):
        file = self.upload(format="uuid")
        self.assertRegex(file.name, r"^[0-9a-f]{32}\.txt$")

    def test_defaults_apply_when_options_absent(self):
        self.user.default_file_private = True
        self.user.show_exif_preview = False
        self.user.save()
        file = self.upload()
        self.assertTrue(file.private)
        self.assertFalse(file.meta_preview)

    def test_auto_password_true_generates(self):
        file = self.upload(**{AUTO_PASSWORD_OPTION: "true"})
        self.assertTrue(file.password)

    def test_auto_password_false_value_honored(self):
        # a false value must not generate a password (walrus precedence fix)
        file = self.upload(**{AUTO_PASSWORD_OPTION: "false"})
        self.assertEqual(file.password, "")

    def test_auto_password_false_overrides_account_default(self):
        self.user.default_file_password = True
        self.user.save()
        file = self.upload(**{AUTO_PASSWORD_OPTION: "false"})
        self.assertEqual(file.password, "")

    def test_account_default_password_still_generates(self):
        self.user.default_file_password = True
        self.user.save()
        file = self.upload()
        self.assertTrue(file.password)

    def test_explicit_password_survives_account_default(self):
        self.user.default_file_password = True
        self.user.save()
        file = self.upload(password=TEST_PASSWORD)
        self.assertEqual(file.password, TEST_PASSWORD)


class RemoteUploadSecurityTestCase(TestCase):
    """SSRF and scheme guards on /api/remote/"""

    @classmethod
    def setUpTestData(cls):
        call_command("loaddata", "settings/fixtures/sitesettings.json", verbosity=0)
        cls.user = CustomUser.objects.create_user(
            username="remoteuser",
            email="remote@test.com",
            password=TEST_PASSWORD,  # nosec  # NOSONAR
        )

    def setUp(self):
        self.client.force_login(self.user)

    def remote(self, url):
        return self.client.post(reverse("api:remote"), data=json.dumps({"url": url}), content_type="application/json")

    def test_non_public_addresses_rejected(self):
        # loopback, cloud metadata, private ranges — all resolve without DNS
        # so these are deterministic offline
        for url in (
            "http://127.0.0.1/secret.txt",
            "http://169.254.169.254/latest/meta-data/",
            "http://10.0.0.1/file.bin",
            "http://192.168.1.1/file.bin",
        ):
            response = self.remote(url)
            self.assertEqual(response.status_code, 400, url)

    def test_non_http_schemes_rejected(self):
        self.assertIsNotNone(remote_url_error("ftp://example.com/file.bin"))
        self.assertIsNotNone(remote_url_error("file:///etc/passwd"))
        self.assertIsNotNone(remote_url_error("gopher://example.com/1"))

    def test_public_address_allowed(self):
        # 1.1.1.1 is globally routable; the validator must not block it
        self.assertIsNone(remote_url_error("http://1.1.1.1/file.bin"))
