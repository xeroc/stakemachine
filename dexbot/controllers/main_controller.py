from dexbot.views.bot_list import MainView
from dexbot.bot import BotInfrastructure

from ruamel.yaml import YAML
from bitshares import BitShares
from bitshares.instance import set_shared_bitshares_instance


class MainController(object):

    bots = dict()

    def __init__(self):
        self.model = BotInfrastructure
        self.view = MainView(self)
        self.view.show()

    def create_bot(self, botname, config):
        bitshares = BitShares(
            node=config['node']
        )
        set_shared_bitshares_instance(bitshares)
        bitshares.wallet.unlock('test')  # Temporal code until password input is implemented

        gui_data = {'id': botname, 'controller': self}
        bot = self.model(config, bitshares, gui_data)
        bot.daemon = True
        bot.start()
        self.bots[botname] = bot

    def stop_bot(self, bot_id):
        self.bots[bot_id].terminate()

    def remove_bot(self, botname):
        # Todo: cancell all orders on removal
        self.bots[botname].terminate()

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
    def get_bots_data():
        """
        Returns dict of all the bots data
        """
        with open('config.yml', 'r') as f:
            yaml = YAML()
            return yaml.load(f)['bots']

    @staticmethod
    def get_latest_bot_config():
        """
        Returns config file data with only the latest bot data
        """
        with open('config.yml', 'r') as f:
            yaml = YAML()
            config = yaml.load(f)
            latest_bot = list(config['bots'].keys())[-1]
            config['bots'] = {latest_bot: config['bots'][latest_bot]}
            return config

    @staticmethod
    def get_bot_config(botname):
        """
        Returns config file data with only the data from a specific bot
        """
        with open('config.yml', 'r') as f:
            yaml = YAML()
            config = yaml.load(f)
            config['bots'] = {botname: config['bots'][botname]}
            return config
