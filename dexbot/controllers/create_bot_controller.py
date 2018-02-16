from dexbot.controllers.main_controller import MainController

import bitshares
from bitshares.instance import shared_bitshares_instance
from bitshares.asset import Asset
from bitshares.account import Account
from bitsharesbase.account import PrivateKey
from ruamel.yaml import YAML


class CreateBotController:

    def __init__(self, main_ctrl):
        self.main_ctrl = main_ctrl
        self.bitshares = main_ctrl.bitshares_instance or shared_bitshares_instance()

    @property
    def strategies(self):
        strategies = {
            'Simple Strategy': 'dexbot.strategies.simple'
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

    def remove_bot(self, bot_name):
        self.main_ctrl.remove_bot(bot_name)

    def is_bot_name_valid(self, bot_name, old_bot_name=None):
        bot_names = self.main_ctrl.get_bots_data().keys()
        # and old_bot_name not in bot_names
        if bot_name in bot_names:
            is_name_changed = False
        else:
            is_name_changed = True
        return is_name_changed

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
    def get_unique_bot_name():
        """
        Returns unique bot name "Bot %n", where %n is the next available index
        """
        index = 1
        bots = MainController.get_bots_data().keys()
        botname = "Bot {0}".format(index)
        while botname in bots:
            botname = "Bot {0}".format(index)
            index += 1

        return botname

    @staticmethod
    def add_bot_config(botname, bot_data):
        yaml = YAML()
        with open('config.yml', 'r') as f:
            config = yaml.load(f)

        config['bots'][botname] = bot_data

        with open("config.yml", "w") as f:
            yaml.dump(config, f)

    @staticmethod
    def get_bot_current_strategy(bot_data):
        strategies = {
            bot_data['strategy']: bot_data['module']
        }
        return strategies

    @staticmethod
    def get_assets(bot_data):
        return bot_data['market'].split('/')

    def get_base_asset(self, bot_data):
        return self.get_assets(bot_data)[1]

    def get_quote_asset(self, bot_data):
        return self.get_assets(bot_data)[0]

    @staticmethod
    def get_account(bot_data):
        return bot_data['account']

    @staticmethod
    def get_target_amount(bot_data):
        return bot_data['target']['amount']

    @staticmethod
    def get_target_center_price(bot_data):
        return bot_data['target']['center_price']

    @staticmethod
    def get_target_spread(bot_data):
        return bot_data['target']['spread']
