import re
import validators
from django import forms
from django.core.exceptions import ValidationError
from pytimeparse2 import parse


class SettingsForm(forms.Form):
    site_url = forms.CharField(max_length=128)
    default_expire = forms.CharField(max_length=128, required=False)
    default_color = forms.CharField(max_length=7)
    nav_color_1 = forms.CharField(max_length=7)
    nav_color_2 = forms.CharField(max_length=7)
    remove_exif_geo = forms.BooleanField(required=False)
    remove_exif = forms.BooleanField(required=False)
    show_exif_preview = forms.BooleanField(required=False)
    s3_bucket_name = forms.CharField(max_length=128, required=False)

    def clean_default_color(self):
        data = self.cleaned_data['default_color'].strip().lower()
        if not re.match('^#(?:[0-9a-f]{2}){3}$', data):
            raise ValidationError('Invalid Color HEX.')
        return data

    def clean_nav_color_1(self):
        data = self.cleaned_data['nav_color_1'].strip().lower() or '#130e36'
        if not re.match('^#(?:[0-9a-f]{2}){3}$', data):
            raise ValidationError('Invalid Color HEX.')
        return data

    def clean_nav_color_2(self):
        data = self.cleaned_data['nav_color_2'].strip().lower() or '#1e1c21'
        if not re.match('^#(?:[0-9a-f]{2}){3}$', data):
            raise ValidationError('Invalid Color HEX.')
        return data

    def clean_default_expire(self):
        data = self.cleaned_data['default_expire'].strip()
        if not data:
            return ''
        expire = parse(data)
        if not expire:
            raise ValidationError('Invalid Expiration Value.')
        return data

    def clean_site_url(self):
        data = self.cleaned_data['site_url'].strip()
        if not validators.url(data):
            raise ValidationError('Invalid Site URL.')
        return data.rstrip('/')
