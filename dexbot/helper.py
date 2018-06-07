import os
import shutil
import errno


def mkdir(d):
    try:
        os.makedirs(d)
    except FileExistsError:
        return
    except OSError:
        raise


def remove(path):
    """ Removes a file or a directory even if they don't exist
    """
    if os.path.isfile(path):
        try:
            os.remove(path)
        except OSError as e:
            if e.errno != errno.ENOENT:
                raise
    elif os.path.isdir(path):
        try:
            shutil.rmtree(path)
        except FileNotFoundError:
            return
