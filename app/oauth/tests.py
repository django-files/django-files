import json
import logging
import types

from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from djangofiles.test_utils import TEST_PASSWORD, WEAK_PASSWORD, WRONG_PASSWORD
from oauth import passkeys
from oauth.models import CustomUser, Discord, PasskeyCredential, UserInvites
from oauth.providers.helpers import create_oauth_user, get_or_create_user
from settings.managers import CACHE_KEY as SITE_SETTINGS_CACHE_KEY
from settings.models import SiteSettings

log = logging.getLogger("app")


class PasskeyConfigTest(TestCase):
    """RP derivation from SiteSettings.site_url."""

    @classmethod
    def setUpTestData(cls):
        call_command("loaddata", "settings/fixtures/sitesettings.json", verbosity=0)

    def setUp(self):
        # SiteSettings.objects.settings() caches in Redis, which survives the
        # per-test DB rollback; tests here mutate and save the singleton, so
        # clear the cache each test to avoid reading a previous test's value.
        cache.delete(SITE_SETTINGS_CACHE_KEY)

    def test_get_rp_from_site_url(self):
        site = SiteSettings.objects.settings()
        site.site_url = "https://files.example.com"
        site.site_title = "My Files"
        site.save()
        rp_id, rp_name, origin = passkeys.get_rp(site)
        self.assertEqual(rp_id, "files.example.com")
        self.assertEqual(rp_name, "My Files")
        self.assertEqual(origin, "https://files.example.com")

    def test_get_rp_requires_site_url(self):
        site = SiteSettings.objects.settings()
        site.site_url = ""
        site.save()
        with self.assertRaises(passkeys.PasskeyConfigError):
            passkeys.get_rp(site)


class PasskeyViewTest(TestCase):
    """Passkey registration/authentication endpoints."""

    @classmethod
    def setUpTestData(cls):
        call_command("loaddata", "settings/fixtures/sitesettings.json", verbosity=0)
        site = SiteSettings.objects.settings()
        site.site_url = "https://example.com"
        site.passkey_auth = True
        site.save()
        cls.user = CustomUser.objects.create_user(
            username="passkeyuser",
            email="passkey@test.com",
            password=TEST_PASSWORD,  # nosec  # NOSONAR
        )

    def setUp(self):
        # SiteSettings.objects.settings() caches in Redis, which survives the
        # per-test DB rollback; tests here mutate and save the singleton, so
        # clear the cache each test to avoid reading a previous test's value.
        cache.delete(SITE_SETTINGS_CACHE_KEY)

    def _login(self):
        self.client.force_login(self.user)

    def test_register_begin_requires_auth(self):
        response = self.client.post(reverse("oauth:passkey-register-begin"))
        self.assertEqual(response.status_code, 302)

    def test_register_begin_returns_options(self):
        self._login()
        response = self.client.post(reverse("oauth:passkey-register-begin"))
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIn("challenge", data)
        self.assertEqual(data["rp"]["id"], "example.com")
        self.assertIn(passkeys.REG_CHALLENGE_KEY, self.client.session)

    def test_auth_begin_returns_options(self):
        response = self.client.post(reverse("oauth:passkey-auth-begin"))
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIn("challenge", data)
        self.assertIn(passkeys.AUTH_CHALLENGE_KEY, self.client.session)

    def test_auth_complete_unknown_credential(self):
        response = self.client.post(
            reverse("oauth:passkey-auth-complete"),
            data=json.dumps({"id": "does-not-exist"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)

    def test_auth_complete_rejects_inactive_user(self):
        self.user.is_active = False
        self.user.save()
        PasskeyCredential.objects.create(user=self.user, credential_id="inactive-cred", public_key="pk")
        response = self.client.post(
            reverse("oauth:passkey-auth-complete"),
            data=json.dumps({"id": "inactive-cred"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)

    def test_endpoints_gated_when_disabled(self):
        site = SiteSettings.objects.settings()
        site.passkey_auth = False
        site.save()
        self._login()
        for name in ("oauth:passkey-register-begin", "oauth:passkey-auth-begin"):
            response = self.client.post(reverse(name))
            self.assertEqual(response.status_code, 400, name)

    def test_list_and_delete(self):
        self._login()
        cred = PasskeyCredential.objects.create(
            user=self.user,
            credential_id="abc123",
            public_key="pk",
            name="Test Key",
        )
        response = self.client.get(reverse("oauth:passkey-list"))
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(len(data["passkeys"]), 1)
        self.assertEqual(data["passkeys"][0]["name"], "Test Key")

        response = self.client.post(reverse("oauth:passkey-delete", kwargs={"pk": cred.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(PasskeyCredential.objects.filter(pk=cred.pk).exists())

    def test_cannot_delete_other_users_passkey(self):
        other = CustomUser.objects.create_user(
            username="other",
            email="other@test.com",
            password=TEST_PASSWORD,  # nosec  # NOSONAR
        )
        cred = PasskeyCredential.objects.create(user=other, credential_id="xyz", public_key="pk")
        self._login()
        response = self.client.post(reverse("oauth:passkey-delete", kwargs={"pk": cred.pk}))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(PasskeyCredential.objects.filter(pk=cred.pk).exists())


class PasskeyInviteTest(TestCase):
    """Passkey account creation via the invite flow."""

    @classmethod
    def setUpTestData(cls):
        call_command("loaddata", "settings/fixtures/sitesettings.json", verbosity=0)
        site = SiteSettings.objects.settings()
        site.site_url = "https://example.com"
        site.passkey_auth = True
        site.save()
        cls.owner = CustomUser.objects.create_superuser(
            username="owner",
            email="owner@test.com",
            password=TEST_PASSWORD,  # nosec  # NOSONAR
        )
        cls.invite = UserInvites.objects.create(owner=cls.owner, max_uses=1)

    def setUp(self):
        # SiteSettings.objects.settings() caches in Redis, which survives the
        # per-test DB rollback; tests here mutate and save the singleton, so
        # clear the cache each test to avoid reading a previous test's value.
        cache.delete(SITE_SETTINGS_CACHE_KEY)

    def _begin_url(self, code):
        return reverse("oauth:passkey-invite-begin", kwargs={"invite": code})

    def _post(self, url, payload):
        return self.client.post(url, data=json.dumps(payload), content_type="application/json")

    def test_begin_returns_options(self):
        response = self._post(self._begin_url(self.invite.invite), {"username": "newuser"})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIn("challenge", data)
        self.assertEqual(data["rp"]["id"], "example.com")
        self.assertEqual(self.client.session["passkey_invite_username"], "newuser")

    def test_begin_invalid_invite(self):
        response = self._post(self._begin_url("nope"), {"username": "newuser"})
        self.assertEqual(response.status_code, 400)

    def test_begin_requires_username(self):
        response = self._post(self._begin_url(self.invite.invite), {})
        self.assertEqual(response.status_code, 400)

    def test_begin_username_taken(self):
        CustomUser.objects.create_user(username="taken", password=TEST_PASSWORD)  # nosec  # NOSONAR
        response = self._post(self._begin_url(self.invite.invite), {"username": "taken"})
        self.assertEqual(response.status_code, 400)

    def test_complete_without_session(self):
        url = reverse("oauth:passkey-invite-complete", kwargs={"invite": self.invite.invite})
        response = self._post(url, {"id": "x"})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(CustomUser.objects.filter(username="newuser").exists())

    def test_disabled_when_passkeys_off(self):
        site = SiteSettings.objects.settings()
        site.passkey_auth = False
        site.save()
        response = self._post(self._begin_url(self.invite.invite), {"username": "newuser"})
        self.assertEqual(response.status_code, 400)


class OAuthUserCreationTest(TestCase):
    """get_or_create_user / create_oauth_user: no username-based account adoption."""

    @classmethod
    def setUpTestData(cls):
        call_command("loaddata", "settings/fixtures/sitesettings.json", verbosity=0)
        site = SiteSettings.objects.settings()
        site.oauth_reg = True
        site.save()

    def setUp(self):
        # SiteSettings.objects.settings() caches in Redis, which survives the
        # per-test DB rollback; tests here mutate and save the singleton, so
        # clear the cache each test to avoid reading a previous test's value.
        cache.delete(SITE_SETTINGS_CACHE_KEY)

    @staticmethod
    def _req():
        return types.SimpleNamespace(session={})

    def test_creates_new_user_with_free_username(self):
        req = self._req()
        user = get_or_create_user(req, "discord-1", "alice", "discord")
        self.assertIsNotNone(user)
        self.assertEqual(user.username, "alice")
        self.assertTrue(req.session.get("oauth_new_user"))

    def test_does_not_adopt_logged_in_account(self):
        existing = CustomUser.objects.create_user(username="bob", password=TEST_PASSWORD)  # nosec  # NOSONAR
        existing.last_login = timezone.now()
        existing.save()
        user = get_or_create_user(self._req(), "discord-2", "bob", "discord")
        self.assertIsNotNone(user)
        self.assertNotEqual(user.pk, existing.pk)
        self.assertNotEqual(user.username, "bob")

    def test_does_not_adopt_never_logged_in_account(self):
        # Account-takeover fix: a pre-created, never-logged-in local account must
        # NOT be claimable by a matching OAuth handle.
        existing = CustomUser.objects.create(username="carol")
        self.assertIsNone(existing.last_login)
        user = get_or_create_user(self._req(), "discord-3", "carol", "discord")
        self.assertIsNotNone(user)
        self.assertNotEqual(user.pk, existing.pk)
        self.assertNotEqual(user.username, "carol")

    def test_returns_none_when_registration_disabled(self):
        site = SiteSettings.objects.settings()
        site.oauth_reg = False
        site.save()
        user = get_or_create_user(self._req(), "discord-4", "dave", "discord")
        self.assertIsNone(user)

    def test_existing_by_provider_id_returned(self):
        u = CustomUser.objects.create_user(username="erin", password=TEST_PASSWORD)  # nosec  # NOSONAR
        Discord.objects.create(user=u, id="discord-5")
        user = get_or_create_user(self._req(), "discord-5", "whatever", "discord")
        self.assertEqual(user.pk, u.pk)

    def test_create_oauth_user_suffixes_on_collision(self):
        CustomUser.objects.create_user(username="frank", password=TEST_PASSWORD)  # nosec  # NOSONAR
        user = create_oauth_user("frank", "Frank")
        self.assertIsNotNone(user)
        self.assertNotEqual(user.username, "frank")
        self.assertEqual(user.first_name, "Frank")


class OAuthUsernameViewTest(TestCase):
    """The post-signup username interstitial."""

    @classmethod
    def setUpTestData(cls):
        call_command("loaddata", "settings/fixtures/sitesettings.json", verbosity=0)
        cls.user = CustomUser.objects.create_user(username="auto1234", password=TEST_PASSWORD)  # nosec  # NOSONAR

    def test_requires_login(self):
        response = self.client.get(reverse("oauth:username"))
        self.assertEqual(response.status_code, 302)

    def test_get_renders(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("oauth:username"))
        self.assertEqual(response.status_code, 200)

    def test_post_changes_username_and_display_name(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("oauth:username"), {"username": "chosen", "first_name": "Chosen One", "next": "/"}
        )
        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "chosen")
        self.assertEqual(self.user.first_name, "Chosen One")

    def test_post_rejects_taken_username(self):
        CustomUser.objects.create_user(username="taken", password=TEST_PASSWORD)  # nosec  # NOSONAR
        self.client.force_login(self.user)
        response = self.client.post(reverse("oauth:username"), {"username": "taken", "next": "/"})
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "auto1234")

    def test_skip_keeps_username(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("oauth:username"), {"skip": "1", "username": "ignored", "next": "/"})
        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "auto1234")


class FirstRunSetupTest(TestCase):
    """First-run bootstrap: create the initial admin only while none exists."""

    @classmethod
    def setUpTestData(cls):
        call_command("loaddata", "settings/fixtures/sitesettings.json", verbosity=0)

    def setUp(self):
        # SiteSettings.objects.settings() caches in Redis, which survives the
        # per-test DB rollback; tests here mutate and save the singleton, so
        # clear the cache each test to avoid reading a previous test's value.
        cache.delete(SITE_SETTINGS_CACHE_KEY)

    def test_login_redirects_to_setup_when_no_admin(self):
        response = self.client.get(reverse("oauth:login"))
        self.assertRedirects(response, reverse("settings:welcome"), fetch_redirect_response=False)

    def test_setup_page_renders_when_no_admin(self):
        response = self.client.get(reverse("settings:welcome"))
        self.assertEqual(response.status_code, 200)

    def test_bootstrap_creates_superuser_and_logs_in(self):
        response = self.client.post(
            reverse("settings:welcome"),
            {
                "username": "admin",
                "password": TEST_PASSWORD,
                "confirm_password": TEST_PASSWORD,
                "timezone": "UTC",
                "site_url": "https://files.example.com",
            },
        )
        self.assertRedirects(response, reverse("settings:site"), fetch_redirect_response=False)
        user = CustomUser.objects.get(username="admin")
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_staff)
        self.assertFalse(SiteSettings.objects.settings().show_setup)
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_bootstrap_rejects_password_mismatch(self):
        response = self.client.post(
            reverse("settings:welcome"),
            {"username": "admin", "password": TEST_PASSWORD, "confirm_password": WRONG_PASSWORD, "timezone": "UTC"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(CustomUser.objects.filter(username="admin").exists())

    def test_bootstrap_rejects_weak_password(self):
        # Passes the form's min_length=6 but fails AUTH_PASSWORD_VALIDATORS.
        response = self.client.post(
            reverse("settings:welcome"),
            {
                "username": "admin",
                "password": WEAK_PASSWORD,
                "confirm_password": WEAK_PASSWORD,
                "timezone": "UTC",
            },  # nosec  # NOSONAR
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(CustomUser.objects.filter(username="admin").exists())

    def test_gate_closed_once_admin_exists(self):
        CustomUser.objects.create_superuser(username="root", password=TEST_PASSWORD)
        # Anonymous visitors can no longer reach the bootstrap form...
        response = self.client.get(reverse("settings:welcome"))
        self.assertRedirects(response, reverse("oauth:login"), fetch_redirect_response=False)
        # ...nor mint a second admin through it.
        response = self.client.post(
            reverse("settings:welcome"),
            {"username": "evil", "password": TEST_PASSWORD, "timezone": "UTC"},  # nosec  # NOSONAR
        )
        self.assertRedirects(response, reverse("oauth:login"), fetch_redirect_response=False)
        self.assertFalse(CustomUser.objects.filter(username="evil").exists())

    def test_setup_page_shows_passkey_option_without_site_url(self):
        # Passkey option must appear on first run even though site_url is unset;
        # the RP is derived from the request origin.
        site = SiteSettings.objects.settings()
        site.site_url = ""
        site.passkey_auth = True
        site.save()
        response = self.client.get(reverse("settings:welcome"))
        self.assertContains(response, "Use Passkey")
        self.assertContains(response, "passkey-setup.js")


class PasskeySetupTest(TestCase):
    """First-run passkey registration for the initial admin."""

    @classmethod
    def setUpTestData(cls):
        call_command("loaddata", "settings/fixtures/sitesettings.json", verbosity=0)
        # No site_url: first-run setup derives the RP from the request origin.
        site = SiteSettings.objects.settings()
        site.site_url = ""
        site.passkey_auth = True
        site.save()

    def setUp(self):
        # SiteSettings.objects.settings() caches in Redis, which survives the
        # per-test DB rollback; tests here mutate and save the singleton, so
        # clear the cache each test to avoid reading a previous test's value.
        cache.delete(SITE_SETTINGS_CACHE_KEY)

    def test_begin_returns_options(self):
        response = self.client.post(
            reverse("oauth:passkey-setup-begin"),
            data=json.dumps({"username": "admin", "timezone": "UTC"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIn("challenge", data)
        # RP id comes from the request host (Django test client uses "testserver").
        self.assertEqual(data["rp"]["id"], "testserver")
        self.assertEqual(self.client.session["passkey_setup_username"], "admin")

    def test_begin_preserves_browser_port(self):
        # A proxy may hide the port from the server, so the browser-supplied
        # origin (matching host, custom port) is trusted for the RP origin.
        response = self.client.post(
            reverse("oauth:passkey-setup-begin"),
            data=json.dumps({"username": "admin", "origin": "http://testserver:9000"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.session["passkey_setup_origin"], "http://testserver:9000")
        self.assertEqual(json.loads(response.content)["rp"]["id"], "testserver")

    def test_begin_ignores_foreign_origin(self):
        response = self.client.post(
            reverse("oauth:passkey-setup-begin"),
            data=json.dumps({"username": "admin", "origin": "http://evil.example.com"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        # Foreign host rejected; falls back to the request host.
        self.assertEqual(self.client.session["passkey_setup_origin"], "http://testserver")

    def test_begin_requires_username(self):
        response = self.client.post(
            reverse("oauth:passkey-setup-begin"),
            data=json.dumps({}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_begin_gated_when_admin_exists(self):
        CustomUser.objects.create_superuser(username="root", password=TEST_PASSWORD)
        response = self.client.post(
            reverse("oauth:passkey-setup-begin"),
            data=json.dumps({"username": "admin"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(CustomUser.objects.filter(username="admin").exists())

    def test_complete_without_session(self):
        response = self.client.post(
            reverse("oauth:passkey-setup-complete"),
            data=json.dumps({"id": "x"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(CustomUser.objects.filter(is_superuser=True).exists())

    def test_disabled_when_passkeys_off(self):
        site = SiteSettings.objects.settings()
        site.passkey_auth = False
        site.save()
        response = self.client.post(
            reverse("oauth:passkey-setup-begin"),
            data=json.dumps({"username": "admin"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
