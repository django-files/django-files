import logging
from PIL import Image, ExifTags, TiffImagePlugin

from .metadata import city_state_from_exif

log = logging.getLogger('celery')

img_mimes = ['image/jpe', 'image/jpg', 'image/jpeg', 'image/webp']


def route(file: object) -> object:
    # Accepts a file and routes file to appropriate upload processor
    if file.mime in img_mimes:
        file = process_image(file)
    return file


def process_image(file: object) -> object:
    # processes image files, collects or strips exif, sets metadata
    with Image.open(file.file.path) as image:
        file.meta['PILImageWidth'], file.meta['PILImageHeight'] = image.size
        if file.user.remove_exif:
            log.info('Stripping EXIF: %s', file.pk)
            with Image.new(image.mode, image.size) as new:
                new.putdata(image.getdata())
                if 'P' in image.mode:
                    new.putpalette(image.getpalette())
                new.save(file.file.path)
        else:
            log.info('Parsing and storing EXIF: %s', file.pk)
            image, exif_clean, exif = handle_exif(image, file.user.remove_exif_geo)
            image.save(file.file.path, exif=exif)
            # determine photo area from gps and store in metadata
            if area := city_state_from_exif(exif_clean.get('GPSInfo')):
                file.meta['GPSArea'] = area
            file.exif = cast(exif_clean)
    return file


def handle_exif(image: object, strip_gps: bool) -> list:
    # takes an image, returns dictionary of exif data
    # does not collect gps data if strip_gps true
    exif_clean = {}
    exif = image.getexif()
    if strip_gps:
        image, exif = strip_gps_raw_exif(image, exif)
    try:
        _getexif = (image._getexif() if hasattr(image, '_getexif') else None) or {}
        exif_data = {ExifTags.TAGS[k]: v for k, v in _getexif.items() if k in ExifTags.TAGS}
        for k, v in exif_data.items():
            exif_clean[k] = v.decode() if isinstance(v, bytes) else str(v)
    except Exception as error:
        log.info("Error processing exif: %s", error)
        for tag, value in exif.items():
            exif_clean[ExifTags.TAGS.get(tag, tag)] = value
    exif_clean['GPSInfo'] = exif.get_ifd(ExifTags.IFD.GPSInfo)
    return image, exif_clean, exif


def strip_gps_raw_exif(image: object, exif: object) -> list:
    # accepts raw exif object from PIL, returns object with no GPS data
    log.info('Stripping EXIF GPS')
    if 0x8825 in exif:
        del exif[0x8825]
    return image, exif


def cast(v):
    # casts exif nested json into nested dictionary
    if isinstance(v, TiffImagePlugin.IFDRational):
        return float(v)
    elif isinstance(v, tuple):
        return tuple(cast(t) for t in v)
    elif isinstance(v, bytes):
        return v.decode(errors='replace')
    elif isinstance(v, dict):
        for kk, vv in v.items():
            v[kk] = cast(vv)
        return v
    else:
        return v
