import os

import appdirs
from ruamel import yaml

CONFIG_PATH = os.path.join(appdirs.user_config_dir('dexbot'), 'config.yml')


class Config(dict):

    def __init__(self, config=None):
        super().__init__()
        if config:
            self.config = config
        else:
            self.config = self.load_config()

    def __setitem__(self, key, value):
        self.config[key] = value

    def __getitem__(self, key):
        return self.config[key]

    def __delitem__(self, key):
        del self.config[key]

    def __contains__(self, key):
        return key in self.config

    @staticmethod
    def create_config(config):
        with open(CONFIG_PATH, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)

    @staticmethod
    def load_config():
        with open(CONFIG_PATH, 'r') as f:
            return yaml.load(f, Loader=yaml.RoundTripLoader)

    def refresh_config(self):
        self.config = self.load_config()

    def get_workers_data(self):
        """ Returns dict of all the workers data
        """
        return self.config['workers']

    @staticmethod
    def get_worker_config_file(worker_name):
        """ Returns config file data with only the data from a specific worker.
            Config loaded from a file
        """
        with open(CONFIG_PATH, 'r') as f:
            config = yaml.load(f, Loader=yaml.RoundTripLoader)

        config['workers'] = {worker_name: config['workers'][worker_name]}
        return config

    def get_worker_config(self, worker_name):
        """ Returns config file data with only the data from a specific worker.
            Config loaded from memory
        """
        config = self.config
        config['workers'] = {worker_name: config['workers'][worker_name]}
        return config

    def remove_worker_config(self, worker_name):
        self.config['workers'].pop(worker_name, None)

        with open(CONFIG_PATH, 'w') as f:
            yaml.dump(self.config, f)

    def add_worker_config(self, worker_name, worker_data):
        self.config['workers'][worker_name] = worker_data

        with open(CONFIG_PATH, 'w') as f:
            yaml.dump(self.config, f, default_flow_style=False)

    def replace_worker_config(self, worker_name, new_worker_name, worker_data):
        workers = self.config['workers']
        # Rotate the dict keys to keep order
        for _ in range(len(workers)):
            key, value = workers.popitem(False)
            if worker_name == key:
                workers[new_worker_name] = worker_data
            else:
                workers[key] = value

        with open(CONFIG_PATH, 'w') as f:
            yaml.dump(self.config, f, default_flow_style=False)
