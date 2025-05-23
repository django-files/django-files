import logging
import re
import zoneinfo

import validators
from django import forms
from django.core.exceptions import ValidationError
from home.util.misc import human_read_to_byte
from oauth.models import CustomUser
from pytimeparse2 import parse


log = logging.getLogger("app")


class SiteSettingsForm(forms.Form):
    site_url = forms.CharField(max_length=128)
    site_title = forms.CharField(max_length=64)
    timezone = forms.ChoiceField(
        choices=zip(zoneinfo.available_timezones(), zoneinfo.available_timezones(), strict=False)
    )
    site_description = forms.CharField(max_length=155)
    site_color = forms.CharField(max_length=7)
    oauth_reg = forms.BooleanField(required=False)
    local_auth = forms.BooleanField(required=False)
    pub_load = forms.BooleanField(required=False)
    pub_album = forms.IntegerField(required=False)
    two_factor = forms.BooleanField(required=False)
    duo_auth = forms.BooleanField(required=False)
    site_animations = forms.BooleanField(required=False)
    s3_bucket_name = forms.CharField(max_length=128, required=False)
    global_storage_quota = forms.CharField(max_length=128, required=False)
    default_user_storage_quota = forms.CharField(max_length=128, required=False)
    login_background = forms.CharField(max_length=16, required=False)
    background_video = forms.CharField(max_length=255, required=False)
    background_picture = forms.CharField(max_length=255, required=False)
    tsparticles_enabled = forms.BooleanField(required=False)
    tsparticles_config = forms.CharField(max_length=255, required=False)

    def clean_pub_album(self):
        data = self.cleaned_data["pub_album"]
        log.debug("data: %s", data)
        log.debug("type(data): %s", type(data))
        if not data:
            return 0
        return int(data)

    def clean_global_storage_quota(self):
        data = self.cleaned_data["global_storage_quota"]
        if not data:
            return 0
        quota_bytes = human_read_to_byte(data)
        if not isinstance(quota_bytes, int):
            raise ValidationError("Invalid byte value.")
        return quota_bytes

    def clean_default_user_storage_quota(self):
        data = self.cleaned_data["default_user_storage_quota"]
        if not data:
            return 0
        quota_bytes = human_read_to_byte(data)
        if not isinstance(quota_bytes, int):
            raise ValidationError("Invalid byte value.")
        return quota_bytes

    def clean_site_color(self):
        return is_hex(self.cleaned_data["site_color"].strip().lower())

    def clean_site_url(self):
        data = self.cleaned_data["site_url"].strip()
        if not validators.url(data, simple_host=True):
            raise ValidationError("Invalid Site URL.")
        return data.rstrip("/")


class UserSettingsForm(forms.Form):
    first_name = forms.CharField(max_length=128, required=False)
    timezone = forms.ChoiceField(
        choices=zip(zoneinfo.available_timezones(), zoneinfo.available_timezones(), strict=False)
    )
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
    user_avatar_choice = forms.ChoiceField(choices=CustomUser.UserAvatarChoices.choices)

    def clean_default_color(self):
        return is_hex(self.cleaned_data["default_color"].strip().lower())

    def clean_nav_color_1(self):
        return is_hex(self.cleaned_data["nav_color_1"].strip().lower() or "#130e36")

    def clean_nav_color_2(self):
        return is_hex(self.cleaned_data["nav_color_2"].strip().lower() or "#1e1c21")

    def clean_default_expire(self):
        data = self.cleaned_data["default_expire"].strip()
        if not data:
            return ""
        expire = parse(data)
        if not expire:
            raise ValidationError("Invalid expiration value.")
        return data


class WelcomeForm(forms.Form):
    username = forms.CharField(max_length=128, strip=True)
    password = forms.CharField(min_length=6, max_length=128, strip=True, required=False)
    site_url = forms.CharField(max_length=255, strip=True, required=False)
    timezone = forms.ChoiceField(
        choices=zip(zoneinfo.available_timezones(), zoneinfo.available_timezones(), strict=False)
    )

    def clean_site_url(self):
        data = self.cleaned_data["site_url"]
        if data:
            if not validators.url(data, simple_host=True):
                raise ValidationError("Invalid Site URL.")
            return data.rstrip("/")
        return None


def is_hex(color: str) -> str:
    if not re.match("^#(?:[0-9a-f]{2}){3}$", color):
        raise ValidationError("Invalid Color HEX.")
    return color
