from .notice import NoticeDialog
from .ui.create_worker_window_ui import Ui_Dialog

from PyQt5 import QtWidgets


class CreateWorkerView(QtWidgets.QDialog):

    def __init__(self, controller):
        super().__init__()
        self.controller = controller

        self.ui = Ui_Dialog()
        self.ui.setupUi(self)

        # Todo: Using a model here would be more Qt like
        self.ui.strategy_input.addItems(self.controller.strategies)
        self.ui.base_asset_input.addItems(self.controller.base_assets)

        self.worker_name = controller.get_unique_worker_name()
        self.ui.worker_name_input.setText(self.worker_name)

        self.ui.save_button.clicked.connect(self.handle_save)
        self.ui.cancel_button.clicked.connect(self.reject)
        self.ui.center_price_dynamic_checkbox.stateChanged.connect(self.onchange_center_price_dynamic_checkbox)
        self.worker_data = {}

    def onchange_center_price_dynamic_checkbox(self):
        checkbox = self.ui.center_price_dynamic_checkbox
        if checkbox.isChecked():
            self.ui.center_price_input.setDisabled(True)
        else:
            self.ui.center_price_input.setDisabled(False)

    def validate_worker_name(self):
        worker_name = self.ui.worker_name_input.text()
        return self.controller.is_worker_name_valid(worker_name)

    def validate_asset(self, asset):
        return self.controller.is_asset_valid(asset)

    def validate_market(self):
        base_asset = self.ui.base_asset_input.currentText()
        quote_asset = self.ui.quote_asset_input.text()
        return base_asset.lower() != quote_asset.lower()

    def validate_account_name(self):
        account = self.ui.account_input.text()
        return self.controller.account_exists(account)

    def validate_account(self):
        account = self.ui.account_input.text()
        private_key = self.ui.private_key_input.text()
        return self.controller.is_account_valid(account, private_key)

    def validate_form(self):
        error_text = ''
        base_asset = self.ui.base_asset_input.currentText()
        quote_asset = self.ui.quote_asset_input.text()
        if not self.validate_worker_name():
            worker_name = self.ui.worker_name_input.text()
            error_text += 'Worker name needs to be unique. "{}" is already in use.'.format(worker_name) + '\n'
        if not self.validate_asset(base_asset):
            error_text += 'Field "Base Asset" does not have a valid asset.' + '\n'
        if not self.validate_asset(quote_asset):
            error_text += 'Field "Quote Asset" does not have a valid asset.' + '\n'
        if not self.validate_market():
            error_text += "Market {}/{} doesn't exist.".format(base_asset, quote_asset) + '\n'
        if not self.validate_account_name():
            error_text += "Account doesn't exist." + '\n'
        if not self.validate_account():
            error_text += 'Private key is invalid.' + '\n'

        if error_text:
            dialog = NoticeDialog(error_text)
            dialog.exec_()
            return False
        else:
            return True

    def handle_save(self):
        if not self.validate_form():
            return

        # Add the private key to the database
        private_key = self.ui.private_key_input.text()
        self.controller.add_private_key(private_key)

        ui = self.ui
        spread = float(ui.spread_input.text()[:-1])  # Remove the percentage character from the end
        target = {
            'amount': float(ui.amount_input.text()),
            'center_price': float(ui.center_price_input.text()),
            'center_price_dynamic': bool(ui.center_price_dynamic_checkbox.isChecked()),
            'spread': spread
        }

        base_asset = ui.base_asset_input.currentText()
        quote_asset = ui.quote_asset_input.text()
        strategy = ui.strategy_input.currentText()
        worker_module = self.controller.get_strategy_module(strategy)
        self.worker_data = {
            'account': ui.account_input.text(),
            'market': '{}/{}'.format(quote_asset, base_asset),
            'module': worker_module,
            'strategy': strategy,
            'target': target
        }
        self.worker_name = ui.worker_name_input.text()
        self.accept()
