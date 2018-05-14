from .ui.create_worker_window_ui import Ui_Dialog
from .errors import gui_error

from PyQt5 import QtWidgets


class CreateWorkerView(QtWidgets.QDialog, Ui_Dialog):

    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.strategy_widget = None

        self.setupUi(self)

        # Todo: Using a model here would be more Qt like
        # Populate the comboboxes
        strategies = self.controller.strategies
        for strategy in strategies:
            self.strategy_input.addItem(strategies[strategy]['name'], strategy)
        self.base_asset_input.addItems(self.controller.base_assets)

        # Generate a name for the worker
        self.worker_name = controller.get_unique_worker_name()
        self.worker_name_input.setText(self.worker_name)

        # Set signals
        self.strategy_input.currentTextChanged.connect(lambda: controller.change_strategy_form(self))
        self.save_button.clicked.connect(lambda: controller.handle_save(self))
        self.cancel_button.clicked.connect(lambda: self.reject())

        self.controller.change_strategy_form(self)
        self.worker_data = {}
