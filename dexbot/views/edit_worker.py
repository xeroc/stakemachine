from .ui.edit_worker_window_ui import Ui_Dialog
from .confirmation import ConfirmationDialog
from .notice import NoticeDialog
from .errors import gui_error

from PyQt5 import QtWidgets


class EditWorkerView(QtWidgets.QDialog, Ui_Dialog):

    def __init__(self, parent_widget, controller, worker_name, config):
        super().__init__()
        self.controller = controller
        self.parent_widget = parent_widget

        self.setupUi(self)
        worker_data = config['workers'][worker_name]
        self.strategy_input.addItems(self.controller.get_worker_current_strategy(worker_data))
        self.worker_name = worker_name
        self.worker_name_input.setText(worker_name)
        self.base_asset_input.addItem(self.controller.get_base_asset(worker_data))
        self.base_asset_input.addItems(self.controller.base_assets)
        self.quote_asset_input.setText(self.controller.get_quote_asset(worker_data))
        self.account_name.setText(self.controller.get_account(worker_data))

        if self.controller.get_amount_relative(worker_data):
            self.order_size_input_to_relative()
            self.relative_order_size_checkbox.setChecked(True)
        else:
            self.order_size_input_to_static()
            self.relative_order_size_checkbox.setChecked(False)

        self.amount_input.setValue(float(self.controller.get_amount(worker_data)))

        self.center_price_input.setValue(self.controller.get_center_price(worker_data))

        center_price_dynamic = self.controller.get_center_price_dynamic(worker_data)
        if center_price_dynamic:
            self.center_price_input.setEnabled(False)
            self.center_price_dynamic_checkbox.setChecked(True)
        else:
            self.center_price_input.setEnabled(True)
            self.center_price_dynamic_checkbox.setChecked(False)

        self.spread_input.setValue(self.controller.get_spread(worker_data))
        self.save_button.clicked.connect(self.handle_save)
        self.cancel_button.clicked.connect(self.reject)
        self.remove_button.clicked.connect(self.handle_remove)
        self.center_price_dynamic_checkbox.stateChanged.connect(self.onchange_center_price_dynamic_checkbox)
        self.relative_order_size_checkbox.stateChanged.connect(self.onchange_relative_order_size_checkbox)
        self.worker_data = {}

    def order_size_input_to_relative(self):
        input_field = self.amount_input
        input_field.setSuffix('%')
        input_field.setDecimals(2)
        input_field.setMaximum(100.00)
        input_field.setMinimumWidth(151)

    def order_size_input_to_static(self):
        input_field = self.amount_input
        input_field.setSuffix('')
        input_field.setDecimals(8)
        input_field.setMaximum(1000000000.000000)
        input_field.setMinimumWidth(151)

    @gui_error
    def onchange_relative_order_size_checkbox(self):
        if self.relative_order_size_checkbox.isChecked():
            self.order_size_input_to_relative()
            self.amount_input.setValue(10.00)
        else:
            self.order_size_input_to_static()
            self.amount_input.setValue(0.000000)

    @gui_error
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
        error_text = error_text.rstrip()  # Remove the extra line-ending

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

    @gui_error
    def handle_save(self):
        if not self.validate_form():
            return

        if not self.handle_save_dialog():
            return

        spread = float(self.spread_input.text()[:-1])  # Remove the percentage character from the end

        # If order size is relative, remove percentage character in the end
        if self.relative_order_size_checkbox.isChecked():
            amount = float(self.amount_input.text()[:-1])
        else:
            amount = self.amount_input.text()

        base_asset = self.base_asset_input.currentText()
        quote_asset = self.quote_asset_input.text()
        strategy = self.strategy_input.currentText()
        worker_module = self.controller.get_strategy_module(strategy)
        self.worker_data = {
            'account': self.account_name.text(),
            'market': '{}/{}'.format(quote_asset, base_asset),
            'module': worker_module,
            'strategy': strategy,
            'amount': amount,
            'amount_relative': bool(self.relative_order_size_checkbox.isChecked()),
            'center_price': float(self.center_price_input.text()),
            'center_price_dynamic': bool(self.center_price_dynamic_checkbox.isChecked()),
            'spread': spread
        }
        self.worker_name = self.worker_name_input.text()
        self.accept()

    def handle_remove(self):
        self.parent_widget.remove_widget_dialog()
        self.reject()