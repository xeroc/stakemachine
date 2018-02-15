from PyQt5 import QtWidgets

from dexbot.views.notice import NoticeDialog
from dexbot.views.gen.edit_bot_window import Ui_Dialog


class EditBotView(QtWidgets.QDialog, Ui_Dialog):
    def __init__(self, controller, botname, config):
        super().__init__()
        self.controller = controller

        self.setupUi(self)
        bot_data = config['bots'][botname]
        self.strategy_input.addItems(self.controller.get_bot_current_strategy(bot_data))
        self.bot_name_input.setText(botname)
        self.base_asset_input.addItem(self.controller.get_base_asset(bot_data))
        self.base_asset_input.addItems(self.controller.base_assets)
        self.quote_asset_input.setText(self.controller.get_quote_asset(bot_data))
        self.account_name.setText(self.controller.get_account(bot_data))
