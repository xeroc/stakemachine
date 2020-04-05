import time

import pytest
from dexbot.orderengines.bitshares_engine import BitsharesOrderEngine
from dexbot.strategies.base import StrategyBase


@pytest.fixture(scope='module')
def worker_name():
    return 'primitive'


@pytest.fixture(scope='session')
def assets(create_asset):
    """ Create some assets with different precision
    """
    create_asset('BASEA', 3)
    create_asset('QUOTEA', 8)


@pytest.fixture(scope='module')
def base_account(assets, prepare_account):
    """ Factory to generate random account with pre-defined balances
    """

    def func():
        account = prepare_account({'BASEA': 10000, 'QUOTEA': 100, 'TEST': 1000})
        return account

    return func


@pytest.fixture(scope='module')
def account(base_account):
    """ Prepare worker account with some balance
    """
    return base_account()


@pytest.fixture()
def config(bitshares, account, worker_name):
    """ Define worker's config with variable assets

        This fixture should be function-scoped to use new fresh bitshares account for each test
    """
    worker_name = worker_name
    config = {
        'node': '{}'.format(bitshares.rpc.url),
        'workers': {
            worker_name: {
                'account': '{}'.format(account),
                'fee_asset': 'TEST',
                'market': 'QUOTEA/BASEA',
                'module': 'dexbot.strategies.base',
            }
        },
    }
    return config


@pytest.fixture()
def orderengine(worker_name, config, bitshares):
    worker = BitsharesOrderEngine(worker_name, config=config, bitshares_instance=bitshares)
    yield worker
    worker.cancel_all_orders()
    time.sleep(1.1)


@pytest.fixture()
def strategybase(worker_name, config, bitshares):
    worker = StrategyBase(worker_name, config=config, bitshares_instance=bitshares)
    yield worker
    worker.cancel_all_orders()
    time.sleep(1.1)
