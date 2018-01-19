from PyQt5 import QtGui, QtWidgets, QtCore

from dexbot.views.gen.bot_list_window import Ui_MainWindow
from dexbot.views.gen.bot_item_widget import Ui_widget
from dexbot.views.create_bot import CreateBotView


class MainView(QtWidgets.QMainWindow):

    def __init__(self, main_ctrl):
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
        create_bot_dialog = CreateBotView(self.main_ctrl)
        return_value = create_bot_dialog.exec_()

        if return_value == 1:
            self.add_bot_widget()

    def refresh_bot_list(self):
        pass





