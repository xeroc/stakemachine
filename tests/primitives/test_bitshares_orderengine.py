import logging

log = logging.getLogger("dexbot")
log.setLevel(logging.DEBUG)


def test_init(worker):
    pass


def test_place_market_sell_order(worker):
    worker.place_market_sell_order(1, 1)
    assert len(worker.own_orders) == 1
