import logging


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
        int(size)
        return size
    except ValueError:
        pass
    factors = {'KB': 1000, 'MB': 1000000, 'GB': 1000000000, 'TB': 1000000000}
    if (unit := size[-2:].upper()) in factors:
        return factors[unit]*int(size[:-2])


def bytes_to_human_read(size):
    factors = ['B', 'KB', 'MB', 'GB', 'TB']
    factor = 0
    while size > 1000:
        factor += 1
        size = size // 1000
    return f'{size} {factors[factor]}'
