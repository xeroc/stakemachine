from bitshares.bitshares import BitShares
from bitshares.market import Market

from dexbot.config import Config
from dexbot.orderengines.bitshares_engine import BitsharesOrderEngine

import pytest
import logging, os

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(funcName)s %(lineno)d  : %(message)s'
)


def test_fixtures():
    TEST_CONFIG = {
        'node': 'wss://api.fr.bitsharesdex.com/ws',
        'workers': {
            'worker 1': {
                'account': 'octet5',  # edit this for TESTNET Account
                'amount': 0.015,
                'center_price': 0.0,
                'center_price_depth': 0.4,
                'center_price_dynamic': True,
                'center_price_offset': True,
                'custom_expiration': False,
                'dynamic_spread': False,
                'dynamic_spread_factor': 1.0,
                'expiration_time': 157680000.0,
                'external_feed': True,
                'external_price_source': 'gecko',
                'fee_asset': 'BTS',
                'manual_offset': 0.0,
                'market': 'OPEN.XMR/BTS',
                'market_depth_amount': 0.20,
                'module': 'dexbot.strategies.relative_orders',
                'partial_fill_threshold': 30.0,
                'price_change_threshold': 2.0,
                'relative_order_size': False,
                'reset_on_partial_fill': False,
                'reset_on_price_change': False,
                'spread': 5.0
            }
        }
    }
    return TEST_CONFIG


class Test_OrderEngine:
    def setup_class(self):
        self.yml_data = test_fixtures()
        self.config = Config(config=self.yml_data)
        self.bitshares_instance = BitShares(node=self.config['node'])

        logging.info("Bitshares Price Feed Test")

        for worker_name, worker in self.config["workers"].items():
            logging.info(worker_name, worker)
            self.pair = self.config["workers"][worker_name]["market"]
            self.market = Market(self.config["workers"][worker_name]["market"])
            self.orderEngine = BitsharesOrderEngine(worker_name, config=self.config, market=self.market,
                                               bitshares_instance=self.bitshares_instance)
            logging.info("instantiating Bitshares order engine")

    def teardown_class(self):
        pass

    def setup_method(self):
        pass

    def teardown_method(self):
        pass

    def test_all_own_orders(self):
        orders = self.orderEngine.all_own_orders()
        logging.info("All own orders: ".format(orders))

    def test_market(self):
        logging.info(self.market.ticker())


if __name__ == '__main__':
    cur_dir = os.path.dirname(__file__)
    test_file = os.path.join(cur_dir, 'bitshares_engine_test.py')
    pytest.main(['--capture=no', test_file])
