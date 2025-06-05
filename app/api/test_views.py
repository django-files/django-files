import logging

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from oauth.models import CustomUser

log = logging.getLogger("app")


class UserApiTestCase(TestCase):
    """Test User API endpoints - Simple version to avoid timeouts"""

    def setUp(self):
        """Set up test environment"""
        call_command("loaddata", "settings/fixtures/sitesettings.json", verbosity=0)

        # Create test users
        self.superuser = CustomUser.objects.create_superuser(
            username="superuser", email="super@test.com", password="12345"  # nosec
        )

        self.regular_user = CustomUser.objects.create_user(
            username="regularuser", email="regular@test.com", password="12345"  # nosec
        )

    def test_current_user_get_with_auth(self):
        """Test GET /api/user/ with valid authorization"""
        response = self.client.get(reverse("api:current-user"), HTTP_AUTHORIZATION=self.regular_user.authorization)
        self.assertEqual(response.status_code, 200)

    def test_current_user_get_without_auth(self):
        """Test GET /api/user/ without authorization"""
        response = self.client.get(reverse("api:current-user"))
        self.assertEqual(response.status_code, 401)

    def test_users_list_as_superuser(self):
        """Test GET /api/users/ as superuser"""
        response = self.client.get(reverse("api:users"), HTTP_AUTHORIZATION=self.superuser.authorization)
        self.assertEqual(response.status_code, 200)

    def test_users_list_as_regular_user_denied(self):
        """Test GET /api/users/ as regular user (should be denied)"""
        response = self.client.get(reverse("api:users"), HTTP_AUTHORIZATION=self.regular_user.authorization)
        self.assertEqual(response.status_code, 403)
