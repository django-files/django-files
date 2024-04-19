import logging
import os
from PIL import Image, ExifTags, TiffImagePlugin, ImageOps
from django.core.files import File
from io import BytesIO

from home.util.geolocation import city_state_from_exif
from home.models import Files

log = logging.getLogger('app')


class ImageProcessor(object):

    def __init__(self, local_path: str, default_remove_exif: bool, default_exif_geo: bool, ctx):
        self.local_path = local_path
        if ctx.get('strip_exif') is not None:
            self.remove_exif = ctx.get('strip_exif')
        else:
            self.remove_exif = default_remove_exif
        if ctx.get('strip_gps') is not None:
            self.remove_exif_geo = ctx.get('strip_gps')
        else:
            self.remove_exif_geo = default_exif_geo
        self.exif = {}
        self.meta = {}
        self.tmp_thumb = os.path.splitext(self.local_path)[0] + "_thumb" + os.path.splitext(self.local_path)[1]

    def process_file(self) -> None:
        # TODO: Concatenate Logic to This Function
        # processes image files, collects or strips exif, sets metadata
        with Image.open(self.local_path) as image:
            self.meta['PILImageWidth'], self.meta['PILImageHeight'] = image.size
            if self.remove_exif:
                return self.strip_exif(image, self.local_path)
            log.info('Parsing and storing EXIF: %s', self.local_path)
            image, exif_clean, exif = self._handle_exif(image)
            # write exif in case exif modified
            image.save(self.local_path, exif=exif)
            # determine photo area from gps and store in metadata
            if area := city_state_from_exif(exif_clean.get('GPSInfo')):
                self.meta['GPSArea'] = area
            self.exif = self.cast(exif_clean)

    def _handle_exif(self, image: Image) -> tuple:
        # TODO: Remove Basic Logic from here and put it all in one function
        # takes an image, returns image, dictionary of exif data, and modified exif data
        # does not collect gps data if strip_gps true
        exif_clean = {}
        exif = image.getexif()
        if self.remove_exif_geo:
            image, exif = self.strip_gps_raw_exif(image, exif)
        try:
            # get_exif tends to not have all data we need, so we call _get_exif, if that fails
            # we fail back to get_exif for all exif attrs
            _getexif = image._getexif() if hasattr(image, '_getexif') else {}
            exif_data = {ExifTags.TAGS[k]: v for k, v in _getexif.items() if k in ExifTags.TAGS}
            for k, v in exif_data.items():
                exif_clean[k] = v.decode() if isinstance(v, bytes) else str(v)
        except Exception as error:
            log.info("Error processing exif: %s", error)
            for tag, value in exif.items():
                exif_clean[ExifTags.TAGS.get(tag, tag)] = value
        exif_clean['GPSInfo'] = exif.get_ifd(ExifTags.IFD.GPSInfo)
        return image, exif_clean, exif

    @classmethod
    def cast(cls, v):
        # casts exif nested json into nested dictionary
        if isinstance(v, TiffImagePlugin.IFDRational):
            return float(v)
        elif isinstance(v, tuple):
            return tuple(cls.cast(t) for t in v)
        elif isinstance(v, bytes):
            return v.decode(errors='replace')
        elif isinstance(v, dict):
            for kk, vv in v.items():
                v[kk] = cls.cast(vv)
            return v
        else:
            return v

    @staticmethod
    def strip_gps_raw_exif(image: Image, exif: dict) -> tuple:
        # accepts raw exif object from PIL, returns object with no GPS data
        log.info('Stripping EXIF GPS')
        if 0x8825 in exif:
            del exif[0x8825]
        return image, exif

    @staticmethod
    def strip_exif(image: Image, local_path: str) -> None:
        # accepts image and file, rewrites image file without exif
        log.info('Stripping EXIF: %s', local_path)
        with Image.new(image.mode, image.size) as new:
            new.putdata(image.getdata())
            if 'P' in image.mode:
                new.putpalette(image.getpalette())
            new.save(local_path)


def thumbnail_processor(file: Files, file_bytes: bytes = None):
    # generate thumbnail via bytes object or file object
    # prefer bytes object if file is still local to avoid wasteful redownload of file
    tmp_file = f'/tmp/thumb_{file.name}'
    file_bytes = BytesIO(file_bytes) if file_bytes else BytesIO(file.file.read())
    with Image.open(file_bytes) as image:
        image = ImageOps.exif_transpose(image)
        # TODO: check resolution is not already small, if it is don't bother generating a thumbnail
        image.thumbnail((512, 512))
        image.save(tmp_file)
    with open(tmp_file, 'rb') as thumb:
        # we cannot call update, we must explicitly save, here since the hooks that upload the file will not happen
        file.thumb = File(thumb, name=file.name)
        file.save()
    os.remove(tmp_file)
