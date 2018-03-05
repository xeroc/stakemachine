from .ui.create_wallet_window_ui import Ui_Dialog
from .notice import NoticeDialog

from PyQt5 import QtWidgets


class CreateWalletView(QtWidgets.QDialog):

    def __init__(self, controller):
        self.controller = controller
        super().__init__()
        self.ui = Ui_Dialog()
        self.ui.setupUi(self)
        self.ui.ok_button.clicked.connect(self.validate_form)

    def validate_form(self):
        password = self.ui.password_input.text()
        confirm_password = self.ui.confirm_password_input.text()
        if not self.controller.create_wallet(password, confirm_password):
            dialog = NoticeDialog('Passwords do not match!')
            dialog.exec_()
        else:
            self.accept()
