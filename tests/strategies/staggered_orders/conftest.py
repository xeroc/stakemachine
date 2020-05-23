import copy
import logging
import os
import tempfile
import time

import pytest
from bitshares.amount import Amount

from dexbot.storage import Storage
from dexbot.strategies.base import StrategyBase
from dexbot.strategies.staggered_orders import Strategy

log = logging.getLogger("dexbot.per_worker")
handler = logging.StreamHandler()
formatter2 = logging.Formatter('%(asctime)s (%(module)s:%(lineno)d) - %(worker_name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter2)
log.addHandler(handler)

log = logging.getLogger("dexbot")
log.setLevel(logging.DEBUG)

MODES = ['mountain', 'valley', 'neutral', 'buy_slope', 'sell_slope']


@pytest.fixture(scope='session')
def assets(create_asset):
    """Create some assets with different precision."""
    create_asset('BASEA', 3)
    create_asset('QUOTEA', 8)
    create_asset('BASEB', 8)
    create_asset('QUOTEB', 3)


@pytest.fixture(scope='module')
def base_account(assets, prepare_account):
    """Factory to generate random account with pre-defined balances."""

    def func():
        account = prepare_account({'BASEA': 10000, 'QUOTEA': 100, 'BASEB': 10000, 'QUOTEB': 100, 'TEST': 1000})
        return account

    return func


@pytest.fixture
def account(base_account):
    """Prepare worker account with some balance."""
    return base_account()


@pytest.fixture
def account_only_base(assets, prepare_account):
    """Prepare worker account with only BASE assets balance."""
    account = prepare_account({'BASEA': 1000, 'BASEB': 1000, 'TEST': 1000})
    return account


@pytest.fixture
def account_1_sat(assets, prepare_account):
    """Prepare worker account to simulate XXX/BTC trading near zero prices."""
    account = prepare_account({'BASEB': 0.02, 'QUOTEB': 10000000, 'TEST': 1000})
    return account


@pytest.fixture(scope='session')
def so_worker_name():
    """Fixture to share Staggered Orders worker name."""
    return 'so-worker'


@pytest.fixture()
def config(request, bitshares, account, so_worker_name):
    """
    Define worker's config with variable assets.

    This fixture should be function-scoped to use new fresh bitshares account for each test
    """
    worker_name = so_worker_name
    config = {
        'node': '{}'.format(bitshares.rpc.url),
        'workers': {
            worker_name: {
                'account': '{}'.format(account),
                'market': 'QUOTEA/BASEA',
                'module': 'dexbot.strategies.staggered_orders',
                'mode': 'valley',
                'center_price': 100.0,
                'center_price_dynamic': False,
                'fee_asset': 'TEST',
                'lower_bound': 90.0,
                'spread': 2.0,
                'increment': 1.0,
                'upper_bound': 110.0,
                'operational_depth': 10,
            }
        },
    }
    return config


@pytest.fixture(params=MODES)
def config_variable_modes(request, config, so_worker_name):
    """Test config which tests all modes."""
    worker_name = so_worker_name
    config = copy.deepcopy(config)
    config['workers'][worker_name]['mode'] = request.param
    return config


@pytest.fixture
def config_only_base(config, so_worker_name, account_only_base):
    """Config which uses an account with only BASE asset."""
    worker_name = so_worker_name
    config = copy.deepcopy(config)
    config['workers'][worker_name]['account'] = account_only_base
    return config


@pytest.fixture
def config_1_sat(so_worker_name, bitshares, account_1_sat):
    """Config to set up a worker on market with center price around 1 sats."""
    worker_name = so_worker_name
    config = {
        'node': '{}'.format(bitshares.rpc.url),
        'workers': {
            worker_name: {
                'account': '{}'.format(account_1_sat),
                'market': 'QUOTEC/BASEC',
                'module': 'dexbot.strategies.staggered_orders',
                'mode': 'valley',
                'center_price': 0.00000001,
                'center_price_dynamic': False,
                'fee_asset': 'TEST',
                'lower_bound': 0.000000002,
                'spread': 30.0,
                'increment': 10.0,
                'upper_bound': 0.00000002,
                'operational_depth': 10,
            }
        },
    }
    return config


@pytest.fixture
def config_multiple_workers_1(bitshares, account):
    """
    Prepares config with multiple SO workers on same account.

    This fixture should be function-scoped to use new fresh bitshares account for each test
    """
    config = {
        'node': '{}'.format(bitshares.rpc.url),
        'workers': {
            'so-worker-1': {
                'account': '{}'.format(account),
                'market': 'QUOTEA/BASEA',
                'module': 'dexbot.strategies.staggered_orders',
                'mode': 'valley',
                'center_price': 100.0,
                'center_price_dynamic': False,
                'fee_asset': 'TEST',
                'lower_bound': 90.0,
                'spread': 2.0,
                'increment': 1.0,
                'upper_bound': 110.0,
                'operational_depth': 10,
            },
            'so-worker-2': {
                'account': '{}'.format(account),
                'market': 'QUOTEB/BASEA',
                'module': 'dexbot.strategies.staggered_orders',
                'mode': 'valley',
                'center_price': 100.0,
                'center_price_dynamic': False,
                'fee_asset': 'TEST',
                'lower_bound': 90.0,
                'spread': 2.0,
                'increment': 1.0,
                'upper_bound': 110.0,
                'operational_depth': 10,
            },
        },
    }
    return config


@pytest.fixture
def config_multiple_workers_2(config_multiple_workers_1):
    """
    Prepares config with multiple SO workers on same account.

    This fixture should be function-scoped to use new fresh bitshares account for each test
    """
    config = copy.deepcopy(config_multiple_workers_1)
    config['workers']['so-worker-1']['market'] = 'QUOTEA/BASEA'
    config['workers']['so-worker-2']['market'] = 'QUOTEA/BASEB'

    return config


@pytest.fixture
def config_other_account(config, base_account, so_worker_name):
    """ Config for other account which simulates foreign trader
    """
    config = copy.deepcopy(config)
    worker_name = so_worker_name
    config['workers'][worker_name]['account'] = base_account()
    return config


@pytest.fixture
def base_worker(bitshares, so_worker_name, storage_db):
    workers = []

    def _base_worker(config, worker_name=so_worker_name):
        worker = Strategy(config=config, name=worker_name, bitshares_instance=bitshares)
        # Set market center price to avoid calling of maintain_strategy()
        worker.market_center_price = worker.worker['center_price']
        # Prevent maintenance bypass during tests
        worker.min_check_interval = 0
        worker.max_check_interval = 0.00000000001  # should differ from min_check_interval!
        worker.check_interval = worker.min_check_interval
        log.info('Initialized {} on account {}'.format(worker_name, worker.account.name))
        workers.append(worker)
        return worker

    yield _base_worker

    # We need to make sure no orders left after test finished
    for worker in workers:
        worker.cancel_all_orders()
        # Workaround to purge all worker data after test
        worker.purge_all_local_worker_data(worker.worker_name)
        worker.bitshares.txbuffer.clear()
        worker.bitshares.bundle = False


@pytest.fixture(scope='session')
def storage_db(so_worker_name):
    """ Prepare custom sqlite database to not mess with main one
    """
    _, db_file = tempfile.mkstemp()  # noqa: F811
    storage = Storage(so_worker_name, db_file=db_file)
    yield storage
    os.unlink(db_file)


@pytest.fixture
def worker(base_worker, config):
    """Worker to test in single mode (for methods which not required to be tested against all modes)"""
    worker = base_worker(config)
    return worker


@pytest.fixture
def worker2(base_worker, config_variable_modes):
    """Worker to test all modes."""
    worker = base_worker(config_variable_modes)
    return worker


@pytest.fixture
def other_worker(so_worker_name, config_other_account):
    """ Foreign trader
    """
    worker = StrategyBase(name=so_worker_name, config=config_other_account)
    yield worker
    worker.cancel_all_orders()


@pytest.fixture
def init_empty_balances(worker, bitshares):
    # Defaults are None, which breaks place_virtual_xxx_order()
    worker.quote_balance = Amount(0, worker.market['quote']['symbol'], bitshares_instance=bitshares)
    worker.base_balance = Amount(0, worker.market['base']['symbol'], bitshares_instance=bitshares)


@pytest.fixture
def orders1(worker, bitshares, init_empty_balances):
    """
    Place 1 buy+sell real order, and 1 buy+sell virtual orders with prices outside of the range.

    Note: this fixture don't calls refresh.xxx() intentionally!
    """
    # Prices outside of the range
    buy_price = 1  # price for test_refresh_balances()
    sell_price = worker.upper_bound + 1
    # Place real orders
    worker.place_market_buy_order(10, buy_price)
    worker.place_market_sell_order(10, sell_price)
    # Place virtual orders
    worker.place_virtual_buy_order(10, buy_price)
    worker.place_virtual_sell_order(10, sell_price)
    yield worker
    # Remove orders on teardown
    worker.cancel_all_orders()
    worker.virtual_orders = []
    # Need to wait until trxs will be included into block because several consequent runs of tests which uses this
    # fixture will cause identical cancel trxs, which is not allowed by the node
    time.sleep(1.1)


@pytest.fixture
def orders2(worker):
    """Place buy+sell real orders near center price."""
    buy_price = worker.market_center_price - 1
    sell_price = worker.market_center_price + 1
    # Place real orders
    worker.place_market_buy_order(1, buy_price)
    worker.place_market_sell_order(1, sell_price)
    worker.refresh_orders()
    worker.refresh_balances()
    yield worker
    worker.cancel_all_orders()
    worker.virtual_orders = []
    time.sleep(1.1)


@pytest.fixture
def orders3(worker):
    """Place buy+sell virtual orders near center price."""
    worker.refresh_balances()
    buy_price = worker.market_center_price - 1
    sell_price = worker.market_center_price + 1
    # Place virtual orders
    worker.place_virtual_buy_order(1, buy_price)
    worker.place_virtual_sell_order(1, sell_price)
    worker.refresh_orders()
    yield worker
    worker.virtual_orders = []


@pytest.fixture
def orders4(worker, orders1):
    """Just wrap orders1, but refresh balances in addition."""
    worker.refresh_balances()
    yield orders1


@pytest.fixture
def orders5(worker2):
    """Place buy+sell virtual orders at some distance from center price, and buy+sell real orders at 1 order distance
    from center."""
    worker = worker2

    worker.refresh_balances()

    # Virtual orders outside of operational depth
    buy_price = worker.market_center_price / (1 + worker.increment) ** (worker.operational_depth * 2)
    sell_price = worker.market_center_price * (1 + worker.increment) ** (worker.operational_depth * 2)
    worker.place_virtual_buy_order(1, buy_price)
    worker.place_virtual_sell_order(1, sell_price)

    # Virtual orders within operational depth
    buy_price = worker.market_center_price / (1 + worker.increment) ** (worker.operational_depth // 2)
    sell_price = worker.market_center_price * (1 + worker.increment) ** (worker.operational_depth // 2)
    worker.place_virtual_buy_order(1, buy_price)
    worker.place_virtual_sell_order(1, sell_price)

    # Real orders outside of operational depth
    buy_price = worker.market_center_price / (1 + worker.increment) ** (worker.operational_depth + 2)
    sell_price = worker.market_center_price * (1 + worker.increment) ** (worker.operational_depth + 2)
    worker.place_market_buy_order(1, buy_price)
    worker.place_market_sell_order(1, sell_price)

    # Real orders at 2 increment distance from the center
    buy_price = worker.market_center_price / (1 + worker.increment) ** 2
    sell_price = worker.market_center_price * (1 + worker.increment) ** 2
    worker.place_market_buy_order(1, buy_price)
    worker.place_market_sell_order(1, sell_price)

    worker.refresh_orders()
    yield worker
    worker.virtual_orders = []
    worker.cancel_all_orders()
    time.sleep(1.1)


@pytest.fixture
def partially_filled_order(worker):
    """Create partially filled order."""
    order = worker.place_market_buy_order(100, 1, returnOrderId=True)
    worker.place_market_sell_order(20, 1)
    worker.refresh_balances()
    # refresh order
    order = worker.get_order(order)
    yield order
    worker.cancel_all_orders()
    time.sleep(1.1)


@pytest.fixture(scope='session')
def increase_until_allocated():
    """
    Run increase_order_sizes() until funds are allocated.

    :param Strategy worker: worker instance
    """

    def func(worker):
        buy_increased = False
        sell_increased = False

        while not buy_increased or not sell_increased:
            worker.refresh_orders()
            worker.refresh_balances(use_cached_orders=True)
            buy_increased = worker.increase_order_sizes('base', worker.base_balance, worker.buy_orders)
            sell_increased = worker.increase_order_sizes('quote', worker.quote_balance, worker.sell_orders)
        worker.refresh_orders()
        log.info('Increase done')

    return func


@pytest.fixture(scope='session')
def maintain_until_allocated():
    """
    Run maintain_strategy() on a specific worker until funds are allocated.

    :param Strategy worker: worker instance
    """

    def func(worker):
        while True:
            worker.maintain_strategy()
            if not worker.check_interval == worker.min_check_interval:
                # Use "if" statement instead of putting this into a "while" to avoid waiting max_check_interval on last
                # run
                break
            time.sleep(worker.min_check_interval)
        log.info('Allocation done')

    return func


@pytest.fixture
def do_initial_allocation(maintain_until_allocated):
    """
    Run maintain_strategy() to make an initial allocation of funds.

    :param Strategy worker: initialized worker
    :param str mode: SO mode (valley, mountain etc)
    """

    def func(worker, mode):
        worker.mode = mode
        worker.cancel_all_orders()
        maintain_until_allocated(worker)
        worker.refresh_orders()
        worker.refresh_balances(use_cached_orders=True)
        worker.check_interval = 0
        log.info('Initial allocation done')

        return worker

    return func
