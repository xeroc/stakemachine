from PyQt5 import QtWidgets

from dexbot.views.gen.bot_item_widget import Ui_widget


class BotItemWidget(QtWidgets.QWidget, Ui_widget):

    def __init__(self, botname, config, controller):
        super(BotItemWidget, self).__init__()

        self.running = False
        self.botname = botname
        self.config = config
        self.controller = controller

        self.setupUi(self)
        self.pause_button.hide()

        self.pause_button.clicked.connect(self.pause_bot)
        self.play_button.clicked.connect(self.start_bot)
        self.remove_button.clicked.connect(self.remove_widget)

        self.setup_ui_data(config)

    def setup_ui_data(self, config):
        botname = list(config['bots'].keys())[0]
        self.set_bot_name(botname)

        market = config['bots'][botname]['market']
        self.set_bot_market(market)

    def start_bot(self):
        self.running = True
        self.pause_button.show()
        self.play_button.hide()

        self.controller.create_bot(self.botname, self.config)

    def pause_bot(self):
        self.running = False
        self.pause_button.hide()
        self.play_button.show()

        self.controller.stop_bot(self.botname)

    def set_bot_name(self, value):
        self.botname_label.setText(value)

    def set_bot_account(self, value):
        pass

    def set_bot_market(self, value):
        self.currency_label.setText(value)

    def set_bot_profit(self, value):
        self.bot_profit.setText(value)

    def remove_widget(self):
        if self.running:
            self.controller.remove_bot(self.botname)
        self.deleteLater()
