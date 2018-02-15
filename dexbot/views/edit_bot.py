from PyQt5 import QtWidgets

from dexbot.views.notice import NoticeDialog
from dexbot.view.gen.edit_bot_window import Ui_Dialog

class EditBotView(QtWidgets.QDialog):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller

        self.ui = Ui_Dialog()
        self.ui.setupUi(self)
