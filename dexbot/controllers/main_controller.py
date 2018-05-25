import os
import logging
import sys

from dexbot import config_file, VERSION
from dexbot.worker import WorkerInfrastructure
from dexbot.views.errors import PyQtHandler

import appdirs
from ruamel import yaml
from bitshares.instance import set_shared_bitshares_instance

CONFIG_PATH = os.path.join(appdirs.user_config_dir('dexbot'), 'config.yml')


class MainController:

    def __init__(self, bitshares_instance, config):
        self.bitshares_instance = bitshares_instance
        set_shared_bitshares_instance(bitshares_instance)
        self.config = config
        self.worker_manager = None

        # Configure logging
        formatter = logging.Formatter(
            '%(asctime)s - %(worker_name)s using account %(account)s on %(market)s - %(levelname)s - %(message)s')
        logger = logging.getLogger("dexbot.per_worker")
        fh = logging.FileHandler('dexbot.log')
        fh.setFormatter(formatter)
        logger.addHandler(fh)
        logger.setLevel(logging.INFO)
        pyqth = PyQtHandler()
        pyqth.setLevel(logging.ERROR)
        logger.addHandler(pyqth)
        logger.info("DEXBot {} on python {} {}".format(VERSION, sys.version[:6], sys.platform), extra={
                    'worker_name': 'NONE', 'account': 'NONE', 'market': 'NONE'})

    def create_worker(self, worker_name, config, view):
        # Todo: Add some threading here so that the GUI doesn't freeze
        if self.worker_manager and self.worker_manager.is_alive():
            self.worker_manager.add_worker(worker_name, config)
        else:
            self.worker_manager = WorkerInfrastructure(config, self.bitshares_instance, view)
            self.worker_manager.daemon = True
            self.worker_manager.start()

    def stop_worker(self, worker_name):
        self.worker_manager.stop(worker_name)

    def remove_worker(self, worker_name):
        # Todo: Add some threading here so that the GUI doesn't freeze
        if self.worker_manager and self.worker_manager.is_alive():
            # Worker manager currently running
            if worker_name in self.worker_manager.workers:
                self.worker_manager.remove_worker(worker_name)
                self.worker_manager.stop(worker_name)
            else:
                # Worker not running
                config = self.get_worker_config(worker_name)
                WorkerInfrastructure.remove_offline_worker(config, worker_name)
        else:
            # Worker manager not running
            config = self.get_worker_config(worker_name)
            WorkerInfrastructure.remove_offline_worker(config, worker_name)

    @staticmethod
    def create_config(config):
        with open(CONFIG_PATH, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)

    @staticmethod
    def load_config():
        with open(CONFIG_PATH, 'r') as f:
            return yaml.safe_load(f)

    def refresh_config(self):
        self.config = self.load_config()

    def get_workers_data(self):
        """ Returns dict of all the workers data
        """
        return self.config['workers']

    def get_worker_config(self, worker_name):
        """ Returns config file data with only the data from a specific worker
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
