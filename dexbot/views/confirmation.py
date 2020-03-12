from PyQt5 import QtWidgets

from .ui.confirmation_window_ui import Ui_Dialog


class ConfirmationDialog(QtWidgets.QDialog):
    def __init__(self, text):
        super().__init__()
        self.ui = Ui_Dialog()
        self.ui.setupUi(self)

        self.ui.confirmation_label.setText(text)
