import logging
from geopy.geocoders import Nominatim
from typing import Tuple

log = logging.getLogger('app')

# TODO: This should probably be a Class or merged into one


def city_state_from_exif(gps_ifd: dict) -> str:
    # TODO: Possibly fix try/expect
    try:
        geolocator = Nominatim(user_agent='django-files')
        location = geolocator.reverse(dms_to_degrees(gps_ifd))
        location_strings = []
        if location.raw['address'].get('city', None):
            location_strings.append(location.raw['address'].get('city'))
        else:
            filter(None, location_strings.append(location.raw['address'].get('county')))
        filter(None, location_strings.append(location.raw['address'].get('state', '')))
        filter(None, location_strings.append(location.raw['address'].get('country', '')))
        return ", ".join(location_strings)
    except Exception as error:
        log.info(error)
        return ''


def dms_to_degrees(gps_ifd: dict) -> Tuple[float, float]:
    dn, mn, sn = gps_ifd[2]
    dw, mw, sw = gps_ifd[4]
    lat_deg = dn + mn / 60 + sn / 3600
    lon_deg = dw + mw / 60 + sw / 3600
    return lat_deg, -lon_deg
