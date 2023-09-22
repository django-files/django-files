import os
from django.core.cache import cache
from django.core.management.base import BaseCommand
from django.forms.models import model_to_dict

from oauth.models import CustomUser
from settings.models import SiteSettings


class Command(BaseCommand):
    help = 'App Startup Task'

    default_user = 'admin'
    default_pass = 'pbkdf2_sha256$600000$3qb8IYaOGB7XnZhBUJFPxH$RvY4+xyt54BtGZoiGeBldJRM6p3Fq9ehnr9inMiqh3E='

    def handle(self, *args, **options):
        # Variables
        username = os.environ.get('USERNAME')
        password = os.environ.get('PASSWORD')
        local = bool(username and password)
        oauth = bool(os.environ.get('DISCORD_CLIENT_ID') or os.environ.get('GITHUB_CLIENT_ID'))

        # Ensure User - see following blocks
        users = CustomUser.objects.all()

        # if users exist and local auth provided, create user or ensure password
        if users and local:
            # TODO: WARNING This will overwrite password set in UI on restart
            if user := users.filter(username=username):
                user[0].set_password(password)
                self.stdout.write(self.style.WARNING('Custom User Password Updated'))
            else:
                CustomUser.objects.create_superuser(username=username, password=password)
                self.stdout.write(self.style.WARNING('Custom User Created'))

        # no local users exist and no oauth method provided
        if not users and not oauth:
            if local:
                # if local auth, create user from provided credentials
                CustomUser.objects.create_superuser(username=username, password=password)
                self.stdout.write(self.style.WARNING('Custom User Created'))
                self.stdout.write(self.style.SUCCESS(f'Username: {username}'))
                self.stdout.write(self.style.SUCCESS('Password: *****'))
            else:
                CustomUser.objects.create(
                    username=self.default_user,
                    password=self.default_pass,
                    is_superuser=True,
                    is_staff=True,
                    show_setup=True,
                )
                self.stdout.write(self.style.WARNING('Default User Created'))
                self.stdout.write(self.style.SUCCESS(f'Username: {username}'))
                self.stdout.write(self.style.SUCCESS('Password: 12345'))

        # Flush template cache
        # TODO: test that this works, may need to move to a worker task
        cache.delete_pattern('*.decorators.cache.*')
        self.stdout.write(self.style.SUCCESS('Flushed Template Cache'))

        # Ensure SiteSettings model
        site_settings, created = SiteSettings.objects.get_or_create(pk=1)
        if created:
            self.stdout.write(self.style.WARNING('SiteSettings Created'))

        # Warm site_settings cache
        # TODO: test that this works, may need to move to a worker task
        cache.set('site_settings', model_to_dict(site_settings))
        self.stdout.write(self.style.SUCCESS('Created Cache site_settings'))

        # Delete Latest Version Cache
        # TODO: move this to an async app startup task and run check
        cache.delete('latest_version')
