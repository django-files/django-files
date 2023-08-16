import logging
from PIL import Image, ExifTags, TiffImagePlugin

from home.models import Files
from home.util.metadata import city_state_from_exif


log = logging.getLogger('celery')

# TODO: This should be a Class or proper Functions


def route(file: Files) -> Files:
    # Accepts a file and routes file to appropriate upload processor
    img_mimes = ['image/jpe', 'image/jpg', 'image/jpeg', 'image/webp']
    if file.mime in img_mimes:
        file = process_image(file)
    return file


def process_image(file: Files) -> Files:
    # processes image files, collects or strips exif, sets metadata
    with Image.open(file.file.path) as image:
        file.meta['PILImageWidth'], file.meta['PILImageHeight'] = image.size
        if file.user.remove_exif:
            strip_exif(image, file)
        else:
            log.info('Parsing and storing EXIF: %s', file.pk)
            image, exif_clean, exif = handle_exif(image, file.user.remove_exif_geo)
            # write exif in case exif modified
            image.save(file.file.path, exif=exif)
            # determine photo area from gps and store in metadata
            if area := city_state_from_exif(exif_clean.get('GPSInfo')):
                file.meta['GPSArea'] = area
            file.exif = cast(exif_clean)
    return file


def handle_exif(image: Image, strip_gps: bool) -> tuple:
    # takes an image, returns image, dictionary of exif data, and modified exif data
    # does not collect gps data if strip_gps true
    exif_clean = {}
    exif = image.getexif()
    if strip_gps:
        image, exif = strip_gps_raw_exif(image, exif)
    try:
        # get_exif tends to not have all data we need, so we call _get_exif, if that fails
        # we fail back to get_exif for all exif attrs
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


def strip_gps_raw_exif(image: Image, exif: dict) -> tuple:
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


def strip_exif(image: Image, file: Files) -> None:
    # accepts image and file, rewrites image file without exif
    log.info('Stripping EXIF: %s', file.pk)
    with Image.new(image.mode, image.size) as new:
        new.putdata(image.getdata())
        if 'P' in image.mode:
            new.putpalette(image.getpalette())
        new.save(file.file.path)
