from .ui.edit_worker_window_ui import Ui_Dialog
from .confirmation import ConfirmationDialog
from .notice import NoticeDialog

from PyQt5 import QtWidgets


class EditWorkerView(QtWidgets.QDialog, Ui_Dialog):

    def __init__(self, controller, worker_name, config):
        super().__init__()
        self.controller = controller

        self.setupUi(self)
        worker_data = config['workers'][worker_name]
        self.strategy_input.addItems(self.controller.get_worker_current_strategy(worker_data))
        self.worker_name = worker_name
        self.worker_name_input.setText(worker_name)
        self.base_asset_input.addItem(self.controller.get_base_asset(worker_data))
        self.base_asset_input.addItems(self.controller.base_assets)
        self.quote_asset_input.setText(self.controller.get_quote_asset(worker_data))
        self.account_name.setText(self.controller.get_account(worker_data))
        self.amount_input.setValue(self.controller.get_target_amount(worker_data))
        self.center_price_input.setValue(self.controller.get_target_center_price(worker_data))

        center_price_dynamic = self.controller.get_target_center_price_dynamic(worker_data)
        if center_price_dynamic:
            self.center_price_input.setEnabled(False)
            self.center_price_dynamic_checkbox.setChecked(True)
        else:
            self.center_price_input.setEnabled(True)
            self.center_price_dynamic_checkbox.setChecked(False)

        self.spread_input.setValue(self.controller.get_target_spread(worker_data))
        self.save_button.clicked.connect(self.handle_save)
        self.cancel_button.clicked.connect(self.reject)
        self.center_price_dynamic_checkbox.stateChanged.connect(self.onchange_center_price_dynamic_checkbox)
        self.worker_data = {}

    def onchange_center_price_dynamic_checkbox(self):
        checkbox = self.center_price_dynamic_checkbox
        if checkbox.isChecked():
            self.center_price_input.setDisabled(True)
        else:
            self.center_price_input.setDisabled(False)

    def validate_worker_name(self):
        old_worker_name = self.worker_name
        worker_name = self.worker_name_input.text()
        if old_worker_name != worker_name:
            return self.controller.is_worker_name_valid(worker_name)
        return True

    def validate_asset(self, asset):
        return self.controller.is_asset_valid(asset)

    def validate_market(self):
        base_asset = self.base_asset_input.currentText()
        quote_asset = self.quote_asset_input.text()
        return base_asset.lower() != quote_asset.lower()

    def validate_form(self):
        error_text = ''
        base_asset = self.base_asset_input.currentText()
        quote_asset = self.quote_asset_input.text()

        if not self.validate_worker_name():
            worker_name = self.worker_name_input.text()
            error_text += 'Worker name needs to be unique. "{}" is already in use.\n'.format(worker_name)
        if not self.validate_asset(base_asset):
            error_text += 'Field "Base Asset" does not have a valid asset.\n'
        if not self.validate_asset(quote_asset):
            error_text += 'Field "Quote Asset" does not have a valid asset.\n'
        if not self.validate_market():
            error_text += "Market {}/{} doesn't exist.\n".format(base_asset, quote_asset)

        if error_text:
            dialog = NoticeDialog(error_text)
            dialog.exec_()
            return False
        else:
            return True

    @staticmethod
    def handle_save_dialog():
        dialog = ConfirmationDialog('Saving the worker will cancel all the current orders.\n'
                                    'Are you sure you want to do this?')
        return dialog.exec_()

    def handle_save(self):
        if not self.validate_form():
            return

        if not self.handle_save_dialog():
            return

        spread = float(self.spread_input.text()[:-1])  # Remove the percentage character from the end
        target = {
            'amount': float(self.amount_input.text()),
            'center_price': float(self.center_price_input.text()),
            'center_price_dynamic': bool(self.center_price_dynamic_checkbox.isChecked()),
            'spread': spread
        }

        base_asset = self.base_asset_input.currentText()
        quote_asset = self.quote_asset_input.text()
        strategy = self.strategy_input.currentText()
        worker_module = self.controller.get_strategy_module(strategy)
        self.worker_data = {
            'account': self.account_name.text(),
            'market': '{}/{}'.format(quote_asset, base_asset),
            'module': worker_module,
            'strategy': strategy,
            'target': target
        }
        self.worker_name = self.worker_name_input.text()
        self.accept()
