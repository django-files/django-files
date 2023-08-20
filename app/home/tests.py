from django.test import TestCase
# from pathlib import Path
# from django.core.management import call_command
# from django.core.files import File
from django.urls import reverse

from oauth.models import CustomUser
from home.models import ShortURLs
from home.tasks import delete_expired_files, app_init


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

# this needs to be reworked for new file processing setup
# class FilesTestCase(TestCase):
#     def setUp(self):
#         call_command('loaddata', 'home/fixtures/sitesettings.json', verbosity=0)
#         print('Creating Test User: testuser')
#         self.user = CustomUser.objects.create_user(username='testuser', password='12345')
#         print(self.user.authorization)
#         login = self.client.login(username='testuser', password='12345')
#         print(login)

#     def test_files(self):
#         """Test Files Object"""
#         path = Path('../.assets/gps.jpg')
#         print(f'Creating Files Object from file: {path}')
#         with path.open(mode='rb') as f:
#             file = Files.objects.create(
#                 file=File(f, name=path.name),
#                 user=self.user,
#             )

#         print(file)
#         file.save()
#         process_file_upload(file.pk)
#         file = Files.objects.get(pk=file.pk)
#         self.assertEqual(file.get_url(), 'https://example.com/r/gps.jpg')
#         self.assertEqual(file.preview_url(), 'https://example.com/u/gps.jpg')
#         self.assertEqual(file.preview_uri(), '/u/gps.jpg')
#         self.assertEqual(file.mime, 'image/jpeg')
#         self.assertEqual(file.size, 3518)
#         self.assertEqual(file.get_size(), '3.4 KiB')
#         self.assertEqual(file.exif, exif_data)
#         self.assertEqual(file.meta, meta_data)
#         response = self.client.get(reverse('home:url-route', kwargs={'filename': file.name}), follow=True)
#         print(dir(response))
#         self.assertEqual(response.status_code, 200)
#         process_stats()

    def test_api(self):
        """Test API"""
        print('Testing view "api:remote" for code "200"')
        url = 'https://repository-images.githubusercontent.com/672712475/52cf00a8-31de-4b0a-8522-63670bb4314a'
        data = {'url': url, 'Expires-At': '1y'}
        response = self.client.post(reverse('api:remote'), data, content_type='application/json', follow=True)
        print(response.json())
        self.assertEqual(response.status_code, 200)

    def test_shorts(self):
        """Test Tasks"""
        print('Testing Shorts')
        url = 'https://repository-images.githubusercontent.com/672712475/52cf00a8-31de-4b0a-8522-63670bb4314a'
        body = {'url': url}
        response1 = self.client.post(reverse('home:shorten'), body, content_type='application/json', follow=True)
        data = response1.json()
        print(data)
        self.assertEqual(response1.status_code, 200)
        short = ShortURLs.objects.all().first()
        print(short)
        # self.assertEqual(data['url'], 'https://example.com/s/Y2sa')
        self.assertEqual(short.url, url)
        response2 = self.client.get(reverse('home:short', kwargs={'short': short.short}))
        self.assertEqual(response2.status_code, 302)
        print(response2.headers)

    @staticmethod
    def test_tasks():
        """Test Tasks"""
        print('Testing Tasks')
        app_init()
        delete_expired_files()


meta_data = {
    "PILImageWidth": 128,
    "PILImageHeight": 96,
    "GPSArea": "Cascade, Idaho"
}

exif_data = {
    "ImageWidth": "4032",
    "ImageLength": "3024",
    "GPSInfo": {
        "1": "N",
        "2": [44.0, 30.0, 15.1703],
        "3": "W",
        "4": [116.0, 2.0, 1.1939],
        "5": "\u0000",
        "6": 1412.065,
        "7": [22.0, 17.0, 38.0],
        "29": "2022:12:21",
    },
    "ResolutionUnit": "2",
    "ExifOffset": "230",
    "Make": "samsung",
    "Model": "SM-G973U",
    "Software": "paint.net 4.3.12",
    "DateTime": "2022:12:21 15:18:20",
    "YCbCrPositioning": "1",
    "XResolution": "72.0",
    "YResolution": "72.0",
    "ExifVersion": "0220",
    "ComponentsConfiguration": "\u0001\u0002\u0003\u0000",
    "ShutterSpeedValue": "8.415",
    "DateTimeOriginal": "2022:12:21 15:18:20",
    "DateTimeDigitized": "2022:12:21 15:18:20",
    "ApertureValue": "2.52",
    "BrightnessValue": "6.68",
    "ExposureBiasValue": "0.0",
    "MaxApertureValue": "1.16",
    "MeteringMode": "2",
    "Flash": "0",
    "FocalLength": "4.3",
    "ColorSpace": "1",
    "ExifImageWidth": "4032",
    "ExifInteroperabilityOffset": "724",
    "SceneCaptureType": "0",
    "SubsecTime": "094798",
    "SubsecTimeOriginal": "094798",
    "SubsecTimeDigitized": "094798",
    "ExifImageHeight": "3024",
    "SensingMethod": "1",
    "ExposureTime": "0.0029239766081871343",
    "FNumber": "2.4", "SceneType": "\u0001",
    "ExposureProgram": "2",
    "ISOSpeedRatings": "50",
    "ExposureMode": "0",
    "FlashPixVersion": "0100",
    "WhiteBalance": "0",
    "FocalLengthIn35mmFilm": "26",
}
