from PyQt5 import QtWidgets
import yaml

class MainController(object):

    def __init__(self, model):
        pass

    def get_bots_data(self):
        """
        Returns dict of all the bots data
        """
        with open('config.yml', 'r') as f:
            return yaml.load(f)['bots']
