from dexbot.views.bot_list import MainView
from dexbot.bot import BotInfrastructure

from ruamel.yaml import YAML

class MainController(object):

    def __init__(self):
        self.model = BotInfrastructure
        self.view = MainView(self)
        self.view.show()

    def get_bots_data(self):
        """
        Returns dict of all the bots data
        """
        with open('config.yml', 'r') as f:
            yaml = YAML()
            return yaml.load(f)['bots']
