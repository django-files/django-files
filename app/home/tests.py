import logging
import os
import shutil
from django.test import TestCase
from pathlib import Path
from django.conf import settings
from channels.testing import ChannelsLiveServerTestCase
from django.core.management import call_command
from django.urls import reverse
from playwright.sync_api import sync_playwright

from api.views import gen_short
from home.models import Files, ShortURLs
from home.tasks import delete_expired_files, app_init, process_stats, flush_template_cache
from home.util.file import process_file
from oauth.models import CustomUser
from settings.models import SiteSettings

log = logging.getLogger('app')


class TestAuthViews(TestCase):
    """Test Auth Views"""
    views = {
        'oauth:login': 302,
        'home:index': 200,
        'home:gallery': 200,
        'home:uppy': 200,
        'home:files': 200,
        'home:albums': 200,
        'home:shorts': 200,
        'home:stats': 200,
        'settings:site': 200,
        'settings:user': 200,
        'settings:sharex': 200,
        'settings:sharex-url': 200,
        'settings:flameshot': 200,
        'api:status': 200,
        'api:stats': 200,
        'api:recent': 200,
    }

    def setUp(self):
        call_command('loaddata', 'settings/fixtures/sitesettings.json', verbosity=0)
        self.user = CustomUser.objects.create_superuser(username='testuser', password='12345')
        log.info('self.user.authorization: %s', self.user.authorization)
        login = self.client.login(username='testuser', password='12345')
        log.info('login: %s', login)

    def test_views_with_auth(self):
        for view, status in self.views.items():
            print(f'Testing view "{view}" for code "{status}"')
            response = self.client.get(reverse(view))
            self.assertEqual(response.status_code, status)


class PlaywrightTest(ChannelsLiveServerTestCase):
    """Test Playwright"""
    screenshots = 'screenshots'
    # TODO: Add Upload view back
    views = ['Gallery', 'Upload/Files', 'Upload/Text', 'Files', 'Albums', 'Shorts', 'Stats']
    previews = ['README.md', 'requirements.txt', 'main.html', 'home_tags.py', 'an225.jpg']
    context = None
    browser = None
    playwright = None
    user = None
    count = 0

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if not os.path.isdir(cls.screenshots):
            os.mkdir(cls.screenshots)
        call_command('loaddata', 'settings/fixtures/sitesettings.json', verbosity=0)
        call_command('loaddata', 'settings/fixtures/customuser.json', verbosity=0)
        call_command('loaddata', 'settings/fixtures/webhooks.json', verbosity=0)
        call_command('loaddata', 'settings/fixtures/discord.json', verbosity=0)
        # cls.user = CustomUser.objects.create_superuser(username='testuser', password='12345')
        cls.user = CustomUser.objects.get(pk=1)
        log.info('cls.user.authorization: %s', cls.user.authorization)
        os.environ['DJANGO_ALLOW_ASYNC_UNSAFE'] = 'true'
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch()
        cls.context = cls.browser.new_context(color_scheme='dark')
        # storage = cls.context.storage_state(path='state.json')
        # cls.context = cls.context.new_context(storage_state='state.json')
        log.info('settings.MEDIA_ROOT: %s', settings.MEDIA_ROOT)
        if os.path.isdir(settings.MEDIA_ROOT):
            log.info('Removing: %s', settings.MEDIA_ROOT)
            shutil.rmtree(settings.MEDIA_ROOT)

    def screenshot(self, page, name):
        self.count += 1
        page.screenshot(path=f'{self.screenshots}/{self.count:0>{2}}_{name}.png')

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls.browser.close()
        cls.playwright.stop()

    def test_browser_views(self):
        settings = SiteSettings.objects.settings()
        settings.site_url = self.live_server_url
        settings.save()
        print(f'--- {self.live_server_url} ---')
        print('--- prep files for browser shots ---')
        print('-'*40)
        log.debug('os.getcwd(): %s', os.getcwd())
        # process_file_path(Path('../.github/workflows/test.yaml'), self.user.id)
        # process_file_path(Path('../.prettierrc.json'), self.user.id)
        process_file_path(Path('./requirements.txt'), self.user.id)
        process_file_path(Path('../README.md'), self.user.id)
        process_file_path(Path('./templates/main.html'), self.user.id)
        process_file_path(Path('./home/templatetags/home_tags.py'), self.user.id)
        private_file = process_file_path(Path('../.assets/an225.jpg'), self.user.id)
        dirs = ['static/video', '../.assets']
        for directory in dirs:
            dir_path = Path(directory)
            log.debug('directory: %s', dir_path)
            for file_name in os.listdir(directory):
                if file_name == 'gps.jpg':
                    continue
                path = dir_path / file_name
                if path.is_file():
                    log.debug('path.name: %s', path.name)
                    file = process_file_path(path, self.user.id)
                    log.debug('file.pk: %s', file.pk)
        print('-'*40)
        print('--- loading shorts for browser shots ---')
        for url in short_urls:
            short = ShortURLs.objects.create(url=url, short=gen_short(), user=self.user)
            log.debug('short: %s', short)
        print('-'*40)
        print('--- Testing: process_stats')
        process_stats()
        print('--- Running: test_browser_views ---')
        page = self.context.new_page()
        page.goto(f'{self.live_server_url}/')
        page.locator('text=Django Files')
        page.wait_for_timeout(timeout=750)
        page.fill('[name=username]', 'testuser')
        page.fill('[name=password]', '12345')
        self.screenshot(page, 'Login')

        page.locator('#login-button').click()
        page.locator('text=Home')
        # page.wait_for_selector('text=Home', timeout=3000)
        page.wait_for_timeout(timeout=500)
        self.screenshot(page, 'Home')

        for view in self.views:
            print('---------- view: %s' % view)
            if '/' in view:
                log.debug('view: %s', view)
                menu, view = view.split('/')
                log.debug('menu: %s', menu)
                log.debug('view: %s', view)
                log.debug('NOT IMPLEMENTED!')
                continue
            else:
                if view == 'Gallery':
                    page.locator('.nav-link').locator('text=Files').first.click()
                    page.wait_for_timeout(timeout=350)
                    page.locator('.link-body-emphasis').locator('text=Gallery').first.click()
                    page.wait_for_timeout(timeout=500)
                else:
                    page.locator('.nav-link').locator(f'text={view}').first.click()

            if view == 'Upload':
                page.wait_for_timeout(timeout=750)
                self.screenshot(page, view)
            else:
                page.wait_for_timeout(timeout=500)
                # page.locator(f'text={view}')
                page.get_by_role("heading", name=view)
                self.screenshot(page, view)

            if view == 'Files':
                page.locator('.ctx-menu-12').first.click()
                self.screenshot(page, f'{view}-file-context-dropdown')
                page.locator('.ctx-rename').first.click()
                page.wait_for_timeout(timeout=500)
                page.locator('#name').fill('iamrenamed.jpg')
                self.screenshot(page, f'{view}-rename-click')
                page.locator('#file-rename-submit').first.click()
                page.wait_for_timeout(timeout=500)
                self.screenshot(page, f'{view}-file-is-renamed')
                page.locator('.ctx-menu-12').first.click()
                page.locator('.ctx-delete').first.click()
                page.wait_for_timeout(timeout=500)
                self.screenshot(page, f'{view}-delete-click')

                page.locator('#confirm-delete').first.click()
                # page.wait_for_timeout(timeout=500)
                # self.screenshot(page, f'{view}-delete-deleted')

            if view == 'Shorts':
                page.locator('#url').fill('https://github.com/django-files/django-files/pkgs/container/django-files')
                page.get_by_role('button', name='Create').click()
                print('--- Testing: flush_template_cache')
                page.wait_for_timeout(timeout=250)
                flush_template_cache()
                # page.on('dialog', lambda dialog: dialog.accept())
                page.reload()
                page.locator(f'text={view}')
                self.screenshot(page, f'{view}-create')

                page.locator('.delete-short-btn').first.click()
                page.wait_for_timeout(timeout=300)
                self.screenshot(page, f'{view}-delete-click')

                page.locator('#short-delete-confirm').click()
                # page.wait_for_timeout(timeout=500)
                self.screenshot(page, f'{view}-delete-deleted')

            if view == 'Albums':
                page.locator('#name').fill('My Cool Pictures')
                page.get_by_role('button', name='Create').click()
                flush_template_cache()
                page.wait_for_timeout(timeout=250)
                self.screenshot(page, f'{view}-create')
                page.locator('.nav-link').get_by_text('Files').click()
                page.wait_for_timeout(timeout=250)
                page.locator('.ctx-menu-11').first.click()
                page.locator('.ctx-album').first.click()
                page.wait_for_timeout(timeout=500)
                self.screenshot(page, f'{view}-add-file')
                page.get_by_text("My Cool Pictures").click()
                page.locator('#file-album-submit').click()
                page.locator('.nav-link').get_by_text('Albums').click()
                page.get_by_text('My Cool Pictures').click()
                page.get_by_title('Fujifilm_FinePix_E500.jpg').is_visible()
                self.screenshot(page, 'Album-view')

        page.locator('#navbarDropdown').click()
        page.locator('text=User Settings').first.click()
        self.screenshot(page, 'Settings-User')

        page.locator('#show_exif_preview').click()
        page.reload()
        page.wait_for_timeout(timeout=500)
        self.screenshot(page, 'Settings-User-save-settings')

        page.locator('.deleteDiscordHookBtn').first.click()
        page.wait_for_timeout(timeout=500)
        self.screenshot(page, 'Settings-delete-click')

        page.locator('#confirmDeleteDiscordHookBtn').click()
        page.wait_for_timeout(timeout=500)
        self.screenshot(page, 'Settings-delete-deleted')

        page.goto(f"{self.live_server_url}{reverse('home:public-uppy')}")
        page.wait_for_timeout(timeout=500)
        self.screenshot(page, 'Public-disabled-redirect')

        page.locator('#pub_load').click()
        page.reload()
        page.wait_for_timeout(timeout=500)
        self.screenshot(page, 'Settings-Site-save-settings')

        # Note: this does not flush the cache since it is an async task, it just tests the UI flush button
        page.locator('#navbarDropdown').click()
        page.locator('#flush-cache').click()
        page.wait_for_timeout(timeout=500)
        self.screenshot(page, 'Settings-Site-flush-cache')

        page.get_by_role('button', name='Create').click()
        page.wait_for_timeout(timeout=250)
        page.reload()
        page.locator('#invites').focus()
        self.screenshot(page, 'Settings-invite-created')

        page.goto(f"{self.live_server_url}{reverse('home:public-uppy')}")
        page.wait_for_timeout(timeout=500)
        self.screenshot(page, 'Public-enabled')

        control = 'gps2.jpg'
        page.goto(f'{self.live_server_url}/u/{control}')
        page.wait_for_timeout(timeout=350)
        page.locator('text=12/17/2022 12:14:26')
        page.locator('text=samsung SM-G973U')
        page.locator('text=King County, Washington, United States')
        page.locator('text=109.0 m')
        page.locator('text=4mm')
        page.locator('text=1.5')
        page.locator('text=400')
        page.locator('text=1/120 s')
        self.screenshot(page, f'Preview-{control}')

        page.locator('.context-placement').click()
        page.locator('text=View Raw').click()
        page.wait_for_load_state()
        self.screenshot(page, f'Raw-{control}')

        for file in self.previews:
            page.goto(f'{self.live_server_url}/u/{file}')
            page.wait_for_timeout(timeout=1000)
            self.screenshot(page, f'Preview-{file}')

        page.goto(f'{self.live_server_url}/404')
        self.screenshot(page, 'Error-404-authed')

        print('--- test_quotas ---')
        page.goto(f'{self.live_server_url}/settings/site/')
        page.get_by_label('Global Storage Quota').fill('750KB')
        page.get_by_label('Site Description').click()
        page.wait_for_timeout(timeout=500)
        page.reload()
        self.screenshot(page, 'Site Settings with Global Quota Near Full')

        page.goto(f'{self.live_server_url}/uppy/')
        with page.expect_file_chooser() as fc_info:
            page.locator('.uppy-DashboardTab-iconMyDevice').click()
        file_chooser = fc_info.value
        file_chooser.set_files("../.assets/an225.jpg")
        page.locator('.uppy-c-btn-primary').click()
        page.wait_for_timeout(timeout=500)
        self.screenshot(page, 'Upload Failed by Global Quota')

        # LOGOUT HAPPENS HERE
        page.goto(f'{self.live_server_url}/')
        page.locator('#navbarDropdown').click()
        page.locator('.log-out').click()
        page.wait_for_timeout(timeout=750)
        self.screenshot(page, 'Logout')

        private_file.private = True
        private_file.save()
        page.goto(f'{self.live_server_url}{private_file.preview_uri()}')
        page.locator('text=Permission Denied')
        self.screenshot(page, 'Error-403-private-file')

        private_file.password = 'test123'
        private_file.save()
        page.goto(f'{self.live_server_url}/u/{private_file.name}')
        page.locator('text=Unlock')
        page.wait_for_timeout(timeout=600)
        self.screenshot(page, 'File-password')

        page.fill('[name=password]', 'test123')
        page.locator('#unlock-button').click()
        page.locator(f'text={private_file.size}')
        page.wait_for_timeout(timeout=250)
        self.screenshot(page, 'File-unlock')


class FilesTestCase(TestCase):
    """Test Files"""
    def setUp(self):
        call_command('loaddata', 'settings/fixtures/sitesettings.json', verbosity=0)
        self.user = CustomUser.objects.create_superuser(username='testuser', password='12345')
        log.info('self.user.authorization: %s', self.user.authorization)
        login = self.client.login(username='testuser', password='12345')
        log.info('login: %s', login)
        site_settings = SiteSettings.objects.settings()
        log.info('site_settings: %s', site_settings)
        log.info('settings.MEDIA_ROOT: %s', settings.MEDIA_ROOT)
        if os.path.isdir(settings.MEDIA_ROOT):
            log.info('Removing: %s', settings.MEDIA_ROOT)
            shutil.rmtree(settings.MEDIA_ROOT)
        os.mkdir(settings.MEDIA_ROOT)

    def tearDown(self):
        pass

    def test_files(self):
        path = Path('../.assets/gps.jpg')
        print(f'--- Testing Control File: {path}')
        file = process_file_path(path, self.user.id)
        # with path.open(mode='rb') as f:
        #     file = process_file(path.name, f, self.user.id)
        print(f'file.file.path: {file.file.path}')
        print(f'file.get_url(): {file.get_url()}')
        print(f'file.preview_uri(): {file.preview_uri()}')
        self.assertRegex(file.get_url(), r'/r/gps\.jpg\?md5=.*&expires=.*')
        self.assertEqual(file.preview_uri(), '/u/gps.jpg')
        self.assertEqual(file.mime, 'image/jpeg')
        self.assertEqual(file.size, 3412)
        self.assertEqual(file.get_size(), '3.4 KB')
        self.assertEqual(file.exif, exif_data)
        self.assertEqual(file.meta, meta_data)
        response = self.client.get(reverse('home:url-route', kwargs={'filename': file.name}), follow=True)
        self.assertEqual(response.status_code, 200)
        files = Files.objects.filter(user=self.user)
        self.assertEqual(len(os.listdir(settings.MEDIA_ROOT)), len(files) + 1)  # account for thumbnail added files

        print('--- Testing: API:REMOTE')
        url = 'https://raw.githubusercontent.com/django-files/django-files/master/.assets/gps.jpg'
        data = {'url': url, 'Expires-At': '1y'}
        response = self.client.post(reverse('api:remote'), data, content_type='application/json', follow=True)
        print(response.json())
        self.assertEqual(response.status_code, 200)
        files = Files.objects.filter(user=self.user)
        self.assertEqual(len(os.listdir(settings.MEDIA_ROOT)), len(files) + 1)

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
        print('--- Testing: delete_expired_files')
        delete_expired_files()


def process_file_path(path: Path, user_id: int) -> Files:
    print(f'--- Processing: path: {path}')
    with path.open(mode='rb') as f:
        file = process_file(path.name, f, user_id)
        log.debug('file: %s', file)
        return file


short_urls = [
    'https://github.com/django-files/django-files',
    'https://github.com/django-files/web-extension',
    'https://addons.mozilla.org/addon/django-files',
    'https://chrome.google.com/webstore/detail/django-files/abpbiefojfkekhkjnpakpekkpeibnjej',
]

meta_data = {
    "PILImageWidth": 128,
    "PILImageHeight": 96,
    "GPSArea": "Cascade, Idaho, United States"
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
