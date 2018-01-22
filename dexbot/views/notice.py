from PyQt5 import QtWidgets

from dexbot.views.gen.notice_window import Ui_Dialog


class NoticeDialog(QtWidgets.QDialog):

    def __init__(self, text):
        super().__init__()
        self.ui = Ui_Dialog()
        self.ui.setupUi(self)

        self.ui.notice_label.setText(text)
        self.ui.ok_button.clicked.connect(self.accept)
