import pytest
import time
import copy
import logging
import random
from dexbot.strategies.base import StrategyBase
from dexbot.strategies.relative_orders import Strategy

log = logging.getLogger("dexbot")


@pytest.fixture(scope='session')
def assets(create_asset):
    """ Create some assets with different precision
    """
    create_asset('BASEA', 3)
    create_asset('QUOTEA', 8)
    create_asset('BASEB', 8)
    create_asset('QUOTEB', 3)


@pytest.fixture(scope='module')
def base_account(assets, prepare_account):
    """ Factory to generate random account with pre-defined balances
    """

    def func():
        account = prepare_account({'BASEA': 10000, 'QUOTEA': 100, 'BASEB': 10000, 'QUOTEB': 100, 'TEST': 1000})
        return account

    return func


@pytest.fixture(scope='module')
def account(base_account):
    """ Prepare worker account with some balance
    """
    return base_account()


@pytest.fixture(scope='session')
def ro_worker_name():
    """ Fixture to share ro Orders worker name
    """
    return 'ro-worker'


@pytest.fixture
def config(bitshares, account, ro_worker_name):
    """ Define worker's config with variable assets

        This fixture should be function-scoped to use new fresh bitshares account for each test
    """
    worker_name = ro_worker_name
    config = {
        'node': '{}'.format(bitshares.rpc.url),
        'workers': {
            worker_name: {
                'account': '{}'.format(account),
                'amount': 1.0,
                'center_price': 1,
                'center_price_depth': 0.0,
                'center_price_dynamic': False,
                'center_price_offset': False,
                'custom_expiration': False,
                'dynamic_spread': False,
                'dynamic_spread_factor': 10,
                'expiration_time': 157680000.0,
                'external_feed': False,
                'external_price_source': 'null',
                'fee_asset': 'TEST',
                'manual_offset': 0.0,
                'market': 'QUOTEA/BASEA',
                'market_depth_amount': 4,
                'module': 'dexbot.strategies.relative_orders',
                'partial_fill_threshold': 30.0,
                'price_change_threshold': 2.0,
                'relative_order_size': False,
                'reset_on_partial_fill': True,
                'reset_on_price_change': False,
                'spread': 5.0,
            }
        },
    }
    return config


@pytest.fixture
def config_other_account(config, base_account, ro_worker_name):
    """ Config for other account which simulates foreign trader
    """
    config = copy.deepcopy(config)
    worker_name = ro_worker_name
    config['workers'][worker_name]['account'] = base_account()
    return config


@pytest.fixture
def base_worker(bitshares, ro_worker_name):
    """ Fixture to create a worker
    """
    workers = []

    def _base_worker(config, worker_name=ro_worker_name):
        worker = Strategy(name=worker_name, config=config, bitshares_instance=bitshares)
        worker.min_check_interval = 0
        workers.append(worker)
        return worker

    yield _base_worker
    for worker in workers:
        worker.cancel_all_orders()
        worker.bitshares.txbuffer.clear()
        worker.bitshares.bundle = False


@pytest.fixture
def ro_worker(base_worker, config):
    """ Basic RO worker
    """
    worker = base_worker(config)
    return worker


@pytest.fixture
def other_worker(ro_worker_name, config_other_account):
    worker = StrategyBase(name=ro_worker_name, config=config_other_account)
    yield worker
    worker.cancel_all_orders()
    time.sleep(1.1)


def empty_ticker_workaround(worker):
    bid = worker.get_highest_market_buy_order()
    sell_price = bid['price'] / 1.01
    to_sell = bid['quote']['amount'] / 10
    log.debug('Executing empty ticker workaround')
    worker.place_market_sell_order(to_sell, sell_price)


@pytest.fixture
def other_orders(other_worker):
    """ Place some orders from second account to simulate foreign trader
    """
    worker = other_worker
    worker.place_market_buy_order(10, 0.5)
    worker.place_market_sell_order(10, 1.5)
    if float(worker.market.ticker().get('highestBid')) == 0:
        empty_ticker_workaround(worker)
    return worker


@pytest.fixture
def other_orders_random(other_worker):
    """ Place some number of random orders within some range
    """
    worker = other_worker
    lower_bound = 0.3
    upper_bound = 2
    center = 1
    num_orders = 10
    for _ in range(num_orders):
        price = random.uniform(lower_bound, center)  # nosec
        amount = random.uniform(0.5, 10)  # nosec
        worker.place_market_buy_order(amount, price)
    for _ in range(num_orders):
        price = random.uniform(center, upper_bound)  # nosec
        amount = random.uniform(0.5, 10)  # nosec
        worker.place_market_sell_order(amount, price)


@pytest.fixture
def config_multiple_workers_1(bitshares, account):
    """ Prepares config with multiple workers on same account
    """
    config = {
        'node': '{}'.format(bitshares.rpc.url),
        'workers': {
            'ro-worker-1': {
                'account': '{}'.format(account),
                'amount': 1.0,
                'center_price': 1,
                'center_price_depth': 0.0,
                'center_price_dynamic': False,
                'center_price_offset': False,
                'custom_expiration': False,
                'dynamic_spread': False,
                'dynamic_spread_factor': 10,
                'expiration_time': 157680000.0,
                'external_feed': False,
                'external_price_source': 'null',
                'fee_asset': 'TEST',
                'manual_offset': 0.0,
                'market': 'QUOTEA/BASEA',
                'market_depth_amount': 4,
                'module': 'dexbot.strategies.relative_orders',
                'partial_fill_threshold': 30.0,
                'price_change_threshold': 2.0,
                'relative_order_size': False,
                'reset_on_partial_fill': True,
                'reset_on_price_change': False,
                'spread': 5.0,
            },
            'ro-worker-2': {
                'account': '{}'.format(account),
                'amount': 1.0,
                'center_price': 10,  # note price difference
                'center_price_depth': 0.0,
                'center_price_dynamic': False,
                'center_price_offset': False,
                'custom_expiration': False,
                'dynamic_spread': False,
                'dynamic_spread_factor': 10,
                'expiration_time': 157680000.0,
                'external_feed': False,
                'external_price_source': 'null',
                'fee_asset': 'TEST',
                'manual_offset': 0.0,
                'market': 'QUOTEB/BASEA',
                'market_depth_amount': 4,
                'module': 'dexbot.strategies.relative_orders',
                'partial_fill_threshold': 30.0,
                'price_change_threshold': 2.0,
                'relative_order_size': False,
                'reset_on_partial_fill': True,
                'reset_on_price_change': False,
                'spread': 5.0,
            },
        },
    }
    return config
