import logging

import pytest

log = logging.getLogger("dexbot")
log.setLevel(logging.DEBUG)


@pytest.fixture()
def worker(orderengine):
    return orderengine


@pytest.mark.mandatory
def test_init(worker):
    pass


def test_place_market_sell_order(worker):
    worker.place_market_sell_order(1, 1)
    assert len(worker.own_orders) == 1

    order = worker.place_market_sell_order(1, 10, returnOrderId=True, invert=True)
    assert order['price'] == 10
