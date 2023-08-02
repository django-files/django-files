import re
import validators
from django import forms
from django.core.exceptions import ValidationError
from pytimeparse2 import parse


class SettingsForm(forms.Form):
    site_url = forms.CharField(max_length=128)
    default_expire = forms.CharField(max_length=128, required=False)
    default_color = forms.CharField(max_length=7)

    def clean_default_color(self):
        data = self.cleaned_data['default_color'].strip().lstrip('#').lower()
        print('data: ', data)
        if not re.match('^(?:[0-9a-f]{2}){3}$', data):
            raise ValidationError('Invalid Color HEX.')
        return data

    def clean_default_expire(self):
        data = self.cleaned_data['default_expire'].strip()
        print('data: ', data)
        if not data:
            return ''
        expire = parse(data)
        if not expire:
            raise ValidationError('Invalid Expiration Value.')
        return data

    def clean_site_url(self):
        data = self.cleaned_data['site_url'].strip()
        print('data: ', data)
        if not validators.url(data):
            raise ValidationError('Invalid Site URL.')
        return data
