from PyQt5 import QtWidgets

from dexbot.controllers.worker_controller import UppercaseValidator, WorkerController

from .ui.create_worker_window_ui import Ui_Dialog


class CreateWorkerView(QtWidgets.QDialog, Ui_Dialog):
    def __init__(self, bitshares_instance):
        super().__init__()
        self.strategy_widget = None
        controller = WorkerController(self, bitshares_instance, 'add')
        self.controller = controller

        self.setupUi(self)

        # Todo: Using a model here would be more Qt like
        # Populate the combobox
        strategies = self.controller.strategies
        for strategy in strategies:
            self.strategy_input.addItem(strategies[strategy]['name'], strategy)

        # Generate a name for the worker
        self.worker_name = controller.get_unique_worker_name()
        self.worker_name_input.setText(self.worker_name)

        # Force uppercase to the assets fields
        validator = UppercaseValidator(self)
        self.base_asset_input.setValidator(validator)
        self.quote_asset_input.setValidator(validator)
        self.fee_asset_input.setValidator(validator)

        # Set signals
        self.strategy_input.currentTextChanged.connect(lambda: controller.change_strategy_form())
        self.save_button.clicked.connect(lambda: controller.handle_save())
        self.cancel_button.clicked.connect(lambda: self.reject())

        self.controller.change_strategy_form()
        self.worker_data = {}
