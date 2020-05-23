from PyQt5 import QtWidgets

from .ui.notice_window_ui import Ui_Dialog


class NoticeDialog(QtWidgets.QDialog, Ui_Dialog):
    def __init__(self, text):
        super().__init__()
        self.setupUi(self)

        self.notice_label.setText(text)
        self.ok_button.clicked.connect(lambda: self.accept())
