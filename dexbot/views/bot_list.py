from PyQt5 import QtGui, QtWidgets, QtCore

from dexbot.views.gen.bot_list_window import Ui_MainWindow
from dexbot.views.gen.bot_item_widget import Ui_widget
from dexbot.views.create_bot import CreateBotView


class MainView(QtWidgets.QMainWindow):

    def __init__(self, model, main_ctrl):
        self.model = model
        self.main_ctrl = main_ctrl
        super(MainView, self).__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.bot_container = self.ui.verticalLayout

        self.ui.add_bot_button.clicked.connect(self.handle_add_bot)

        bots = main_ctrl.get_bots_data()
        for bot in bots:
            self.add_bot_widget()

    def add_bot_widget(self):
        widget = BotItemWidget()
        self.bot_container.addWidget(widget)
        widget.setFixedSize(widget.frameSize())

    def handle_add_bot(self):
        self.create_bot_dialog = CreateBotView(self.model, self.main_ctrl)
        return_value = self.create_bot_dialog.exec_()

        if return_value == 1:
            self.add_bot_widget()

    def refresh_bot_list(self):
        pass


class BotItemWidget(QtWidgets.QWidget, Ui_widget):

    def __init__(self):
        super(BotItemWidget, self).__init__()

        self.setupUi(self)
        self.pause_button.hide()

        self.pause_button.clicked.connect(self.pause_bot)
        self.play_button.clicked.connect(self.start_bot)
        self.remove_button.clicked.connect(self.remove_widget)

    def start_bot(self):
        self.pause_button.show()
        self.play_button.hide()

    def pause_bot(self):
        self.pause_button.hide()
        self.play_button.show()

    def remove_widget(self):
        self.deleteLater()
