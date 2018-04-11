import os


def mkdir(d):
    try:
        os.makedirs(d)
    except FileExistsError:
        return
    except OSError:
        raise
