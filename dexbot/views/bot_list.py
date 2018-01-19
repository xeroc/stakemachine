from PyQt5 import QtGui, QtWidgets, QtCore

from dexbot.queue.queue_dispatcher import ThreadDispatcher
from dexbot.views.gen.bot_list_window import Ui_MainWindow
from dexbot.views.create_bot import CreateBotView

from dexbot.views.bot_item import BotItemWidget


class MainView(QtWidgets.QMainWindow):

    bot_widgets = dict()

    def __init__(self, main_ctrl):
        self.main_ctrl = main_ctrl
        super(MainView, self).__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.bot_container = self.ui.verticalLayout

        self.ui.add_bot_button.clicked.connect(self.handle_add_bot)

        # Load bot widgets from config file
        bots = main_ctrl.get_bots_data()
        for botname in bots:
            config = self.main_ctrl.get_bot_config(botname)
            self.add_bot_widget(botname, config)

        # Dispatcher polls for events from the bots that are used to change the ui
        self.dispatcher = ThreadDispatcher(self)
        self.dispatcher.start()

    def add_bot_widget(self, botname, config):
        widget = BotItemWidget(botname, config, self.main_ctrl)
        widget.setFixedSize(widget.frameSize())
        self.bot_container.addWidget(widget)
        self.bot_widgets['botname'] = widget

    def handle_add_bot(self):
        create_bot_dialog = CreateBotView(self.main_ctrl)
        return_value = create_bot_dialog.exec_()

        # User clicked save
        if return_value == 1:
            botname = create_bot_dialog.botname
            config = self.main_ctrl.get_bot_config(botname)
            self.add_bot_widget(botname, config)

    def refresh_bot_list(self):
        pass

    def set_bot_name(self, bot_id, value):
        self.bot_widgets[bot_id].set_bot_name(value)

    def set_bot_account(self, bot_id, value):
        self.bot_widgets[bot_id].set_bot_account(value)

    def set_bot_profit(self, bot_id, value):
        self.bot_widgets[bot_id].set_bot_profit(value)

    def set_bot_market(self, bot_id, value):
        self.bot_widgets[bot_id].set_bot_market(value)

    def customEvent(self, event):
        # Process idle_queue_dispatcher events
        event.callback()
