import logging
from geopy.geocoders import Nominatim


log = logging.getLogger('app')

# TODO: Fix this mess


def city_state_from_exif(gps_ifd: dict) -> str:
    geolocator = Nominatim(user_agent='django-files')
    try:
        dn, mn, sn, dw, mw, sw = strip_dms(gps_ifd)
        dms_string = f"{int(dn)}°{int(mn)}'{sn}\" N, \
        {int(dw) if dw is not None else ''}°{int(mw) if mw is not None else ''}'{sw if sw is not None else ''}\" W"
        location = geolocator.reverse(dms_string)
        if not (area := location.raw['address'].get('city')):
            area = location.raw['address'].get('county')
        state = location.raw['address'].get('state', '')
        return f"{area}, {state}"
    except Exception as error:
        log.error(error)
        return ''


def strip_dms(gps_ifd: dict) -> list:
    try:
        dn, mn, sn = gps_ifd[2]
        dw, mw, sw = gps_ifd[4]
        return [dn, mn, sn, dw, mw, sw]
    except Exception as error:
        log.error(error)
        return []
