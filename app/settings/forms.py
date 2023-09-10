import re
import validators
import zoneinfo
from django import forms
from oauth.models import CustomUser
from django.core.exceptions import ValidationError
from pytimeparse2 import parse


class SiteSettingsForm(forms.Form):
    site_url = forms.CharField(max_length=128)
    site_title = forms.CharField(max_length=64)
    site_description = forms.CharField(max_length=155)
    site_color = forms.CharField(max_length=7)
    oauth_reg = forms.BooleanField(required=False)
    pub_load = forms.BooleanField(required=False)
    two_factor = forms.BooleanField(required=False)
    duo_auth = forms.BooleanField(required=False)
    s3_bucket_name = forms.CharField(max_length=128, required=False)

    def clean_site_color(self):
        return is_hex(self.cleaned_data['site_color'].strip().lower())

    def clean_site_url(self):
        data = self.cleaned_data['site_url'].strip()
        if not validators.url(data):
            raise ValidationError('Invalid Site URL.')
        return data.rstrip('/')


class UserSettingsForm(forms.Form):
    first_name = forms.CharField(max_length=128, required=False)
    timezone = forms.ChoiceField(choices=zip(zoneinfo.available_timezones(), zoneinfo.available_timezones()))
    default_expire = forms.CharField(max_length=128, required=False)
    default_color = forms.CharField(max_length=7)
    nav_color_1 = forms.CharField(max_length=7)
    nav_color_2 = forms.CharField(max_length=7)
    remove_exif_geo = forms.BooleanField(required=False)
    remove_exif = forms.BooleanField(required=False)
    show_exif_preview = forms.BooleanField(required=False)
    default_file_private = forms.BooleanField(required=False)
    default_file_password = forms.BooleanField(required=False)
    default_upload_name_format = forms.ChoiceField(choices=CustomUser.UploadNameFormats.choices)

    def clean_default_color(self):
        return is_hex(self.cleaned_data['default_color'].strip().lower())

    def clean_nav_color_1(self):
        return is_hex(self.cleaned_data['nav_color_1'].strip().lower() or '#130e36')

    def clean_nav_color_2(self):
        return is_hex(self.cleaned_data['nav_color_2'].strip().lower() or '#1e1c21')

    def clean_default_expire(self):
        data = self.cleaned_data['default_expire'].strip()
        if not data:
            return ''
        expire = parse(data)
        if not expire:
            raise ValidationError('Invalid Expiration Value.')
        return data


def is_hex(color: str) -> str:
    if not re.match('^#(?:[0-9a-f]{2}){3}$', color):
        raise ValidationError('Invalid Color HEX.')
    return color
