import hashlib
import hmac
import json
import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

from celery.exceptions import Retry
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from djangofiles.test_utils import TEST_PASSWORD
from home.models import Albums, Stream, Webhook
from home.tasks import dispatch_webhook_event, fire_webhook
from home.util.auth import create_api_token
from home.util.file import process_file
from home.util.webhooks import (
    EVENT_FILE_UPLOAD,
    EVENT_TEST,
    EVENT_USER_CREATED,
    SITE_ONLY_EVENTS,
    WEBHOOK_EVENTS,
    build_album_payload,
    build_discord_embed,
    build_file_payload,
    build_stream_payload,
    build_user_payload,
    send_webhook,
)
from oauth.models import CustomUser
from settings.models import SiteSettings

log = logging.getLogger("app")

CUSTOM_URL = "https://example.com/hooks/django-files"
DISCORD_URL = "https://discord.com/api/webhooks/123/abc"


def _mock_response(status_code=200):
    response = MagicMock()
    response.status_code = status_code
    response.is_success = 200 <= status_code < 300
    response.text = ""
    return response


class WebhookBaseTestCase(TestCase):
    def setUp(self):
        call_command("loaddata", "settings/fixtures/sitesettings.json", verbosity=0)
        self.user = CustomUser.objects.create_user(
            username="hookuser",
            email="hook@test.com",
            password=TEST_PASSWORD,  # nosec  # NOSONAR
        )

    def create_webhook(self, **kwargs):
        defaults = {
            "owner": self.user,
            "name": "Test Hook",
            "webhook_type": Webhook.WEBHOOK_TYPE_CUSTOM,
            "url": CUSTOM_URL,
            "events": [EVENT_FILE_UPLOAD],
        }
        defaults.update(kwargs)
        return Webhook.objects.create(**defaults)


class WebhookModelTests(WebhookBaseTestCase):
    def test_create_defaults(self):
        webhook = Webhook.objects.create(owner=self.user, name="Bare", url=CUSTOM_URL)
        self.assertTrue(webhook.active)
        self.assertEqual(webhook.webhook_type, Webhook.WEBHOOK_TYPE_CUSTOM)
        self.assertEqual(webhook.events, [])
        self.assertEqual(webhook.secret, "")

    def test_owner_relation(self):
        webhook = self.create_webhook()
        self.assertIn(webhook, self.user.webhooks.all())

    def test_delete(self):
        webhook = self.create_webhook()
        webhook.delete()
        self.assertFalse(Webhook.objects.filter(pk=webhook.pk).exists())


class PayloadBuilderTests(WebhookBaseTestCase):
    def test_build_file_payload(self):
        with Path("./requirements.txt").open("rb") as f:
            file = process_file("requirements.txt", f, self.user.id)
        payload = build_file_payload(file)
        self.assertEqual(payload["id"], file.id)
        self.assertEqual(payload["name"], file.name)
        self.assertEqual(payload["size"], file.size)
        self.assertEqual(payload["mime"], file.mime)
        self.assertEqual(payload["user"], self.user.username)
        site_url = SiteSettings.objects.settings().site_url
        self.assertTrue(payload["url"].startswith(site_url))
        self.assertTrue(payload["raw_url"].startswith(site_url))

    def test_build_album_payload(self):
        album = Albums.objects.create(user=self.user, name="Test Album")
        payload = build_album_payload(album)
        self.assertEqual(payload["id"], album.id)
        self.assertEqual(payload["name"], "Test Album")
        self.assertEqual(payload["file_count"], 0)
        self.assertEqual(payload["user"], self.user.username)
        self.assertIn(f"album={album.id}", payload["url"])

    def test_build_stream_payload(self):
        stream = Stream.objects.create(
            name="teststream", title="Test", description="A test stream", user=self.user
        )
        payload = build_stream_payload(stream)
        self.assertEqual(payload["name"], "teststream")
        self.assertEqual(payload["title"], "Test")
        self.assertEqual(payload["description"], "A test stream")
        self.assertEqual(payload["user"], self.user.username)
        self.assertIn("/live/teststream/", payload["url"])

    def test_build_discord_embed_stream_description(self):
        data = {"name": "s1", "description": "Movie night", "url": "u", "user": "x"}
        body = build_discord_embed("stream.live", data, "https://example.com")
        self.assertIn("Movie night", body["embeds"][0]["description"])

    def test_build_user_payload(self):
        payload = build_user_payload(self.user)
        self.assertEqual(payload["id"], self.user.id)
        self.assertEqual(payload["username"], self.user.username)
        self.assertEqual(payload["email"], self.user.email)
        self.assertEqual(payload["date_joined"], self.user.date_joined.isoformat())

    def test_build_discord_embed(self):
        data = build_user_payload(self.user)
        body = build_discord_embed(EVENT_USER_CREATED, data, "https://example.com")
        self.assertEqual(len(body["embeds"]), 1)
        embed = body["embeds"][0]
        self.assertEqual(embed["title"], "User Created")
        self.assertIn(self.user.username, embed["description"])
        site_title = SiteSettings.objects.settings().site_title
        self.assertEqual(body["username"], site_title)
        self.assertEqual(embed["footer"], {"text": f"django-files • {site_title}"})

    def test_build_discord_embed_file_media(self):
        image_data = {"name": "a.jpg", "mime": "image/jpeg", "size": 1, "url": "u", "raw_url": "https://x/raw/a.jpg"}
        body = build_discord_embed(EVENT_FILE_UPLOAD, image_data, "https://example.com")
        self.assertEqual(body["embeds"][0]["image"], {"url": "https://x/raw/a.jpg"})
        self.assertNotIn("content", body)
        video_data = {"name": "b.mp4", "mime": "video/mp4", "size": 1, "url": "u", "raw_url": "https://x/raw/b.mp4"}
        body = build_discord_embed(EVENT_FILE_UPLOAD, video_data, "https://example.com")
        self.assertEqual(body["content"], "https://x/raw/b.mp4")
        self.assertNotIn("image", body["embeds"][0])


class SendWebhookTests(WebhookBaseTestCase):
    @patch("home.util.webhooks.httpx.post")
    def test_custom_payload_and_signature(self, mock_post):
        mock_post.return_value = _mock_response()
        webhook = self.create_webhook(secret="topsecret")  # nosec  # NOSONAR
        data = {"id": 1, "name": "file.txt"}
        response = send_webhook(webhook, EVENT_FILE_UPLOAD, data)
        self.assertTrue(response.is_success)
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], CUSTOM_URL)
        body = kwargs["content"]
        payload = json.loads(body)
        self.assertEqual(payload["event"], EVENT_FILE_UPLOAD)
        self.assertEqual(payload["data"], data)
        self.assertIn("timestamp", payload)
        self.assertEqual(payload["site_url"], SiteSettings.objects.settings().site_url)
        headers = kwargs["headers"]
        self.assertEqual(headers["X-Webhook-Event"], EVENT_FILE_UPLOAD)
        expected = "sha256=" + hmac.new(b"topsecret", body, hashlib.sha256).hexdigest()
        self.assertEqual(headers["X-Webhook-Signature"], expected)

    @patch("home.util.webhooks.httpx.post")
    def test_custom_no_secret_no_signature(self, mock_post):
        mock_post.return_value = _mock_response()
        webhook = self.create_webhook()
        send_webhook(webhook, EVENT_FILE_UPLOAD, {})
        headers = mock_post.call_args.kwargs["headers"]
        self.assertNotIn("X-Webhook-Signature", headers)

    @patch("home.util.webhooks.httpx.post")
    def test_discord_sends_embed(self, mock_post):
        mock_post.return_value = _mock_response()
        webhook = self.create_webhook(webhook_type=Webhook.WEBHOOK_TYPE_DISCORD, url=DISCORD_URL)
        send_webhook(webhook, EVENT_TEST, {"id": 1, "name": "Test Hook", "user": "hookuser"})
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], DISCORD_URL)
        self.assertIn("embeds", kwargs["json"])


class WebhookTaskTests(WebhookBaseTestCase):
    @patch("home.tasks.fire_webhook.delay")
    def test_dispatch_fires_subscribed(self, mock_delay):
        webhook = self.create_webhook()
        dispatch_webhook_event(EVENT_FILE_UPLOAD, self.user.pk, {"id": 1})
        mock_delay.assert_called_once_with(webhook.pk, EVENT_FILE_UPLOAD, {"id": 1})

    @patch("home.tasks.fire_webhook.delay")
    def test_dispatch_skips_unsubscribed(self, mock_delay):
        self.create_webhook(events=["album.created"])
        dispatch_webhook_event(EVENT_FILE_UPLOAD, self.user.pk, {})
        mock_delay.assert_not_called()

    @patch("home.tasks.fire_webhook.delay")
    def test_dispatch_skips_inactive(self, mock_delay):
        self.create_webhook(active=False)
        dispatch_webhook_event(EVENT_FILE_UPLOAD, self.user.pk, {})
        mock_delay.assert_not_called()

    def _create_staff_user(self):
        return CustomUser.objects.create_user(
            username="staffuser",
            email="staff@test.com",
            password=TEST_PASSWORD,  # nosec  # NOSONAR
            is_staff=True,
        )

    @patch("home.tasks.fire_webhook.delay")
    def test_dispatch_site_only_event_requires_site_scope(self, mock_delay):
        # user-scoped hooks never receive site-only events, even when subscribed
        self.create_webhook(events=[EVENT_USER_CREATED])
        staff = self._create_staff_user()
        mock_delay.reset_mock()
        site_hook = Webhook.objects.create(
            owner=staff,
            name="Site Hook",
            url=CUSTOM_URL,
            scope=Webhook.SCOPE_SITE,
            events=[EVENT_USER_CREATED],
        )
        dispatch_webhook_event(EVENT_USER_CREATED, None, {"id": 1})
        mock_delay.assert_called_once_with(site_hook.pk, EVENT_USER_CREATED, {"id": 1})

    @patch("home.tasks.fire_webhook.delay")
    def test_dispatch_site_scope_receives_all_users_events(self, mock_delay):
        staff = self._create_staff_user()
        mock_delay.reset_mock()
        site_hook = Webhook.objects.create(
            owner=staff,
            name="Site Hook",
            url=CUSTOM_URL,
            scope=Webhook.SCOPE_SITE,
            events=[EVENT_FILE_UPLOAD],
        )
        # event owner is self.user, not the hook owner
        dispatch_webhook_event(EVENT_FILE_UPLOAD, self.user.pk, {"id": 1})
        mock_delay.assert_called_once_with(site_hook.pk, EVENT_FILE_UPLOAD, {"id": 1})

    @patch("home.tasks.fire_webhook.delay")
    def test_dispatch_user_scope_skips_other_users_events(self, mock_delay):
        staff = self._create_staff_user()
        Webhook.objects.create(owner=staff, name="Staff User Hook", url=CUSTOM_URL, events=[EVENT_FILE_UPLOAD])
        mock_delay.reset_mock()
        dispatch_webhook_event(EVENT_FILE_UPLOAD, self.user.pk, {"id": 1})
        mock_delay.assert_not_called()

    @patch("home.tasks.send_webhook")
    def test_fire_webhook_success(self, mock_send):
        mock_send.return_value = _mock_response()
        webhook = self.create_webhook()
        result = fire_webhook(webhook.pk, EVENT_FILE_UPLOAD, {})
        self.assertEqual(result, 200)

    @patch("home.tasks.send_webhook")
    def test_fire_webhook_discord_404_deletes(self, mock_send):
        mock_send.return_value = _mock_response(404)
        webhook = self.create_webhook(webhook_type=Webhook.WEBHOOK_TYPE_DISCORD, url=DISCORD_URL)
        fire_webhook(webhook.pk, EVENT_FILE_UPLOAD, {})
        self.assertFalse(Webhook.objects.filter(pk=webhook.pk).exists())

    @patch("home.tasks.send_webhook")
    def test_fire_webhook_5xx_retries(self, mock_send):
        mock_send.return_value = _mock_response(500)
        webhook = self.create_webhook()
        with self.assertRaises(Retry):
            fire_webhook(webhook.pk, EVENT_FILE_UPLOAD, {})

    @patch("home.tasks.send_webhook")
    def test_fire_webhook_custom_deactivated_after_max_retries(self, mock_send):
        mock_send.return_value = _mock_response(400)
        webhook = self.create_webhook()
        with patch.object(fire_webhook, "max_retries", 0):
            result = fire_webhook(webhook.pk, EVENT_FILE_UPLOAD, {})
        self.assertEqual(result, 400)
        webhook.refresh_from_db()
        self.assertFalse(webhook.active)

    @patch("home.tasks.send_webhook")
    def test_fire_webhook_missing_returns(self, mock_send):
        result = fire_webhook(999999, EVENT_FILE_UPLOAD, {})
        self.assertIsNone(result)
        mock_send.assert_not_called()


class WebhookApiTests(WebhookBaseTestCase):
    def setUp(self):
        super().setUp()
        self.token = create_api_token(self.user, name="Test Token")
        self.other_user = CustomUser.objects.create_user(
            username="otheruser",
            email="other@test.com",
            password=TEST_PASSWORD,  # nosec  # NOSONAR
        )
        self.other_token = create_api_token(self.other_user, name="Test Token")
        self.superuser = CustomUser.objects.create_superuser(
            username="superuser",
            email="super@test.com",
            password=TEST_PASSWORD,  # nosec  # NOSONAR
        )
        self.superuser_token = create_api_token(self.superuser, name="Test Token")

    def _auth(self, token):
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def test_list_requires_auth(self):
        response = self.client.get(reverse("api:webhooks"))
        self.assertEqual(response.status_code, 401)

    def test_create_and_list(self):
        body = {"name": "Mine", "url": CUSTOM_URL, "events": [EVENT_FILE_UPLOAD]}
        response = self.client.post(
            reverse("api:webhooks"), json.dumps(body), content_type="application/json", **self._auth(self.token)
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["name"], "Mine")
        self.assertEqual(data["events"], [EVENT_FILE_UPLOAD])
        response = self.client.get(reverse("api:webhooks"), **self._auth(self.token))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["webhooks"]), 1)
        # other users do not see it
        response = self.client.get(reverse("api:webhooks"), **self._auth(self.other_token))
        self.assertEqual(len(response.json()["webhooks"]), 0)

    def test_create_validation(self):
        auth = self._auth(self.token)
        url = reverse("api:webhooks")
        cases = [
            {"url": CUSTOM_URL},  # missing name
            {"name": "X"},  # missing url
            {"name": "X", "url": "not-a-url"},
            {"name": "X", "url": CUSTOM_URL, "events": ["bogus.event"]},
            {"name": "X", "url": CUSTOM_URL, "webhook_type": "bogus"},
        ]
        for body in cases:
            response = self.client.post(url, json.dumps(body), content_type="application/json", **auth)
            self.assertEqual(response.status_code, 400, body)

    def test_detail_ownership(self):
        webhook = self.create_webhook()
        url = reverse("api:webhook-detail", kwargs={"webhook_id": webhook.pk})
        self.assertEqual(self.client.get(url, **self._auth(self.token)).status_code, 200)
        self.assertEqual(self.client.get(url, **self._auth(self.other_token)).status_code, 404)
        self.assertEqual(self.client.get(url, **self._auth(self.superuser_token)).status_code, 200)

    def test_patch(self):
        webhook = self.create_webhook()
        url = reverse("api:webhook-detail", kwargs={"webhook_id": webhook.pk})
        user_events = [event for event in WEBHOOK_EVENTS if event not in SITE_ONLY_EVENTS]
        body = {"name": "Renamed", "events": user_events, "active": False}
        response = self.client.patch(url, json.dumps(body), content_type="application/json", **self._auth(self.token))
        self.assertEqual(response.status_code, 200)
        webhook.refresh_from_db()
        self.assertEqual(webhook.name, "Renamed")
        self.assertEqual(webhook.events, user_events)
        self.assertFalse(webhook.active)

    def test_patch_invalid(self):
        webhook = self.create_webhook()
        url = reverse("api:webhook-detail", kwargs={"webhook_id": webhook.pk})
        response = self.client.patch(
            url, json.dumps({"url": "bogus"}), content_type="application/json", **self._auth(self.token)
        )
        self.assertEqual(response.status_code, 400)

    def test_delete(self):
        webhook = self.create_webhook()
        url = reverse("api:webhook-detail", kwargs={"webhook_id": webhook.pk})
        response = self.client.delete(url, **self._auth(self.token))
        self.assertEqual(response.status_code, 204)
        self.assertFalse(Webhook.objects.filter(pk=webhook.pk).exists())

    @patch("api.views.send_webhook")
    def test_test_fire(self, mock_send):
        mock_send.return_value = _mock_response()
        webhook = self.create_webhook()
        url = reverse("api:webhook-test", kwargs={"webhook_id": webhook.pk})
        response = self.client.post(url, **self._auth(self.token))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"success": True, "status_code": 200})
        args, _ = mock_send.call_args
        self.assertEqual(args[0], webhook)
        self.assertEqual(args[1], EVENT_TEST)

    def test_create_site_scope_requires_superuser(self):
        body = {"name": "Site", "url": CUSTOM_URL, "scope": "site"}
        response = self.client.post(
            reverse("api:webhooks"), json.dumps(body), content_type="application/json", **self._auth(self.token)
        )
        self.assertEqual(response.status_code, 400)
        response = self.client.post(
            reverse("api:webhooks"),
            json.dumps(body),
            content_type="application/json",
            **self._auth(self.superuser_token),
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["scope"], "site")

    def test_user_scope_rejects_site_only_events(self):
        body = {"name": "X", "url": CUSTOM_URL, "events": ["user.created"]}
        response = self.client.post(
            reverse("api:webhooks"),
            json.dumps(body),
            content_type="application/json",
            **self._auth(self.superuser_token),
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("site scope", response.json()["error"])

    def test_patch_cannot_drop_scope_with_site_only_events(self):
        webhook = Webhook.objects.create(
            owner=self.superuser,
            name="Site Hook",
            url=CUSTOM_URL,
            scope=Webhook.SCOPE_SITE,
            events=["user.created"],
        )
        url = reverse("api:webhook-detail", kwargs={"webhook_id": webhook.pk})
        response = self.client.patch(
            url, json.dumps({"scope": "user"}), content_type="application/json", **self._auth(self.superuser_token)
        )
        self.assertEqual(response.status_code, 400)
        response = self.client.patch(
            url,
            json.dumps({"scope": "user", "events": [EVENT_FILE_UPLOAD]}),
            content_type="application/json",
            **self._auth(self.superuser_token),
        )
        self.assertEqual(response.status_code, 200)
        webhook.refresh_from_db()
        self.assertEqual(webhook.scope, Webhook.SCOPE_USER)

    @patch("api.views.send_webhook")
    def test_test_fire_not_owner(self, mock_send):
        webhook = self.create_webhook()
        url = reverse("api:webhook-test", kwargs={"webhook_id": webhook.pk})
        response = self.client.post(url, **self._auth(self.other_token))
        self.assertEqual(response.status_code, 404)
        mock_send.assert_not_called()


class PendingDiscordWebhookTests(WebhookBaseTestCase):
    """The Discord OAuth flow stages a webhook in the session; the settings page
    hands it to the modal exactly once so the user can finish setup."""

    PENDING = {"hook_id": "123", "name": "my-channel-hook", "url": DISCORD_URL}

    def test_settings_page_stages_pending_webhook_once(self):
        self.client.force_login(self.user)
        session = self.client.session
        session["pending_discord_webhook"] = self.PENDING
        session.save()
        response = self.client.get(reverse("settings:user"))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn("pending-webhook-data", html)
        self.assertIn("my-channel-hook", html)
        self.assertNotIn("pending_discord_webhook", self.client.session)
        # a reload no longer offers the staged webhook
        response = self.client.get(reverse("settings:user"))
        self.assertNotIn("pending-webhook-data", response.content.decode())

    def test_settings_page_without_pending_webhook(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("settings:user"))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("pending-webhook-data", response.content.decode())

    def _stage(self, scope):
        session = self.client.session
        session["pending_discord_webhook"] = {**self.PENDING, "scope": scope}
        session.save()

    def test_site_scoped_pending_lands_on_site_page_only(self):
        superuser = CustomUser.objects.create_superuser(
            username="superadmin",
            email="admin@test.com",
            password=TEST_PASSWORD,  # nosec  # NOSONAR
        )
        self.client.force_login(superuser)
        self._stage("site")
        # the user page must not consume a site-scoped staged webhook
        html = self.client.get(reverse("settings:user")).content.decode()
        self.assertNotIn("pending-webhook-data", html)
        self.assertIn("pending_discord_webhook", self.client.session)
        html = self.client.get(reverse("settings:site")).content.decode()
        self.assertIn("pending-webhook-data", html)
        self.assertNotIn("pending_discord_webhook", self.client.session)

    def test_user_scoped_pending_skips_site_page(self):
        superuser = CustomUser.objects.create_superuser(
            username="superadmin",
            email="admin@test.com",
            password=TEST_PASSWORD,  # nosec  # NOSONAR
        )
        self.client.force_login(superuser)
        self._stage("user")
        html = self.client.get(reverse("settings:site")).content.decode()
        self.assertNotIn("pending-webhook-data", html)
        html = self.client.get(reverse("settings:user")).content.decode()
        self.assertIn("pending-webhook-data", html)

    def test_oauth_webhook_scope_session(self):
        self.client.force_login(self.user)
        self.client.get(reverse("oauth:webhook") + "?scope=site")
        self.assertEqual(self.client.session.get("webhook_scope"), "user")
        superuser = CustomUser.objects.create_superuser(
            username="superadmin",
            email="admin@test.com",
            password=TEST_PASSWORD,  # nosec  # NOSONAR
        )
        self.client.force_login(superuser)
        self.client.get(reverse("oauth:webhook") + "?scope=site")
        self.assertEqual(self.client.session.get("webhook_scope"), "site")


class WebhookSettingsPagesTests(WebhookBaseTestCase):
    """User settings manages user-scoped hooks; site settings manages site-scoped hooks."""

    def setUp(self):
        super().setUp()
        self.superuser = CustomUser.objects.create_superuser(
            username="superuser",
            email="super@test.com",
            password=TEST_PASSWORD,  # nosec  # NOSONAR
        )
        self.site_hook = Webhook.objects.create(
            owner=self.superuser,
            name="SiteWideHook",
            url=CUSTOM_URL,
            scope=Webhook.SCOPE_SITE,
            events=[EVENT_USER_CREATED],
        )

    def test_user_page_shows_only_user_scoped_hooks(self):
        user_hook = self.create_webhook(name="MyUserHook")
        self.client.force_login(self.superuser)
        html = self.client.get(reverse("settings:user")).content.decode()
        self.assertNotIn("SiteWideHook", html)
        self.assertIn('id="webhook-scope" name="scope" value="user"', html)
        # site-only events are not offered on the user page
        self.assertNotIn(f'value="{EVENT_USER_CREATED}"', html)
        self.client.force_login(self.user)
        html = self.client.get(reverse("settings:user")).content.decode()
        self.assertIn(user_hook.name, html)

    def test_site_page_shows_site_scoped_hooks(self):
        self.create_webhook(name="MyUserHook")
        self.client.force_login(self.superuser)
        html = self.client.get(reverse("settings:site")).content.decode()
        self.assertIn("SiteWideHook", html)
        self.assertNotIn("MyUserHook", html)
        self.assertIn('id="webhook-scope" name="scope" value="site"', html)
        self.assertIn(f'value="{EVENT_USER_CREATED}"', html)

    def test_site_page_requires_superuser(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("settings:site"))
        self.assertEqual(response.status_code, 401)
