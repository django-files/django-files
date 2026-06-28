from django.test import TestCase
from django.urls import reverse
from djangofiles.test_utils import TEST_PASSWORD
from oauth.models import CustomUser


class TestViews(TestCase):
    """Test General Views"""

    def setUp(self):
        # An administrator must exist, otherwise oauth:login redirects (302) to the
        # first-run setup wizard instead of rendering the login page.
        CustomUser.objects.create_superuser(username="admin", password=TEST_PASSWORD)
        self.views = {
            "health_check": 200,
            "flush_cache": 302,
            "oauth:login": 200,
            "oauth:discord": 302,
            "home:index": 302,
            "home:gallery": 302,
            "home:uppy": 302,
            "home:files": 302,
            "home:shorts": 302,
            "home:stats": 302,
            "home:upload": 405,
            "home:shorten": 405,
            "settings:user": 302,
            "settings:site": 302,
            "api:upload": 405,
            "api:shorten": 405,
        }

    def test_views(self):
        for view, status in self.views.items():
            print(f'Testing view "{view}" for code "{status}"')
            response = self.client.get(reverse(view))
            self.assertEqual(response.status_code, status)
