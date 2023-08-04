from django.test import TestCase
# from pathlib import Path
# from django.core.files import File
from django.urls import reverse

from oauth.models import CustomUser
# from .tasks import process_file_upload
# from .models import Files


class TestAuthViews(TestCase):
    def setUp(self):
        self.views = {
            'health_check': 200,
            'flush_cache': 405,
            'oauth:login': 302,
            # 'home:index': 200,
            # 'home:gallery': 200,
            # 'home:files': 200,
            # 'home:settings': 200,
            # 'home:gen-sharex': 200,
            # 'home:gen-flameshot': 200,
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

#
# class FilesTestCase(TestCase):
#     def setUp(self):
#         print('Creating Test User: testuser')
#         self.user = CustomUser.objects.create_user(username='testuser', password='12345')
#         print(self.user.authorization)
#         login = self.client.login(username='testuser', password='12345')
#         print(login)
#
#     TODO: Needs a redis service
#     def test_files(self):
#         """Test Files Object"""
#         print('Creating Files Object from file: manage.py')
#         path = Path('manage.py')
#         with path.open(mode='rb') as f:
#             file = Files.objects.create(
#                 file=File(f, name=path.name),
#                 user=self.user,
#             )
#         print(file)
#         # file.info = 'test'
#         # file.save()
#         # # process_file_upload(file.pk)
#         # file = Files.objects.get(pk=file.pk)
#         # print(file.get_size())
#         # print(file.get_url())
#
#     def test_sharex(self):
#         """Test ShareX Response"""
#         print('Testing view "home:gen-sharex" for code "200"')
#         response = self.client.get(reverse('home:gen-sharex'))
#         print(response)
#         self.assertEqual(response.status_code, 200)
