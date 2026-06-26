import json
import logging

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from oauth import passkeys
from oauth.models import CustomUser, PasskeyCredential
from settings.models import SiteSettings

log = logging.getLogger("app")


class PasskeyConfigTest(TestCase):
    """RP derivation from SiteSettings.site_url."""

    def setUp(self):
        call_command("loaddata", "settings/fixtures/sitesettings.json", verbosity=0)

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

    def setUp(self):
        call_command("loaddata", "settings/fixtures/sitesettings.json", verbosity=0)
        site = SiteSettings.objects.settings()
        site.site_url = "https://example.com"
        site.passkey_auth = True
        site.save()
        self.user = CustomUser.objects.create_user(
            username="passkeyuser",
            email="passkey@test.com",
            password="12345",  # nosec  # NOSONAR
        )

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
            password="12345",  # nosec  # NOSONAR
        )
        cred = PasskeyCredential.objects.create(user=other, credential_id="xyz", public_key="pk")
        self._login()
        response = self.client.post(reverse("oauth:passkey-delete", kwargs={"pk": cred.pk}))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(PasskeyCredential.objects.filter(pk=cred.pk).exists())
