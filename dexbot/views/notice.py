from .ui.notice_window_ui import Ui_Dialog

from PyQt5 import QtWidgets


class NoticeDialog(QtWidgets.QDialog):

    def __init__(self, text):
        super().__init__()
        self.ui = Ui_Dialog()
        self.ui.setupUi(self)

        self.ui.notice_label.setText(text)
        self.ui.ok_button.clicked.connect(lambda: self.accept())
