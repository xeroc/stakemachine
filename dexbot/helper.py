import os
import shutil
import errno
import logging
from appdirs import user_data_dir

from dexbot import APP_NAME, AUTHOR


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


def initialize_orders_log():
    """ Creates .csv log file, adds the headers first time only
    """
    data_dir = user_data_dir(APP_NAME, AUTHOR)
    filename = data_dir + '/orders.csv'
    file = os.path.isfile(filename)

    formatter = logging.Formatter('%(message)s')
    logger = logging.getLogger("dexbot.orders_log")

    file_handler = logging.FileHandler(filename)
    file_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.setLevel(logging.INFO)

    if not file:
        logger.info("ID;operation_type;base_asset;base_amount;quote_asset;quote_amount;timestamp")
