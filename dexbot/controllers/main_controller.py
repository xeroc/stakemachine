from dexbot.worker import WorkerInfrastructure

from ruamel.yaml import YAML
from bitshares.instance import set_shared_bitshares_instance


class MainController:

    workers = dict()

    def __init__(self, bitshares_instance):
        self.bitshares_instance = bitshares_instance
        set_shared_bitshares_instance(bitshares_instance)
        self.worker_template = WorkerInfrastructure

    def create_worker(self, worker_name, config, view):
        # Todo: Add some threading here so that the GUI doesn't freeze
        worker = self.worker_template(config, self.bitshares_instance, view)
        worker.daemon = True
        worker.start()
        self.workers[worker_name] = worker

    def stop_worker(self, worker_name):
        self.workers[worker_name].stop()
        self.workers.pop(worker_name, None)

    def remove_worker(self, worker_name):
        # Todo: Add some threading here so that the GUI doesn't freeze
        if worker_name in self.workers:
            # Worker currently running
            self.workers[worker_name].remove_worker()
            self.workers[worker_name].stop()
            self.workers.pop(worker_name, None)
        else:
            # Worker not running
            config = self.get_worker_config(worker_name)
            self.worker_template.remove_offline_worker(config, worker_name)

    @staticmethod
    def load_config():
        yaml = YAML()
        with open('config.yml', 'r') as f:
            return yaml.load(f)

    @staticmethod
    def get_workers_data():
        """
        Returns dict of all the workers data
        """
        with open('config.yml', 'r') as f:
            yaml = YAML()
            return yaml.load(f)['workers']

    @staticmethod
    def get_worker_config(worker_name):
        """
        Returns config file data with only the data from a specific worker
        """
        with open('config.yml', 'r') as f:
            yaml = YAML()
            config = yaml.load(f)
            config['workers'] = {worker_name: config['workers'][worker_name]}
            return config

    @staticmethod
    def remove_worker_config(worker_name):
        yaml = YAML()
        with open('config.yml', 'r') as f:
            config = yaml.load(f)

        config['workers'].pop(worker_name, None)

        with open("config.yml", "w") as f:
            yaml.dump(config, f)

    @staticmethod
    def add_worker_config(worker_name, worker_data):
        yaml = YAML()
        with open('config.yml', 'r') as f:
            config = yaml.load(f)

        config['workers'][worker_name] = worker_data

        with open("config.yml", "w") as f:
            yaml.dump(config, f)
