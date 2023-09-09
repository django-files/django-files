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
