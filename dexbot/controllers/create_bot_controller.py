from dexbot.controllers.main_controller import MainController

import bitshares
from bitshares.instance import shared_bitshares_instance
from bitshares.asset import Asset
from bitshares.account import Account
from ruamel.yaml import YAML


class CreateBotController:

    def __init__(self, bitshares_instance):
        self.bitshares = bitshares_instance or shared_bitshares_instance()

    @property
    def strategies(self):
        strategies = {
            'Simple Strategy': 'dexbot.strategies.simple'
        }
        return strategies

    def get_strategy_module(self, strategy):
        return self.strategies[strategy]

    @staticmethod
    def is_bot_name_valid(bot_name):
        bot_names = MainController.get_bots_data().keys()
        if bot_name in bot_names:
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
        # Todo: finish this
        return True

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
