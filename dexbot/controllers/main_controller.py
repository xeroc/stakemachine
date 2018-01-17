from PyQt5 import QtWidgets
from ruamel.yaml import YAML

class MainController(object):

    def __init__(self, model):
        pass

    def get_bots_data(self):
        """
        Returns dict of all the bots data
        """
        with open('config.yml', 'r') as f:
            yaml = YAML()
            return yaml.load(f)['bots']
