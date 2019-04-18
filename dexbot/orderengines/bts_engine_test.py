from bitshares.bitshares import BitShares
from bitshares.market import Market

from dexbot.config import Config

from dexbot.orderengines.bts_engine import BitsharesOrderEngine
from dexbot.strategies.base import StrategyBase

def fixture_data():

    TEST_CONFIG = {
        'node': 'wss://api.fr.bitsharesdex.com/ws',
        'workers': {
                'worker 1': {
                    'account': 'octet5',
                    'amount': 1.0,
                    'center_price': 0.3,
                    'center_price_depth': 0.0,
                    'center_price_dynamic': False,
                    'center_price_offset': False,
                    'custom_expiration': False,
                    'dynamic_spread': False,
                    'dynamic_spread_factor': 1.0,
                    'expiration_time': 157680000.0,
                    'external_feed': False,
                    'external_price_source': 'null',
                    'fee_asset': 'BTS',
                    'manual_offset': 0.0,
                    'market': 'OPEN.BTC/BTS',
                    'market_depth_amount': 0.0,
                    'module': 'dexbot.strategies.relative_orders',
                    'partial_fill_threshold': 30.0,
                    'price_change_threshold': 2.0,
                    'relative_order_size': False,
                    'reset_on_partial_fill': True,
                    'reset_on_price_change': False,
                    'spread': 5.0
                }
        }
    }
    return TEST_CONFIG


yml_data = fixture_data()
config = Config(config=yml_data)
bts = BitShares(node=config['node'])
print("Bitshares Price Feed Test")


for worker_name, worker in config["workers"].items():
    print(worker_name)
    print(worker)
    pair = config["workers"][worker_name]["market"]
    market = Market(config["workers"][worker_name]["market"])
    print(pair)

    print("instantiating StrategyBase as a base comparison")
    strategy = StrategyBase(worker_name, config=config, bitshares_instance=bts)

    print("instantiating Bitshares order engine")
    orderEngine = BitsharesOrderEngine(worker_name, config=config, bitshares_instance=bts)



