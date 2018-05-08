from .ui.unlock_wallet_window_ui import Ui_Dialog
from .notice import NoticeDialog
from .errors import gui_error
from PyQt5 import QtWidgets


class UnlockWalletView(QtWidgets.QDialog):

    def __init__(self, controller):
        self.controller = controller
        super().__init__()
        self.ui = Ui_Dialog()
        self.ui.setupUi(self)
        self.ui.ok_button.clicked.connect(self.validate_form)

    @gui_error
    def validate_form(self):
        password = self.ui.password_input.text()
        if not self.controller.unlock_wallet(password):
            dialog = NoticeDialog('Invalid password!')
            dialog.exec_()
            self.ui.password_input.setText('')
        else:
            self.accept()
