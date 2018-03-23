from dexbot.controllers.main_controller import MainController

import bitshares
from bitshares.instance import shared_bitshares_instance
from bitshares.asset import Asset
from bitshares.account import Account
from bitsharesbase.account import PrivateKey
from ruamel.yaml import YAML


class CreateWorkerController:

    def __init__(self, main_ctrl):
        self.main_ctrl = main_ctrl
        self.bitshares = main_ctrl.bitshares_instance or shared_bitshares_instance()

    @property
    def strategies(self):
        strategies = {
            'Relative Orders': 'dexbot.strategies.relative_orders'
        }
        return strategies

    def get_strategy_module(self, strategy):
        return self.strategies[strategy]

    @property
    def base_assets(self):
        assets = [
            'USD', 'OPEN.BTC', 'CNY', 'BTS', 'BTC'
        ]
        return assets

    def remove_worker(self, worker_name):
        self.main_ctrl.remove_worker(worker_name)

    def is_worker_name_valid(self, worker_name):
        worker_names = self.main_ctrl.get_workers_data().keys()
        # Check that the name is unique
        if worker_name in worker_names:
            return False
        return True

    def is_asset_valid(self, asset):
        try:
            Asset(asset, bitshares_instance=self.bitshares)
            return True
        except bitshares.exceptions.AssetDoesNotExistsException:
            return False

    def account_exists(self, account):
        try:
            Account(account, bitshares_instance=self.bitshares)
            return True
        except bitshares.exceptions.AccountDoesNotExistsException:
            return False

    def is_account_valid(self, account, private_key):
        if not private_key or not account:
            return False

        wallet = self.bitshares.wallet
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

    def add_private_key(self, private_key):
        wallet = self.bitshares.wallet
        try:
            wallet.addPrivateKey(private_key)
        except ValueError:
            # Private key already added
            pass

    @staticmethod
    def get_unique_worker_name():
        """
        Returns unique worker name "Worker %n", where %n is the next available index
        """
        index = 1
        workers = MainController.get_workers_data().keys()
        worker_name = "Worker {0}".format(index)
        while worker_name in workers:
            worker_name = "Worker {0}".format(index)
            index += 1

        return worker_name

    @staticmethod
    def get_worker_current_strategy(worker_data):
        strategies = {
            worker_data['strategy']: worker_data['module']
        }
        return strategies

    @staticmethod
    def get_assets(worker_data):
        return worker_data['market'].split('/')

    def get_base_asset(self, worker_data):
        return self.get_assets(worker_data)[1]

    def get_quote_asset(self, worker_data):
        return self.get_assets(worker_data)[0]

    @staticmethod
    def get_account(worker_data):
        return worker_data['account']

    @staticmethod
    def get_target_amount(worker_data):
        return worker_data['target']['amount']

    @staticmethod
    def get_target_center_price(worker_data):
        return worker_data['target']['center_price']

    @staticmethod
    def get_target_center_price_dynamic(worker_data):
        return worker_data['target']['center_price_dynamic']

    @staticmethod
    def get_target_spread(worker_data):
        return worker_data['target']['spread']
