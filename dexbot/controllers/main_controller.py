from dexbot.views.bot_list import MainView
from dexbot.bot import BotInfrastructure

from ruamel.yaml import YAML
from bitshares import BitShares


class MainController(object):

    def __init__(self):
        self.model = BotInfrastructure
        self.view = MainView(self)
        self.view.show()

    def get_bots_data(self):
    def create_bot(self, botname, config):
        bitshares = BitShares(
            node=config['node']
        )

    def stop_bot(self, bot_id):
        self.bots[bot_id].terminate()

    def remove_bot(self, botname):
        # Todo: cancell all orders on removal
        self.bots[botname].terminate()

        """
        Returns dict of all the bots data
        """
        with open('config.yml', 'r') as f:
            yaml = YAML()
            return yaml.load(f)['bots']
