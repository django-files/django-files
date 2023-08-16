import logging
from geopy.geocoders import Nominatim
from typing import Optional, Tuple

log = logging.getLogger('app')

# TODO: This should probably be a Class or merged into one


def city_state_from_exif(gps_ifd: dict) -> str:
    # TODO: Possibly fix try/expect
    try:
        geolocator = Nominatim(user_agent='django-files')
        lat_lon = dms_to_degrees(gps_ifd)
        location = geolocator.reverse(lat_lon)
        if not (area := location.raw['address'].get('city')):
            area = location.raw['address'].get('county')
        state = location.raw['address'].get('state', '')
        return f'{area}, {state}'
    except Exception as error:
        log.info(error)
        return ''


def dms_to_degrees(gps_ifd: dict) -> Optional[Tuple[float, float]]:
    # TODO: This should not be a try/expect, but upstream does not handle it
    try:
        dn, mn, sn = gps_ifd[2]
        dw, mw, sw = gps_ifd[4]
        lat_deg = dn + mn / 60 + sn / 3600
        lon_deg = dw + mw / 60 + sw / 3600
        return lat_deg, -lon_deg
    except Exception as error:
        log.info(error)
