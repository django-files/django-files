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
            'home:files': 302,
            'home:settings': 302,
            'home:upload': 405,
        }
        self.pk_views = {
            'home:delete-hook': 302,
            'home:delete-file': 302,
        }

    def test_views_without_auth(self):
        for view, status in self.views.items():
            print(f'Testing view "{view}" for code "{status}"')
            response = self.client.get(reverse(view))
            self.assertEqual(response.status_code, status)
        for view, status in self.pk_views.items():
            print(f'Testing view "{view}" for code "{status}"')
            response = self.client.get(reverse(view, kwargs={'pk': '1'}))
            self.assertEqual(response.status_code, status)
