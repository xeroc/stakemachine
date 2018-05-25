import logging
import sys

from dexbot import config_file, VERSION
from dexbot.worker import WorkerInfrastructure
from dexbot.config import Config
from dexbot.views.errors import PyQtHandler

from bitshares.instance import set_shared_bitshares_instance


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
                config = self.config.get_worker_config(worker_name)
                WorkerInfrastructure.remove_offline_worker(config, worker_name)
        else:
            # Worker manager not running
            config = self.config.get_worker_config(worker_name)
            WorkerInfrastructure.remove_offline_worker(config, worker_name)

