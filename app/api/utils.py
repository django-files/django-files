from django.forms.models import model_to_dict

from home.models import Files, Albums
from settings.context_processors import site_settings_processor


def extract_files(q: Files.objects):
    site_settings = site_settings_processor(None)["site_settings"]
    files = []
    for file in q:
        data = model_to_dict(file, exclude=["file", "thumb", "albums"])
        data["url"] = site_settings["site_url"] + file.preview_uri()
        data["thumb"] = site_settings["site_url"] + file.thumb_path
        data["raw"] = site_settings["site_url"] + file.raw_path
        data["date"] = file.date
        data["albums"] = [album.id for album in Albums.objects.filter(files__id=file.id)]
        files.append(data)
    # log.debug('files: %s', files)
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
