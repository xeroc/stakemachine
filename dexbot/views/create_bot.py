from PyQt5 import QtGui, QtWidgets, QtCore

from dexbot.views.gen.create_bot_window import Ui_Dialog


class CreateBotView(QtWidgets.QDialog):

    def __init__(self, model, main_ctrl):
        self.model = model
        self.main_ctrl = main_ctrl
        super(CreateBotView, self).__init__()
        self.ui = Ui_Dialog()
        self.ui.setupUi(self)

        self.ui.save_button.clicked.connect(self.handle_save)
        self.ui.cancel_button.clicked.connect(self.handle_cancel)

    def handle_save(self):
        self.accept()

    def handle_cancel(self):
        self.reject()
