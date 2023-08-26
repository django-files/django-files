import logging
from PIL import Image, ExifTags, TiffImagePlugin

from home.util.geolocation import city_state_from_exif

log = logging.getLogger('app')


class ImageProcessor(object):

    def __init__(self, local_path: str, remove_exif: bool, remove_exif_geo: bool):
        self.local_path = local_path
        self.remove_exif = remove_exif
        self.remove_exif_geo = remove_exif_geo
        self.exif = {}
        self.meta = {}

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
