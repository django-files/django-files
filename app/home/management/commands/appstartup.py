# import logging
# import os
# from django.core.cache import cache
# from django.core.management.base import BaseCommand
# from django.forms.models import model_to_dict
#
# from oauth.models import CustomUser
# from settings.models import SiteSettings
#
# log = logging.getLogger('app')
#
#
# def create_initial_user():
#     # default_user = 'admin'
#     # default_pass = '12345'
#     # username = os.environ.get('USERNAME')
#     # password = os.environ.get('PASSWORD')
#     # credentials_provided = bool(username and password)
#     # username = username or default_user
#     # password = password or default_pass
#
#     # username = os.environ.get('USERNAME', 'admin')
#     # password = os.environ.get('PASSWORD', '12345')
#     # local = bool(os.environ.get('USERNAME') and os.environ.get('PASSWORD'))
#        # oauth = bool(os.environ.get('OAUTH_REDIRECT_URL'))
#
#     # site_settings = SiteSettings.objects.settings()
#     # users = CustomUser.objects.all()
#
#     # # if users exist and local auth provided, create user or ensure password
#     # if not oauth or local:
#     #     CustomUser.objects.create_superuser(username=username, password=password)
#     #     log.info('Initial User Created')
#     #     log.info(f'Username: {username}')
#     #     log.info(f'Password: {password}')
#
#     # if users exist and local auth provided, create user or ensure password
#     # if credentials_provided:
#     #     if user := users.filter(username=username):
#     #         user[0].set_password(password)
#     #         log.info('Custom User Password Updated')
#     #     else:
#     #         CustomUser.objects.create_superuser(username=username, password=password)
#     #         log.info('Custom User Created')
#     # else:
#     #     # no local users exist and no oauth method provided
#     #     if not users and not oauth:
#     #         if credentials_provided:
#     #             # if local auth, create user from provided credentials
#     #             CustomUser.objects.create_superuser(username=username, password=password)
#     #             log.info('Custom User Created')
#     #             log.info(f'Username: {username}')
#     #             log.info('Password: *****')
#     #         else:
#     #             CustomUser.objects.create(
#     #                 username=default_user,
#     #                 password=default_pass,
#     #                 is_superuser=True,
#     #                 is_staff=True,
#     #                 show_setup=True,
#     #             )
#     #             log.info('Default User Created')
#     #             log.info(f'Username: {username}')
#     #             log.info('Password: 12345')
