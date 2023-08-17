from django.test import TestCase
from pathlib import Path
from django.core.management import call_command
from django.core.files import File
from django.urls import reverse

from oauth.models import CustomUser
from home.models import Files
from home.tasks import process_file_upload, delete_expired_files, process_stats, app_init


class TestAuthViews(TestCase):
    """Test Auth Views"""
    def setUp(self):
        self.views = {
            'oauth:login': 302,
            'home:index': 200,
            'home:files': 200,
            'home:gallery': 200,
            'home:uppy': 200,
            'home:shorts': 200,
            'home:settings': 200,
            'home:stats': 200,
            'home:gen-sharex': 200,
            'home:gen-sharex-url': 200,
            'home:gen-flameshot': 200,
            'api:status': 200,
            'api:stats': 200,
            'api:recent': 200,
        }
        print('Creating Test User: testuser')
        self.user = CustomUser.objects.create_user(username='testuser', password='12345')
        print(self.user.authorization)
        login = self.client.login(username='testuser', password='12345')
        print(login)

    def test_views_with_auth(self):
        for view, status in self.views.items():
            print(f'Testing view "{view}" for code "{status}"')
            response = self.client.get(reverse(view))
            self.assertEqual(response.status_code, status)


class FilesTestCase(TestCase):
    def setUp(self):
        call_command('loaddata', 'home/fixtures/sitesettings.json', verbosity=0)
        print('Creating Test User: testuser')
        self.user = CustomUser.objects.create_user(username='testuser', password='12345')
        print(self.user.authorization)
        login = self.client.login(username='testuser', password='12345')
        print(login)

    def test_files(self):
        """Test Files Object"""
        print('Creating Files Object from file: ../app/static/video/loop.jpg')
        path = Path('../app/static/video/loop.jpg')
        with path.open(mode='rb') as f:
            file = Files.objects.create(
                file=File(f, name=path.name),
                user=self.user,
            )
        print(file)
        file.save()
        process_file_upload(file.pk)
        file = Files.objects.get(pk=file.pk)
        print(file.mime)
        print(file.get_url())
        print(file.preview_url())
        print(file.preview_uri())
        print(file.get_size())

    def test_api(self):
        """Test API"""
        print('Testing view "api:remote" for code "200"')
        url = 'https://repository-images.githubusercontent.com/672712475/52cf00a8-31de-4b0a-8522-63670bb4314a'
        response = self.client.post(reverse('api:remote'), {'url': url}, content_type='application/json', follow=True)
        print(response.json())
        self.assertEqual(response.status_code, 200)

    @staticmethod
    def test_tasks():
        """Test Tasks"""
        print('Testing Tasks')
        app_init()
        delete_expired_files()
        process_stats()
