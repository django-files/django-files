import logging
from math import log10, floor


def anytobool(value):
    logging.debug('true_false: %s', value)
    if not isinstance(value, str):
        return bool(value)
    logging.debug('value: %s', value)
    if value.lower() in ['true', 'yes', 'on', '1']:
        return True
    logging.debug('FAIL')
    return False


def human_read_to_byte(size):
    try:
        return int(size)
    except ValueError:
        pass
    factors = {'B': 0, 'KB': 1, 'MB': 2, 'GB': 3, 'TB': 4, 'PB': 5, 
               'K': 1, 'M': 2, 'G': 3, 'T': 4, 'P': 5}
    try:
        if not any(c.isdigit() for c in size[-2:]):
            unit, size = size[-2:], size[:-2]
        elif not any(c.isdigit() for c in size[-1:]):
            unit, size = size[-1:], size[:-1]
        unit, size = unit.strip().upper(), size.strip()
        return int(float(size)* pow(1000, factors[unit]))
    except ValueError:
        # if we are unable to extract float, the input is invalid, form will raise validation error on None
        return


def bytes_to_human_read(size) -> str:
    if size:
        factors = ['B', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB']
        factor = floor(log10(size)/3)
        return f'{size * pow(10, -factor * 3):.2f} {factors[factor]}'
    return '0'
