from django.forms.models import model_to_dict

from home.models import Files
from settings.context_processors import site_settings_processor


def extract_files(q: Files.objects):
    site_settings = site_settings_processor(None)['site_settings']
    files = []
    for file in q:
        data = model_to_dict(file, exclude=['file', 'thumb'])
        data['url'] = site_settings['site_url'] + file.preview_uri()
        data['thumb'] = site_settings['site_url'] + file.thumb_path
        data['raw'] = site_settings['site_url'] + file.raw_path
        data['date'] = file.date
        files.append(data)
    # log.debug('files: %s', files)
    return files
