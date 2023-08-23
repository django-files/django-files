import os
# import re
import shutil
from django.test import TestCase
from pathlib import Path
from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.core.management import call_command
# from django.core.files import File
from django.urls import reverse
from playwright.sync_api import sync_playwright

from oauth.models import CustomUser
from home.models import ShortURLs, Files
from home.tasks import delete_expired_files, app_init, process_stats
from home.util.file import process_file


class TestAuthViews(TestCase):
    """Test Auth Views"""
    views = {
        'oauth:login': 302,
        'home:index': 200,
        'home:gallery': 200,
        'home:uppy': 200,
        'home:files': 200,
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

    def setUp(self):
        call_command('loaddata', 'home/fixtures/sitesettings.json', verbosity=0)
        self.user = CustomUser.objects.create_user(username='testuser', password='12345')
        print(self.user.authorization)
        login = self.client.login(username='testuser', password='12345')
        print(login)

    def test_views_with_auth(self):
        for view, status in self.views.items():
            print(f'Testing view "{view}" for code "{status}"')
            response = self.client.get(reverse(view))
            self.assertEqual(response.status_code, status)


class PlaywrightTest(StaticLiveServerTestCase):
    """Test Playwright"""
    screenshots = 'screenshots'
    views = ['Gallery', 'Upload', 'Files', 'Shorts', 'Settings']
    context = None
    browser = None
    playwright = None

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if not os.path.isdir(cls.screenshots):
            os.mkdir(cls.screenshots)
        call_command('loaddata', 'home/fixtures/sitesettings.json', verbosity=0)
        user = CustomUser.objects.create_user(username='testuser', password='12345')
        print(user.authorization)
        os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch()
        cls.context = cls.browser.new_context(color_scheme='dark')
        # storage = cls.context.storage_state(path="state.json")
        # cls.context = cls.context.new_context(storage_state="state.json")

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls.browser.close()
        cls.playwright.stop()

    def test_browser_views(self):
        page = self.context.new_page()
        page.goto(f"{self.live_server_url}/")
        page.locator('text=Django Files')
        page.wait_for_timeout(timeout=1000)
        page.screenshot(path=f'{self.screenshots}/Login.png')
        page.fill('[name=username]', 'testuser')
        page.fill('[name=password]', '12345')
        page.click('#login-button')

        page.wait_for_selector('text=Home', timeout=3000)
        page.screenshot(path=f'{self.screenshots}/Home.png')

        # page.click('text=View Stats')
        # page.get_by_role("link", name=re.compile(".+View Stats", re.IGNORECASE)).click()
        page.goto(f"{self.live_server_url}/stats/")
        page.wait_for_selector('text=Stats', timeout=3000)
        page.screenshot(path=f'{self.screenshots}/Stats.png')

        for view in self.views:
            page.locator(f'text={view}').first.click()
            page.wait_for_selector(f'text={view}', timeout=3000)
            page.screenshot(path=f'{self.screenshots}/{view}.png')


class FilesTestCase(TestCase):
    """Test Files"""
    def setUp(self):
        call_command('loaddata', 'home/fixtures/sitesettings.json', verbosity=0)
        self.user = CustomUser.objects.create_user(username='testuser', password='12345')
        print(self.user.authorization)
        login = self.client.login(username='testuser', password='12345')
        print(login)
        print(f'settings.MEDIA_ROOT: {settings.MEDIA_ROOT}')
        if os.path.isdir(settings.MEDIA_ROOT):
            print(f'Removing: {settings.MEDIA_ROOT}')
            shutil.rmtree(settings.MEDIA_ROOT)
        os.mkdir(settings.MEDIA_ROOT)

    def tearDown(self):
        pass

    def test_files(self):
        path = Path('../.assets/gps.jpg')
        print(f'--- Testing: FILE PATH: {path}')
        with path.open(mode='rb') as f:
            file = process_file(path.name, f, self.user.id)
        print(f'file.file.path: {file.file.path}')
        # TODO: Fix File Processing so it does not create 2 file objects
        print(f'file.get_url(): {file.get_url()}')
        print(f'file.preview_url(): {file.preview_url()}')
        print(f'file.preview_uri(): {file.preview_uri()}')
        # self.assertEqual(file.get_url(), 'https://example.com/r/gps.jpg')
        # self.assertEqual(file.preview_url(), 'https://example.com/u/gps.jpg')
        # self.assertEqual(file.preview_uri(), '/u/gps.jpg')
        self.assertEqual(file.mime, 'image/jpeg')
        self.assertEqual(file.size, 3518)
        self.assertEqual(file.get_size(), '3.4 KiB')
        print('-'*40)
        print(file.exif)
        print('-'*40)
        print(exif_data)
        print('-'*40)
        self.assertEqual(file.exif, exif_data)
        self.assertEqual(file.meta, meta_data)
        response = self.client.get(reverse('home:url-route', kwargs={'filename': file.name}), follow=True)
        self.assertEqual(response.status_code, 200)
        # TODO: This will test file duplication once fixed
        files = Files.objects.filter(user=self.user)
        self.assertEqual(len(os.listdir(settings.MEDIA_ROOT)), len(files))

        print('--- Testing: API:REMOTE')
        url = 'https://raw.githubusercontent.com/django-files/django-files/master/.assets/gps.jpg'
        data = {'url': url, 'Expires-At': '1y'}
        response = self.client.post(reverse('api:remote'), data, content_type='application/json', follow=True)
        print(response.json())
        self.assertEqual(response.status_code, 200)
        # TODO: This will test file duplication once fixed
        files = Files.objects.filter(user=self.user)
        self.assertEqual(len(os.listdir(settings.MEDIA_ROOT)), len(files))

        print('--- Testing: SHORTS')
        url = 'https://raw.githubusercontent.com/django-files/django-files/master/.assets/gps.jpg'
        body = {'url': url}
        response1 = self.client.post(reverse('home:shorten'), body, content_type='application/json', follow=True)
        data = response1.json()
        print(data)
        self.assertEqual(response1.status_code, 200)
        short = ShortURLs.objects.all().first()
        print(short)
        self.assertEqual(short.url, url)
        response2 = self.client.get(reverse('home:short', kwargs={'short': short.short}))
        self.assertEqual(response2.status_code, 302)
        print(response2.headers.get('Location'))
        self.assertEqual(response2.headers.get('Location'), short.url)

        print(f' --- MEDIA_ROOT: {settings.MEDIA_ROOT} - {len(os.listdir(settings.MEDIA_ROOT))}')
        print(os.listdir(settings.MEDIA_ROOT))

        files = Files.objects.filter(user=self.user)
        print(f'files count: {len(files)}')
        shorts = ShortURLs.objects.filter(user=self.user)
        print(f'shorts count: {len(shorts)}')

        print('--- Testing: app_init')
        app_init()
        print('--- Testing: process_stats')
        process_stats()
        print('--- Testing: delete_expired_files')
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
        1: "N",
        2: (44.0, 30.0, 15.1703),
        3: "W",
        4: (116.0, 2.0, 1.1939),
        5: "\x00",
        6: 1412.065,
        7: (22.0, 17.0, 38.0),
        29: "2022:12:21",
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
    "ComponentsConfiguration": "\x01\x02\x03\x00",
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
    "FNumber": "2.4",
    "SceneType": "\x01",
    "ExposureProgram": "2",
    "ISOSpeedRatings": "50",
    "ExposureMode": "0",
    "FlashPixVersion": "0100",
    "WhiteBalance": "0",
    "FocalLengthIn35mmFilm": "26",
}
