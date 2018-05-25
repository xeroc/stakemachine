from .ui.unlock_wallet_window_ui import Ui_Dialog
from .notice import NoticeDialog
from .errors import gui_error

from PyQt5 import QtWidgets


class UnlockWalletView(QtWidgets.QDialog, Ui_Dialog):

    def __init__(self, controller):
        self.controller = controller
        super().__init__()
        self.setupUi(self)
        self.ok_button.clicked.connect(lambda: self.validate_form())

    @gui_error
    def validate_form(self):
        password = self.password_input.text()
        if not self.controller.unlock_wallet(password):
            dialog = NoticeDialog('Invalid password!')
            dialog.exec_()
            self.password_input.setText('')
        else:
            self.accept()
