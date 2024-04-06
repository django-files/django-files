def human_read_to_mbyte(size):
    try:
        int(size)
        return size
    except ValueError:
        pass
    factors = {'MB': 1, 'GB': 1000, 'TB': 1000000}
    if (unit := size[-2:].upper()) in factors:
        return factors[unit]*int(size[:-2])
