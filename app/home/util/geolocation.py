import logging
from geopy.geocoders import Nominatim
from typing import Tuple

log = logging.getLogger('app')

# TODO: This should probably be a Class also


def city_state_from_exif(gps_ifd: dict) -> str:
    try:
        geolocator = Nominatim(user_agent='django-files')
        lat, lon = dms_to_degrees(gps_ifd)
        log.debug('lat: %s', lat)
        log.debug('lon: %s', lon)
        location = geolocator.reverse((lat, lon))
        log.info('-'*20)
        log.info(location)
        log.info('-'*20)
        if not (area := location.raw['address'].get('city')):
            area = location.raw['address'].get('county')
        state = location.raw['address'].get('state', '')
        return f"{area}, {state}"
    except Exception as error:
        log.error(error)
        return ''


def dms_to_degrees(gps_ifd: dict) -> Tuple[float, float]:
    dn, mn, sn = gps_ifd[2]
    dw, mw, sw = gps_ifd[4]
    lat_deg = dn + mn / 60 + sn / 3600
    lon_deg = dw + mw / 60 + sw / 3600
    return lat_deg, -lon_deg
