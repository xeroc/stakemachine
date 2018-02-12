from PyQt5 import QtWidgets

from dexbot.views.gen.bot_item_widget import Ui_widget
from dexbot.views.confirmation import ConfirmationDialog
from dexbot.storage import worker


class BotItemWidget(QtWidgets.QWidget, Ui_widget):

    def __init__(self, botname, config, controller, view):
        super(BotItemWidget, self).__init__()

        self.running = False
        self.botname = botname
        self.config = config
        self.controller = controller
        self.view = view

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

        profit = worker.execute(worker.get_item, botname, 'profit')
        if profit:
            self.set_bot_profit(profit)

        percentage = worker.execute(worker.get_item, botname, 'slider')
        if percentage:
            self.set_bot_slider(percentage)

    def start_bot(self):
        self.running = True
        self.pause_button.show()
        self.play_button.hide()

        self.controller.create_bot(self.botname, self.config, self.view)

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
        if value >= 0:
            value = '+' + str(value)
        else:
            value = '-' + str(value)
        value = str(value) + '%'
        self.profit_label.setText(value)

    def set_bot_slider(self, value):
        self.order_slider.setSliderPosition(value)

    def remove_widget(self):
        dialog = ConfirmationDialog('Are you sure you want to remove bot "{}"?'.format(self.botname))
        return_value = dialog.exec_()
        if return_value:
            self.controller.remove_bot(self.botname)
            self.deleteLater()

            # Todo: Remove the line below this after multi-bot support is added
            self.view.ui.add_bot_button.setEnabled(True)
