from .ui.create_wallet_window_ui import Ui_Dialog
from .notice import NoticeDialog
from .errors import gui_error

from PyQt5 import QtWidgets


class CreateWalletView(QtWidgets.QDialog, Ui_Dialog):

    def __init__(self, controller):
        self.controller = controller
        super().__init__()
        self.setupUi(self)
        self.ok_button.clicked.connect(lambda: self.validate_form())

    @gui_error
    def validate_form(self):
        password = self.password_input.text()
        confirm_password = self.confirm_password_input.text()
        if not self.controller.create_wallet(password, confirm_password):
            dialog = NoticeDialog('Passwords do not match!')
            dialog.exec_()
        else:
            self.accept()
