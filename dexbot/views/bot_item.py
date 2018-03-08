from .ui.bot_item_widget_ui import Ui_widget
from .confirmation import ConfirmationDialog
from .edit_bot import EditBotView
from dexbot.storage import worker
from dexbot.controllers.create_bot_controller import CreateBotController

from PyQt5 import QtWidgets


class BotItemWidget(QtWidgets.QWidget, Ui_widget):

    def __init__(self, botname, config, main_ctrl, view):
        super(BotItemWidget, self).__init__()

        self.main_ctrl = main_ctrl
        self.running = False
        self.botname = botname
        self.config = config
        self.controller = main_ctrl
        self.view = view

        self.setupUi(self)
        self.pause_button.hide()

        self.pause_button.clicked.connect(self.pause_bot)
        self.play_button.clicked.connect(self.start_bot)
        self.remove_button.clicked.connect(self.remove_widget_dialog)
        self.edit_button.clicked.connect(self.handle_edit_bot)

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

        value = str(value) + '%'
        self.profit_label.setText(value)

    def set_bot_slider(self, value):
        self.order_slider.setSliderPosition(value)

    def remove_widget_dialog(self):
        dialog = ConfirmationDialog('Are you sure you want to remove bot "{}"?'.format(self.botname))
        return_value = dialog.exec_()
        if return_value:
            self.remove_widget()

    def remove_widget(self):
        self.controller.remove_bot(self.botname)
        self.deleteLater()

        # Todo: Remove the line below this after multi-bot support is added
        self.view.ui.add_bot_button.setEnabled(True)

    def handle_edit_bot(self):
        controller = CreateBotController(self.main_ctrl)
        edit_bot_dialog = EditBotView(controller, self.botname, self.config)
        return_value = edit_bot_dialog.exec_()

        # User clicked save
        if return_value == 1:
            bot_name = edit_bot_dialog.bot_name
            config = self.main_ctrl.get_bot_config(bot_name)
            self.remove_widget()
            self.view.add_bot_widget(bot_name, config)
