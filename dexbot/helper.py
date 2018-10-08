import os
import math
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


def truncate(number, decimals):
    """ Change the decimal point of a number without rounding

        :param float | number: A float number to be cut down
        :param int | decimals: Number of decimals to be left to the float number
        :return: Price with specified precision
    """
    return math.floor(number * 10 ** decimals) / 10 ** decimals


def get_data_directory():
    """ Returns the data directory path which contains history, sql and logs
    """
    return user_data_dir(APP_NAME, AUTHOR)


def initialize_orders_log():
    """ Creates .csv log file, adds the headers first time only
    """
    data_dir = get_data_directory()
    filename = os.path.join(data_dir, 'history.csv')
    file = os.path.isfile(filename)

    formatter = logging.Formatter('%(message)s')
    logger = logging.getLogger("dexbot.orders_log")

    file_handler = logging.FileHandler(filename)
    file_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.setLevel(logging.INFO)

    if not file:
        logger.info("worker_name;ID;operation_type;base_asset;base_amount;quote_asset;quote_amount;timestamp")


try:
    # Unfortunately setuptools is only "kinda-sorta" a standard module
    # it's available on pretty much any modern Python system, but some embedded Pythons may not have it
    # so we make it a soft-dependency
    import pkg_resources

    def find_external_strategies():
        """Use setuptools introspection to find third-party strategies the user may have installed.
        Packages that provide a strategy should export a setuptools "entry point" (see setuptools docs)
        with group "dexbot.strategy", "name" is the display name of the strategy. 
        Only set the module not any attribute (because it would always be a class called "Strategy")
        If you want a handwritten graphical UI, define "Ui_Form" and "StrategyController" in the same module

        yields a 2-tuple: description, module name"""
        for entry_point in pkg_resources.iter_entry_points("dexbot.strategy"):
            yield (entry_point.name, entry_point.module_name)

except ImportError:
    # Our system doesn't have setuptools, so no way to find external strategies
    def find_external_strategies():
        return []
