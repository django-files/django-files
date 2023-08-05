from django.test import TestCase
from django.urls import reverse


class TestViews(TestCase):
    def setUp(self):
        self.views = {
            'health_check': 200,
            'flush_cache': 302,
            'oauth:login': 200,
            'oauth:start': 302,
            'home:index': 302,
            'home:gallery': 302,
            'home:uppy': 302,
            'home:settings': 302,
            'home:upload': 405,
        }

    def test_views(self):
        for view, status in self.views.items():
            print(f'Testing view "{view}" for code "{status}"')
            response = self.client.get(reverse(view))
            self.assertEqual(response.status_code, status)
