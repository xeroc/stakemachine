import logging
import traceback

from dexbot.qt_queue.idle_queue import idle_add
from dexbot.ui import translate_error
from PyQt5 import QtCore, QtWidgets

from .ui.error_dialog_ui import Ui_Dialog


class PyQtHandler(logging.Handler):
    """
    Logging handler for Py Qt events.

    Based on Vinay Sajip's DBHandler class (http://www.red-dove.com/python_logging.html)
    """

    def __init__(self):
        logging.Handler.__init__(self)
        self.info_handler = None

    def emit(self, record):
        # Use default formatting:
        self.format(record)
        message = record.msg
        if record.levelno > logging.WARNING:
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
        else:
            if self.info_handler and hasattr(record, "worker_name"):
                idle_add(self.info_handler, record.worker_name, record.levelno, message)

    def set_info_handler(self, info_handler):
        self.info_handler = info_handler


class ErrorDialog(QtWidgets.QDialog, Ui_Dialog):
    def __init__(self, title, message, extra=None, detail=None):
        super().__init__()
        self.setupUi(self)

        self.resize(400, 1)
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.WindowCloseButtonHint | QtCore.Qt.WindowMinimizeButtonHint)

        self.setWindowTitle('DEXBot - {}'.format(title))
        self.message_label.setText(message)

        self.hide_details.hide()
        self.detail_box.hide()

        if extra:
            self.extra_label.setText(extra)

        if detail:
            self.detail_box.setText(detail)
        else:
            self.show_details.hide()

        # Button actions
        self.hide_details.clicked.connect(lambda: self.hide_details_func())
        self.show_details.clicked.connect(lambda: self.show_details_func())
        self.ok_button.clicked.connect(lambda: self.accept())

    def show_details_func(self):
        self.detail_box.show()
        self.show_details.hide()
        self.hide_details.show()
        self.vertical_spacer.hide()
        self.resize(self.geometry().width(), 300)

    def hide_details_func(self):
        self.detail_box.hide()
        self.hide_details.hide()
        self.show_details.show()
        self.vertical_spacer.show()
        self.resize(self.geometry().width(), 1)


def gui_error(func):
    """ A decorator for GUI handler functions - traps all exceptions and displays the dialog
    """

    def func_wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except BaseException as exc:
            show_dialog("DEXBot Error", "An error occurred with DEXBot: \n" + repr(exc), None, traceback.format_exc())

    return func_wrapper


def show_dialog(title, message, extra=None, detail=None):
    error_dialog = ErrorDialog(title, message, extra, detail)
    error_dialog.exec_()
