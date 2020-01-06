import os
import pathlib
from collections import OrderedDict, defaultdict

import appdirs
from dexbot import APP_NAME, AUTHOR
from dexbot.node_manager import get_sorted_nodelist
from ruamel import yaml

DEFAULT_CONFIG_DIR = appdirs.user_config_dir(APP_NAME, appauthor=AUTHOR)
DEFAULT_CONFIG_FILE = os.path.join(DEFAULT_CONFIG_DIR, 'config.yml')


class Config(dict):
    def __init__(self, config=None, path=None):
        """ Creates or loads the config file based on if it exists.
            :param dict config: data used to create the config file
            :param str path: path to the config file
        """
        super().__init__()
        if path:
            self.config_dir = os.path.dirname(path)
            self.config_file = path
        else:
            self.config_dir = DEFAULT_CONFIG_DIR
            self.config_file = DEFAULT_CONFIG_FILE

        if config:
            self.create_config(config, self.config_file)
            self._config = self.load_config(self.config_file)
        else:
            if not os.path.isfile(self.config_file):
                self.create_config(self.default_data, self.config_file)
            self._config = self.load_config(self.config_file)

        # In case there is not a list of nodes in the config file,
        # the node will be replaced by a list of pre-defined nodes,
        # sorted by least latency, no-response nodes are dropped.
        if isinstance(self._config['node'], str):
            sorted_nodes = get_sorted_nodelist(self.node_list)
            self._config['node'] = sorted_nodes
            self.save_config()

        self.intersections_data = None

    def __setitem__(self, key, value):
        self._config[key] = value

    def __getitem__(self, key):
        return self._config[key]

    def __delitem__(self, key):
        del self._config[key]

    def __contains__(self, key):
        return key in self._config

    def get(self, key, default=None):
        return self._config.get(key, default)

    @property
    def default_data(self):
        return {'node': self.node_list, 'workers': {}}

    @property
    def workers_data(self):
        """ Returns dict of all the workers data
        """
        return self._config['workers']

    def dict(self):
        """ Returns a dict instance of the stored data
        """
        return self._config

    @staticmethod
    def create_config(config, path=None):
        if not path:
            config_dir = DEFAULT_CONFIG_DIR
            config_file = DEFAULT_CONFIG_FILE
        else:
            config_dir = os.path.dirname(path)
            config_file = path

        if not os.path.exists(config_dir):
            pathlib.Path(config_dir).mkdir(parents=True, exist_ok=True)

        with open(config_file, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)

    @staticmethod
    def load_config(path=None):
        if not path:
            path = DEFAULT_CONFIG_FILE

        with open(path, 'r') as f:
            return Config.ordered_load(f, loader=yaml.SafeLoader)

    def save_config(self):
        with open(self.config_file, 'w') as f:
            yaml.dump(self._config, f, default_flow_style=False)

    def refresh_config(self):
        self._config = self.load_config(self.config_file)

    @staticmethod
    def get_worker_config_file(worker_name, path=None):
        """ Returns config file data with only the data from a specific worker.
            Config loaded from a file
        """
        if not path:
            path = DEFAULT_CONFIG_FILE

        with open(path, 'r') as f:
            config = Config.ordered_load(f, loader=yaml.SafeLoader)

        config['workers'] = OrderedDict({worker_name: config['workers'][worker_name]})
        return config

    def get_worker_config(self, worker_name):
        """ Returns config file data with only the data from a specific worker.
            Config loaded from memory
        """
        config = self._config.copy()
        config['workers'] = OrderedDict({worker_name: config['workers'][worker_name]})
        return config

    def remove_worker_config(self, worker_name):
        self._config['workers'].pop(worker_name, None)

        with open(self.config_file, 'w') as f:
            yaml.dump(self._config, f, default_flow_style=False)

    def add_worker_config(self, worker_name, worker_data):
        self._config['workers'][worker_name] = worker_data

        with open(self.config_file, 'w') as f:
            yaml.dump(self._config, f, default_flow_style=False)

    def replace_worker_config(self, worker_name, new_worker_name, worker_data):
        workers = self._config['workers']
        # Rotate the dict keys to keep order
        for _ in range(len(workers)):
            key, value = workers.popitem(False)
            if worker_name == key:
                workers[new_worker_name] = worker_data
            else:
                workers[key] = value

        with open(self.config_file, 'w') as f:
            yaml.dump(self._config, f, default_flow_style=False)

    @staticmethod
    def ordered_load(stream, loader=None, object_pairs_hook=OrderedDict):
        if loader is None:
            loader = yaml.UnsafeLoader

        class OrderedLoader(loader):
            pass

        def construct_mapping(mapping_loader, node):
            mapping_loader.flatten_mapping(node)
            return object_pairs_hook(mapping_loader.construct_pairs(node))

        OrderedLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, construct_mapping)
        return yaml.load(stream, OrderedLoader)

    @staticmethod
    def assets_intersections(config):
        """ Collect intersections of assets on the same account across multiple workers

            :return: defaultdict instance representing dict with intersections

            The goal of calculating assets intersections is to be able to use single account on multiple workers and
            trade some common assets. For example, trade BTS/USD, BTC/BTS, ETH/BTC markets on same account.

            Configuration variable `operational_percent_xxx` defines what percent of total account balance should be
            available for the worker. It may be set or omitted.

            The logic of splitting balance is following: workers who define `operational_percent_xxx` will take this
            defined percent, and remaining workers will just split the remaining balance between each other. For
            example, 3 workers with 30% 30% 30%, and 2 workers with 0. These 2 workers will take the remaining `(100 -
            3*30) / 2 = 5`.

            Example return as a dict

            .. code-block:: python

                {'foo': {'RUBLE': {'sum_pct': 0, 'zero_workers': 0},
                         'USD': {'sum_pct': 0, 'zero_workers': 0},
                         'CNY': {'sum_pct': 0, 'zero_workers': 0}
                         }
                }
        """

        def update_data(asset, operational_percent):
            if isinstance(data[account][asset]['sum_pct'], float):
                # Existing dict key
                data[account][asset]['sum_pct'] += operational_percent
                if not operational_percent:
                    # Increase count of workers with 0 op percent
                    data[account][asset]['num_zero_workers'] += 1
            else:
                # Create new dict key
                data[account][asset]['sum_pct'] = operational_percent
                if operational_percent:
                    data[account][asset]['num_zero_workers'] = 0
                else:
                    data[account][asset]['num_zero_workers'] = 1

            if data[account][asset]['sum_pct'] > 1:
                raise ValueError('Operational percent for asset {} is more than 100%'.format(asset))

        def tree():
            return defaultdict(tree)

        data = tree()

        for _, worker in config['workers'].items():
            account = worker['account']
            quote_asset = worker['market'].split('/')[0]
            base_asset = worker['market'].split('/')[1]
            operational_percent_quote = worker.get('operational_percent_quote', 0) / 100
            operational_percent_base = worker.get('operational_percent_base', 0) / 100
            update_data(quote_asset, operational_percent_quote)
            update_data(base_asset, operational_percent_base)

        return data

    @property
    def node_list(self):
        """ A pre-defined list of Bitshares nodes. """
        return [
            "wss://bitshares.openledger.info/ws",
            "wss://openledger.hk/ws",
            "wss://na.openledger.info/ws",
            "wss://ws.gdex.top",
            "wss://api.bts.ai",
            "wss://api-ru.bts.blckchnd.com",
            "wss://bts-seoul.clockwork.gr",
            "wss://btsfullnode.bangzi.info/ws",
            "wss://api.fr.bitsharesdex.com",
            "wss://btsws.roelandp.nl/ws",
            "wss://kc-us-dex.xeldal.com/ws",
            "wss://dallas.us.api.bitshares.org/ws",
            "wss://siliconvalley.us.api.bitshares.org/ws",
            "wss://toronto.ca.api.bitshares.org/ws",
        ]
