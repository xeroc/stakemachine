from .ui.edit_worker_window_ui import Ui_Dialog
from dexbot.controllers.worker_controller import WorkerController, UppercaseValidator

from PyQt5 import QtWidgets


class EditWorkerView(QtWidgets.QDialog, Ui_Dialog):

    def __init__(self, parent_widget, bitshares_instance, worker_name, config):
        super().__init__()
        self.worker_name = worker_name
        self.strategy_widget = None
        controller = WorkerController(self, bitshares_instance, 'edit')
        self.controller = controller
        self.parent_widget = parent_widget

        self.setupUi(self)
        worker_data = config['workers'][worker_name]

        # Todo: Using a model here would be more Qt like
        # Populate the combobox
        strategies = self.controller.strategies
        for strategy in strategies:
            self.strategy_input.addItem(strategies[strategy]['name'], strategy)

        # Set values from config
        index = self.strategy_input.findData(self.controller.get_strategy_module(worker_data))
        self.strategy_input.setCurrentIndex(index)
        self.worker_name_input.setText(worker_name)
        self.base_asset_input.setText(self.controller.get_base_asset(worker_data))
        self.quote_asset_input.setText(self.controller.get_quote_asset(worker_data))
        self.fee_asset_input.setText(worker_data.get('fee_asset', 'BTS'))
        self.account_name.setText(self.controller.get_account(worker_data))
        self.operational_percent_quote_input.setValue(worker_data.get('operational_percent_quote', 0))
        self.operational_percent_base_input.setValue(worker_data.get('operational_percent_base', 0))

        # Force uppercase to the assets fields
        validator = UppercaseValidator(self)
        self.base_asset_input.setValidator(validator)
        self.quote_asset_input.setValidator(validator)
        self.fee_asset_input.setValidator(validator)

        # Set signals
        self.strategy_input.currentTextChanged.connect(lambda: controller.change_strategy_form())
        self.save_button.clicked.connect(lambda: self.controller.handle_save())
        self.cancel_button.clicked.connect(lambda: self.reject())
        self.remove_button.clicked.connect(self.handle_remove)

        self.controller.change_strategy_form(worker_data)
        self.worker_data = {}

    def handle_remove(self):
        self.parent_widget.remove_widget_dialog()
        self.reject()
