from .ui.settings_window_ui import Ui_settings_dialog
from dexbot.controllers.settings_controller import SettingsController

from PyQt5 import QtWidgets


class SettingsView(QtWidgets.QDialog, Ui_settings_dialog):

    def __init__(self):
        super().__init__()

        # Initialize view controller
        controller = SettingsController()

        self.setupUi(self)

        # Add items to list
