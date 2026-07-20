import json
import os
import tempfile
import time
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from djangofiles.test_utils import TEST_PASSWORD
from home.models import Files
from home.tasks import cleanup_tus_uploads, import_tus_upload
from home.util.auth import create_api_token
from home.util.tus import has_disk_space
from oauth.models import CustomUser


def hook_payload(hook_type, *, size=1024, metadata=None, headers=None, storage=None, size_is_deferred=False):
    """Build a tusd v2 HTTP hook request body."""
    return {
        "Type": hook_type,
        "Event": {
            "Upload": {
                "ID": "abc123",
                "Size": size,
                "SizeIsDeferred": size_is_deferred,
                "Offset": 0,
                "MetaData": metadata or {},
                "Storage": storage,
            },
            "HTTPRequest": {
                "Method": "POST",
                "URI": "/tus/",
                "Header": headers or {},
            },
        },
    }


TEST_HOOK_SECRET = "tus-test-hook-secret"  # nosec  # NOSONAR


@override_settings(TUS_ENABLED=True, TUS_HOOK_SECRET=TEST_HOOK_SECRET)
class TusHookTestCase(TestCase):
    """Test POST /api/tus/hook/ (tusd pre-create / post-finish events)"""

    @classmethod
    def setUpTestData(cls):
        call_command("loaddata", "settings/fixtures/sitesettings.json", verbosity=0)
        cls.user = CustomUser.objects.create_user(
            username="tususer",
            email="tus@test.com",
            password=TEST_PASSWORD,  # nosec  # NOSONAR
        )
        cls.token = create_api_token(cls.user, name="Tus Token")

    def hook(self, payload, secret=TEST_HOOK_SECRET):
        url = reverse("api:tus-hook")
        if secret is not None:
            url += f"?secret={secret}"
        return self.client.post(url, data=json.dumps(payload), content_type="application/json")

    def assertRejected(self, response, status):
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get("RejectUpload"))
        self.assertEqual(data["HTTPResponse"]["StatusCode"], status)

    def test_pre_create_bearer_token(self):
        payload = hook_payload("pre-create", headers={"Authorization": [f"Bearer {self.token}"]})
        response = self.hook(payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data.get("RejectUpload"))
        self.assertEqual(data["ChangeFileInfo"]["MetaData"]["user_id"], str(self.user.id))

    def test_pre_create_metadata_token(self):
        payload = hook_payload("pre-create", metadata={"authorization": self.token})
        response = self.hook(payload)
        self.assertEqual(response.json()["ChangeFileInfo"]["MetaData"]["user_id"], str(self.user.id))

    def test_pre_create_invalid_token(self):
        payload = hook_payload("pre-create", headers={"Authorization": ["Bearer wrongtoken"]})
        self.assertRejected(self.hook(payload), 401)

    def test_pre_create_no_auth(self):
        self.assertRejected(self.hook(hook_payload("pre-create")), 401)

    def test_pre_create_session_cookie_with_origin(self):
        self.client.login(username="tususer", password=TEST_PASSWORD)
        session_key = self.client.session.session_key
        payload = hook_payload(
            "pre-create",
            headers={"Cookie": [f"sessionid={session_key}"], "Origin": ["https://example.com"]},
        )
        response = self.hook(payload)
        self.assertEqual(response.json()["ChangeFileInfo"]["MetaData"]["user_id"], str(self.user.id))

    def test_pre_create_session_cookie_without_origin(self):
        """Cookie auth without an Origin/Referer must be rejected (CSRF)."""
        self.client.login(username="tususer", password=TEST_PASSWORD)
        session_key = self.client.session.session_key
        payload = hook_payload("pre-create", headers={"Cookie": [f"sessionid={session_key}"]})
        self.assertRejected(self.hook(payload), 401)

    def test_pre_create_session_cookie_foreign_origin(self):
        self.client.login(username="tususer", password=TEST_PASSWORD)
        session_key = self.client.session.session_key
        payload = hook_payload(
            "pre-create",
            headers={"Cookie": [f"sessionid={session_key}"], "Origin": ["https://evil.example.net"]},
        )
        self.assertRejected(self.hook(payload), 401)

    def test_pre_create_deferred_length(self):
        payload = hook_payload(
            "pre-create", size=0, size_is_deferred=True, headers={"Authorization": [f"Bearer {self.token}"]}
        )
        self.assertRejected(self.hook(payload), 400)

    def test_pre_create_over_user_quota(self):
        self.user.storage_quota = 100
        self.user.save()
        try:
            payload = hook_payload("pre-create", size=1000, headers={"Authorization": [f"Bearer {self.token}"]})
            self.assertRejected(self.hook(payload), 400)
        finally:
            self.user.storage_quota = 0
            self.user.save()

    @override_settings(UPLOAD_MAX_SIZE=500)
    def test_pre_create_exceeds_max_size(self):
        payload = hook_payload("pre-create", size=1000, headers={"Authorization": [f"Bearer {self.token}"]})
        self.assertRejected(self.hook(payload), 413)

    def test_pre_create_rejects_when_disk_nearly_full(self):
        with patch("api.tus.has_disk_space", return_value=False):
            payload = hook_payload("pre-create", size=1000, headers={"Authorization": [f"Bearer {self.token}"]})
            self.assertRejected(self.hook(payload), 507)

    def test_pre_create_allows_when_disk_has_space(self):
        with patch("api.tus.has_disk_space", return_value=True):
            payload = hook_payload("pre-create", size=1000, headers={"Authorization": [f"Bearer {self.token}"]})
            response = self.hook(payload)
            self.assertFalse(response.json().get("RejectUpload"))

    def test_pre_create_parses_options(self):
        """Header and metadata options land in df_kwargs like the XHR endpoint."""
        payload = hook_payload(
            "pre-create",
            headers={"Authorization": [f"Bearer {self.token}"], "Strip-Gps": ["true"], "Format": ["uuid"]},
            metadata={"password": "hunter2", "Expires-At": "1h", "user_id": "999"},  # nosec  # NOSONAR
        )
        response = self.hook(payload)
        meta = response.json()["ChangeFileInfo"]["MetaData"]
        # a client-spoofed user_id is always overwritten with the real one
        self.assertEqual(meta["user_id"], str(self.user.id))
        kwargs = json.loads(meta["df_kwargs"])
        self.assertEqual(kwargs["strip_gps"], "true")
        self.assertEqual(kwargs["format"], "uuid")
        self.assertEqual(kwargs["password"], "hunter2")
        self.assertEqual(kwargs["expr"], "1h")

    def test_post_finish_enqueues_import(self):
        with patch("api.tus.import_tus_upload") as mock_task:
            payload = hook_payload(
                "post-finish",
                metadata={"user_id": str(self.user.id), "df_kwargs": '{"private": "true"}', "name": "video.mp4"},
                storage={"Type": "filestore", "Path": "/data/media/tus/abc123"},
            )
            response = self.hook(payload)
        self.assertEqual(response.status_code, 200)
        mock_task.delay.assert_called_once_with(
            "/data/media/tus/abc123", "video.mp4", self.user.id, {"private": "true"}
        )

    def test_post_finish_without_user_id_ignored(self):
        """An upload that skipped pre-create stamping must not be imported."""
        with patch("api.tus.import_tus_upload") as mock_task:
            payload = hook_payload(
                "post-finish", metadata={"name": "x.bin"}, storage={"Type": "filestore", "Path": "/data/media/tus/x"}
            )
            response = self.hook(payload)
        self.assertEqual(response.status_code, 200)
        mock_task.delay.assert_not_called()

    def test_pre_create_strips_credentials_from_metadata(self):
        """Tokens must never persist into tusd's .info sidecar / HEAD echo."""
        payload = hook_payload(
            "pre-create",
            metadata={"authorization": self.token, "Token": self.token, "name": "keep.bin"},
        )
        response = self.hook(payload)
        meta = response.json()["ChangeFileInfo"]["MetaData"]
        self.assertEqual(meta["user_id"], str(self.user.id))
        self.assertEqual(meta["name"], "keep.bin")
        for key in meta:
            self.assertNotIn(key.lower(), ("authorization", "token"))

    def test_invalid_json(self):
        url = reverse("api:tus-hook") + f"?secret={TEST_HOOK_SECRET}"
        response = self.client.post(url, data="not json", content_type="application/json")
        self.assertEqual(response.status_code, 400)

    def test_unknown_hook_type_is_noop(self):
        response = self.hook(hook_payload("post-terminate"))
        self.assertEqual(response.status_code, 200)

    def test_hook_disabled_is_404(self):
        with override_settings(TUS_ENABLED=False):
            response = self.hook(hook_payload("pre-create"))
        self.assertEqual(response.status_code, 404)

    def test_hook_missing_secret(self):
        response = self.hook(hook_payload("pre-create"), secret=None)
        self.assertEqual(response.status_code, 403)

    def test_hook_wrong_secret(self):
        response = self.hook(hook_payload("pre-create"), secret="wrong")  # nosec  # NOSONAR
        self.assertEqual(response.status_code, 403)

    def test_hook_unconfigured_secret_fails_closed(self):
        """No env secret and no secret file: every call is rejected."""
        with override_settings(
            TUS_HOOK_SECRET="", TUS_HOOK_SECRET_FILE="/nonexistent/tus-hook.secret"
        ):  # nosec  # NOSONAR
            response = self.hook(hook_payload("pre-create"))
        self.assertEqual(response.status_code, 403)

    def test_hook_secret_from_file(self):
        with tempfile.NamedTemporaryFile("w", suffix=".secret", delete=False) as f:  # NOSONAR
            f.write(f"{TEST_HOOK_SECRET}\n")
        try:
            with override_settings(TUS_HOOK_SECRET="", TUS_HOOK_SECRET_FILE=f.name):  # nosec  # NOSONAR
                response = self.hook(hook_payload("post-terminate"))
            self.assertEqual(response.status_code, 200)
        finally:
            os.remove(f.name)


class TusImportTaskTestCase(TestCase):
    """Test the import_tus_upload / cleanup_tus_uploads Celery tasks"""

    @classmethod
    def setUpTestData(cls):
        call_command("loaddata", "settings/fixtures/sitesettings.json", verbosity=0)
        cls.user = CustomUser.objects.create_user(
            username="tustaskuser",
            email="tustask@test.com",
            password=TEST_PASSWORD,  # nosec  # NOSONAR
        )

    def setUp(self):
        self.tus_dir = tempfile.mkdtemp()

    def write_upload(self, name="abc123", content=b"tus test content"):
        path = os.path.join(self.tus_dir, name)
        with open(path, "wb") as f:
            f.write(content)
        with open(path + ".info", "w") as f:
            f.write("{}")
        return path

    def test_import_creates_file_and_cleans_up(self):
        with self.settings(TUS_UPLOAD_DIR=self.tus_dir):
            path = self.write_upload()
            import_tus_upload(path, "upload.txt", self.user.id, {})
        file = Files.objects.filter(user=self.user).first()
        self.assertIsNotNone(file)
        self.assertEqual(file.size, len(b"tus test content"))
        self.assertFalse(os.path.exists(path))
        self.assertFalse(os.path.exists(path + ".info"))

    def test_import_applies_options(self):
        options = {"private": "true", "password": "hunter2"}  # nosec  # NOSONAR
        with self.settings(TUS_UPLOAD_DIR=self.tus_dir):
            path = self.write_upload()
            import_tus_upload(path, "secret.txt", self.user.id, options)
        file = Files.objects.filter(user=self.user).first()
        self.assertTrue(file.private)
        self.assertEqual(file.password, "hunter2")

    def test_import_rejects_over_quota(self):
        """Concurrent uploads can pass pre-create individually; the import
        recheck against the real on-disk size is the backstop."""
        self.user.storage_quota = 8
        self.user.save()
        try:
            with self.settings(TUS_UPLOAD_DIR=self.tus_dir):
                path = self.write_upload(content=b"sixteen bytes!!!")
                import_tus_upload(path, "big.txt", self.user.id, {})
            self.assertFalse(Files.objects.filter(user=self.user).exists())
            self.assertFalse(os.path.exists(path))
            self.assertFalse(os.path.exists(path + ".info"))
        finally:
            self.user.storage_quota = 0
            self.user.save()

    @override_settings(UPLOAD_MAX_SIZE=8)
    def test_import_rejects_over_max_size(self):
        with self.settings(TUS_UPLOAD_DIR=self.tus_dir):
            path = self.write_upload(content=b"sixteen bytes!!!")
            import_tus_upload(path, "big.txt", self.user.id, {})
        self.assertFalse(Files.objects.filter(user=self.user).exists())
        self.assertFalse(os.path.exists(path))

    def test_import_rejects_path_outside_tus_dir(self):
        outside = tempfile.NamedTemporaryFile(delete=False)  # NOSONAR
        outside.write(b"data")
        outside.close()
        try:
            with self.settings(TUS_UPLOAD_DIR=self.tus_dir):
                import_tus_upload(outside.name, "escape.txt", self.user.id, {})
            self.assertFalse(Files.objects.filter(user=self.user).exists())
            self.assertTrue(os.path.exists(outside.name))
        finally:
            os.remove(outside.name)

    def test_cleanup_sweeps_only_stale_files(self):
        with self.settings(TUS_UPLOAD_DIR=self.tus_dir, TUS_EXPIRE_HOURS=24):
            stale = self.write_upload("stale")
            fresh = self.write_upload("fresh")
            old = time.time() - 25 * 3600
            os.utime(stale, (old, old))
            os.utime(stale + ".info", (old, old))
            cleanup_tus_uploads()
        self.assertFalse(os.path.exists(stale))
        self.assertFalse(os.path.exists(stale + ".info"))
        self.assertTrue(os.path.exists(fresh))
        self.assertTrue(os.path.exists(fresh + ".info"))


class HasDiskSpaceTestCase(TestCase):
    """Test home.util.tus.has_disk_space"""

    def setUp(self):
        self.tus_dir = tempfile.mkdtemp()

    def fake_usage(self, free):
        return type("usage", (), {"total": 0, "used": 0, "free": free})()

    def test_rejects_when_declared_size_plus_headroom_exceeds_free(self):
        with self.settings(TUS_UPLOAD_DIR=self.tus_dir, TUS_DISK_HEADROOM_MB=1024):
            with patch("shutil.disk_usage", return_value=self.fake_usage(500 * 1024 * 1024)):
                self.assertFalse(has_disk_space(100 * 1024 * 1024))

    def test_allows_when_free_space_covers_size_plus_headroom(self):
        with self.settings(TUS_UPLOAD_DIR=self.tus_dir, TUS_DISK_HEADROOM_MB=1024):
            with patch("shutil.disk_usage", return_value=self.fake_usage(10 * 1024 * 1024 * 1024)):
                self.assertTrue(has_disk_space(100 * 1024 * 1024))

    def test_fails_open_on_stat_error(self):
        """A stat failure shouldn't itself block every upload."""
        with self.settings(TUS_UPLOAD_DIR="/nonexistent/path/for/test"):
            with patch("shutil.disk_usage", side_effect=OSError("no such path")):
                self.assertTrue(has_disk_space(100))
