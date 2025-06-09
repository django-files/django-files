from typing import Any, Dict, List

from django.forms.models import model_to_dict
from home.models import Albums, Files
from oauth.models import CustomUser
from settings.context_processors import site_settings_processor


def serialize_user(user: CustomUser) -> Dict[str, Any]:
    """
    Serialize a user instance into a dictionary with consistent exclusions and additions.

    Args:
        user: CustomUser instance to serialize

    Returns:
        Dict containing user data with password and authorization excluded, and avatar_url added
    """
    user_dict = model_to_dict(user, exclude=["password", "authorization"])
    user_dict["avatar_url"] = user.get_avatar_url()
    return user_dict


def serialize_users(users: List[CustomUser]) -> List[Dict[str, Any]]:
    """
    Serialize a list of user instances into a list of dictionaries.

    Args:
        users: List of CustomUser instances to serialize

    Returns:
        List of dictionaries containing user data
    """
    return [serialize_user(user) for user in users]


def extract_files(q: Files.objects):
    site_settings = site_settings_processor(None)["site_settings"]
    files = []
    for file in q:
        data = model_to_dict(file, exclude=["file", "thumb", "albums"])
        data["user_name"] = file.user.get_name()
        data["user_username"] = file.user.username

        data["url"] = site_settings["site_url"] + file.preview_uri()
        data["thumb"] = site_settings["site_url"] + file.thumb_path
        data["raw"] = site_settings["site_url"] + file.raw_path
        data["date"] = file.date
        data["albums"] = [album.id for album in Albums.objects.filter(files__id=file.id)]
        files.append(data)
    return files


def extract_albums(q: Albums.objects):
    site_settings = site_settings_processor(None)["site_settings"]
    albums = []
    for album in q:
        data = model_to_dict(album)
        data["date"] = album.date
        data["url"] = site_settings["site_url"] + "/gallery?album=" + str(album.id)
        albums.append(data)
    return albums
