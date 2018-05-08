import logging
import traceback

from dexbot.ui import translate_error
from dexbot.queue.idle_queue import idle_add

from PyQt5 import QtWidgets


class PyQtHandler(logging.Handler):
    """
    Logging handler for Py Qt events.
    Based on Vinay Sajip's DBHandler class (http://www.red-dove.com/python_logging.html)
    """
    def emit(self, record):
        # Use default formatting:
        self.format(record)
        message = record.msg
        extra = translate_error(message)
        if record.exc_info:
            if not extra:
                extra = translate_error(repr(record.exc_info[1]))
            detail = logging._defaultFormatter.formatException(record.exc_info)
        else:
            detail = None
        if hasattr(record, "worker_name"):
            title = "Error on {}".format(record.worker_name)
        else:
            title = "DEXBot Error"
        idle_add(show_dialog, title, message, extra, detail)


def gui_error(func):
    """A decorator for GUI handler functions - traps all exceptions and displays the dialog
    """
    def func_wrapper(obj, *args, **kwargs):
        try:
            return func(obj)
        except BaseException as exc:
            show_dialog("DEXBot Error", "An error occurred with DEXBot: \n"+repr(exc), None, traceback.format_exc())
            
    return func_wrapper


def show_dialog(title, message, extra=None, detail=None):
    msg = QtWidgets.QMessageBox()
    msg.setIcon(QtWidgets.QMessageBox.Critical)
    msg.setText(message)
    if extra:
        msg.setInformativeText(extra)
    msg.setWindowTitle(title)
    if detail:
        msg.setDetailedText(detail)
    msg.setStandardButtons(QtWidgets.QMessageBox.Ok)

    msg.exec_()

