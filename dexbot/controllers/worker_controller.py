import collections
import re

from dexbot.views.errors import gui_error
from dexbot.config import Config
from dexbot.helper import find_external_strategies
from dexbot.views.notice import NoticeDialog
from dexbot.views.confirmation import ConfirmationDialog
from dexbot.views.strategy_form import StrategyFormWidget

import bitshares
from bitshares.instance import shared_bitshares_instance
from bitshares.asset import Asset
from bitshares.account import Account
from bitsharesbase.account import PrivateKey
from PyQt5 import QtGui


class WorkerController:

    def __init__(self, view, bitshares_instance, mode):
        self.view = view
        self.bitshares = bitshares_instance or shared_bitshares_instance()
        self.mode = mode

    @property
    def strategies(self):
        strategies = collections.OrderedDict()
        strategies['dexbot.strategies.relative_orders'] = {
            'name': 'Relative Orders',
            'form_module': ''
        }
        strategies['dexbot.strategies.staggered_orders'] = {
            'name': 'Staggered Orders',
            'form_module': 'dexbot.views.ui.forms.staggered_orders_widget_ui'
        }
        for desc, module in find_external_strategies():
            strategies[module] = {'name': desc, 'form_module': module}
            # if there is no UI form in the module then GUI will gracefully revert to auto-ui
        return strategies

    @classmethod
    def get_strategies(cls):
        """ Class method for getting the strategies
        """
        return cls(None, None, None).strategies

    @property
    def base_assets(self):
        assets = [
            'USD', 'OPEN.BTC', 'CNY', 'BTS', 'BTC'
        ]
        return assets

    def add_private_key(self, private_key):
        wallet = self.bitshares.wallet
        try:
            wallet.addPrivateKey(private_key)
        except ValueError:
            # Private key already added
            pass

    @staticmethod
    def get_unique_worker_name():
        """ Returns unique worker name "Worker %n"
            %n is the next available index
        """
        index = 1
        workers = Config().workers_data.keys()
        worker_name = "Worker {0}".format(index)
        while worker_name in workers:
            worker_name = "Worker {0}".format(index)
            index += 1

        return worker_name

    @staticmethod
    def get_strategy_module(worker_data):
        return worker_data['module']

    @staticmethod
    def get_strategy_mode(worker_data):
        return worker_data['mode']

    @staticmethod
    def get_allow_instant_fill(worder_data):
        return worder_data['allow_instant_fill']

    @staticmethod
    def get_assets(worker_data):
        return re.split("[/:]", worker_data['market'])

    def get_base_asset(self, worker_data):
        return self.get_assets(worker_data)[1]

    def get_quote_asset(self, worker_data):
        return self.get_assets(worker_data)[0]

    @staticmethod
    def get_account(worker_data):
        return worker_data['account']

    @staticmethod
    def handle_save_dialog():
        dialog = ConfirmationDialog('Saving the worker will cancel all the current orders.\n'
                                    'Are you sure you want to do this?')
        return dialog.exec_()

    @gui_error
    def change_strategy_form(self, worker_data=None):
        # Make sure the container is empty
        for index in reversed(range(self.view.strategy_container.count())):
            self.view.strategy_container.itemAt(index).widget().setParent(None)

        strategy_module = self.view.strategy_input.currentData()
        self.view.strategy_widget = StrategyFormWidget(self, strategy_module, worker_data)
        self.view.strategy_container.addWidget(self.view.strategy_widget)

        # Resize the dialog to be minimum possible height
        width = self.view.geometry().width()
        self.view.setMinimumHeight(0)
        self.view.resize(width, 1)

    @classmethod
    def validate_worker_name(cls, worker_name, old_worker_name=None):
        if old_worker_name != worker_name:
            worker_names = Config().workers_data.keys()
            # Check that the name is unique
            if worker_name in worker_names:
                return False
            return True
        return True

    def validate_asset(self, asset):
        try:
            Asset(asset, bitshares_instance=self.bitshares)
            return True
        except bitshares.exceptions.AssetDoesNotExistsException:
            return False

    @classmethod
    def validate_market(cls, base_asset, quote_asset):
        return base_asset.lower() != quote_asset.lower()

    def validate_account_name(self, account):
        if not account:
            return False
        try:
            Account(account, bitshares_instance=self.bitshares)
            return True
        except bitshares.exceptions.AccountDoesNotExistsException:
            return False

    def validate_private_key(self, account, private_key):
        wallet = self.bitshares.wallet
        if not private_key:
            # Check if the private key is already in the database
            accounts = wallet.getAccounts()
            if any(account == d['name'] for d in accounts):
                return True
            return False

        try:
            pubkey = format(PrivateKey(private_key).pubkey, self.bitshares.prefix)
        except ValueError:
            return False

        accounts = wallet.getAllAccounts(pubkey)
        account_names = [account['name'] for account in accounts]

        if account in account_names:
            return True
        else:
            return False

    def validate_private_key_type(self, account, private_key):
        account = Account(account)
        pubkey = format(PrivateKey(private_key).pubkey, self.bitshares.prefix)
        key_type = self.bitshares.wallet.getKeyType(account, pubkey)
        if key_type != 'active':
            return False
        return True

    @classmethod
    def validate_account_not_in_use(cls, account):
        workers = Config().workers_data
        for worker_name, worker in workers.items():
            if worker['account'] == account:
                return False
        return True

    @gui_error
    def validate_form(self):
        error_texts = []
        base_asset = self.view.base_asset_input.currentText()
        quote_asset = self.view.quote_asset_input.text()
        fee_asset = self.view.fee_asset_input.text()
        worker_name = self.view.worker_name_input.text()
        old_worker_name = None if self.mode == 'add' else self.view.worker_name

        if not self.validate_worker_name(worker_name, old_worker_name):
            error_texts.append(
                'Worker name needs to be unique. "{}" is already in use.'.format(worker_name))
        if not self.validate_asset(base_asset):
            error_texts.append('Field "Base Asset" does not have a valid asset.')
        if not self.validate_asset(quote_asset):
            error_texts.append('Field "Quote Asset" does not have a valid asset.')
        if not self.validate_asset(fee_asset):
            error_texts.append('Field "Fee Asset" does not have a valid asset.')
        if not self.validate_market(base_asset, quote_asset):
            error_texts.append("Market {}/{} doesn't exist.".format(base_asset, quote_asset))
        if self.mode == 'add':
            account = self.view.account_input.text()
            private_key = self.view.private_key_input.text()
            if not self.validate_account_name(account):
                error_texts.append("Account doesn't exist.")
            if not self.validate_account_not_in_use(account):
                error_texts.append('Use a different account. "{}" is already in use.'.format(account))
            if not self.validate_private_key(account, private_key):
                error_texts.append('Private key is invalid.')
            elif private_key and not self.validate_private_key_type(account, private_key):
                error_texts.append('Please use active private key.')

        error_texts.extend(self.view.strategy_widget.strategy_controller.validation_errors())
        error_text = '\n'.join(error_texts)

        if error_text:
            dialog = NoticeDialog(error_text)
            dialog.exec_()
            return False
        else:
            return True

    @gui_error
    def handle_save(self):
        if not self.validate_form():
            return

        if self.mode == 'add':
            # Add the private key to the database
            private_key = self.view.private_key_input.text()
            if private_key:
                self.add_private_key(private_key)

            account = self.view.account_input.text()
        else:  # Edit
            account = self.view.account_name.text()

        base_asset = self.view.base_asset_input.currentText()
        quote_asset = self.view.quote_asset_input.text()
        fee_asset = self.view.fee_asset_input.text()
        strategy_module = self.view.strategy_input.currentData()

        self.view.worker_data = {
            'account': account,
            'market': '{}/{}'.format(quote_asset, base_asset),
            'module': strategy_module,
            'fee_asset': fee_asset,
            **self.view.strategy_widget.values
        }
        self.view.worker_name = self.view.worker_name_input.text()
        self.view.accept()


class UppercaseValidator(QtGui.QValidator):

    @staticmethod
    def validate(string, pos):
        return QtGui.QValidator.Acceptable, string.upper(), pos
