from PyQt5 import QtGui, QtWidgets, QtCore

from dexbot.views.gen.create_bot_window import Ui_Dialog


class CreateBotView(QtWidgets.QDialog):

    def __init__(self, controller):
        self.controller = controller
        super(CreateBotView, self).__init__()
        self.ui = Ui_Dialog()
        self.ui.setupUi(self)

        botname = controller.get_unique_bot_name()
        self.ui.botname_input.setText(botname)

        self.ui.save_button.clicked.connect(self.handle_save)
        self.ui.cancel_button.clicked.connect(self.handle_cancel)

    def validate_form(self):
        return True

    def handle_save(self):
        if not self.validate_form():
            # Todo: add validation error notice for user
            return
        self.botname = self.ui.botname_input.getText()
        bot_data = {
            'account': self.ui.account_input,
            'market': '',
            'module': '',
            'bot': ''
        }
        self.controller.add_bot_config(self.botname, bot_data)
        self.accept()

    def handle_cancel(self):
        self.reject()
