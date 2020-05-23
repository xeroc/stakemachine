import logging

import pytest

log = logging.getLogger("dexbot")
log.setLevel(logging.DEBUG)


@pytest.fixture()
def worker(strategybase):
    return strategybase


@pytest.mark.mandatory
def test_init(worker):
    pass


@pytest.mark.parametrize('asset', ['base', 'quote'])
def test_get_operational_balance(asset, worker, monkeypatch):
    share = 0.1

    def get_share(*args):
        return share

    symbol = worker.market[asset]['symbol']
    balance = worker.balance(symbol)
    op_balance = worker.get_operational_balance()
    assert op_balance[asset] == balance['amount']

    monkeypatch.setattr(worker, 'get_worker_share_for_asset', get_share)
    op_balance = worker.get_operational_balance()
    assert op_balance[asset] == balance['amount'] * share
