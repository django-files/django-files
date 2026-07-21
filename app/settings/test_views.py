from django.core.cache import cache
from django.core.management import call_command
from django.test import Client, TestCase
from django.urls import reverse
from djangofiles.test_utils import TEST_PASSWORD
from oauth.models import CustomUser


class UserSessionsContextTestCase(TestCase):
    """GET /settings/user/ only lists the authenticated user's own sessions."""

    @classmethod
    def setUpTestData(cls):
        call_command("loaddata", "settings/fixtures/sitesettings.json", verbosity=0)
        cls.user_a = CustomUser.objects.create_user(
            username="ctxusera",
            email="ctxa@test.com",
            password=TEST_PASSWORD,  # nosec  # NOSONAR
        )
        cls.user_b = CustomUser.objects.create_user(
            username="ctxuserb",
            email="ctxb@test.com",
            password=TEST_PASSWORD,  # nosec  # NOSONAR
        )

    def setUp(self):
        # sessions live in Redis, not the DB, so TestCase's rollback won't clear them
        cache.clear()

    @staticmethod
    def _login(username):
        client = Client()
        client.login(username=username, password=TEST_PASSWORD)  # nosec  # NOSONAR
        return client

    def test_sessions_scoped_to_current_user_only(self):
        # user B has an active session too, but must never appear on user A's page
        self._login("ctxuserb")
        client_a = self._login("ctxusera")
        response = client_a.get(reverse("settings:user"))
        self.assertEqual(response.status_code, 200)
        sessions = response.context["sessions"]
        self.assertEqual(len(sessions), 1)
        self.assertTrue(all(s["user_id"] == str(self.user_a.id) for s in sessions))

    def test_second_device_session_included(self):
        client_a1 = self._login("ctxusera")
        self._login("ctxusera")
        response = client_a1.get(reverse("settings:user"))
        sessions = response.context["sessions"]
        self.assertEqual(len(sessions), 2)

    def test_current_session_flagged(self):
        client_a = self._login("ctxusera")
        response = client_a.get(reverse("settings:user"))
        sessions = response.context["sessions"]
        current = [s for s in sessions if s.get("current")]
        self.assertEqual(len(current), 1)
        self.assertEqual(current[0]["key"], client_a.session.session_key)
