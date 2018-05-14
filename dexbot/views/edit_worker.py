from .ui.edit_worker_window_ui import Ui_Dialog
from .confirmation import ConfirmationDialog
from .notice import NoticeDialog
from .errors import gui_error

from PyQt5 import QtWidgets


class EditWorkerView(QtWidgets.QDialog, Ui_Dialog):

    def __init__(self, controller, worker_name, config):
        super().__init__()
        self.controller = controller
        self.worker_name = worker_name
        self.strategy_widget = None

        self.setupUi(self)
        worker_data = config['workers'][worker_name]

        # Todo: Using a model here would be more Qt like
        # Populate the comboboxes
        strategies = self.controller.strategies
        for strategy in strategies:
            self.strategy_input.addItem(strategies[strategy]['name'], strategy)

        # Set values from config
        index = self.strategy_input.findData(self.controller.get_strategy_module(worker_data))
        self.strategy_input.setCurrentIndex(index)
        self.worker_name_input.setText(worker_name)
        self.base_asset_input.addItem(self.controller.get_base_asset(worker_data))
        self.base_asset_input.addItems(self.controller.base_assets)
        self.quote_asset_input.setText(self.controller.get_quote_asset(worker_data))
        self.account_name.setText(self.controller.get_account(worker_data))

        # Set signals
        self.strategy_input.currentTextChanged.connect(lambda: controller.change_strategy_form(self))
        self.save_button.clicked.connect(lambda: self.controller.handle_save(self))
        self.cancel_button.clicked.connect(lambda: self.reject())

        self.controller.change_strategy_form(self, worker_data)
        self.worker_data = {}
