from django.test import TestCase
from django.urls import reverse


class TestViews(TestCase):
    def setUp(self):
        self.views = {
            'health_check': 200,
            'oauth:login': 200,
            'oauth:start': 302,
            'home:index': 302,
            'home:files': 302,
            'home:settings': 302,
            'home:upload': 405,
        }

    def test_views(self):
        for view, status in self.views.items():
            print('Testing view "{}" for code "{}"'.format(view, status))
            response = self.client.get(reverse(view))
            self.assertEqual(response.status_code, status)
