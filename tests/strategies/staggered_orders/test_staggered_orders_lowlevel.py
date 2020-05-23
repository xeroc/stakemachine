import logging

# Turn on debug for dexbot logger
logger = logging.getLogger("dexbot")
logger.setLevel(logging.DEBUG)


###################
# Lower-level methods used by higher-level methods
###################


def test_cancel_orders_wrapper(orders4):
    worker = orders4

    # test real order
    orders = worker.own_orders
    before = len(orders)
    worker.cancel_orders_wrapper(orders[0])
    after = len(worker.own_orders)
    assert before - after == 1
    # test virtual order
    before = len(worker.virtual_orders)
    worker.cancel_orders_wrapper(worker.virtual_orders[0])
    after = len(worker.virtual_orders)
    assert before - after == 1


def test_place_virtual_buy_order(worker, init_empty_balances):
    worker.place_virtual_buy_order(100, 1)
    assert len(worker.virtual_orders) == 1
    assert worker.virtual_orders[0]['base']['amount'] == 100
    assert worker.virtual_orders[0]['for_sale']['amount'] == 100
    assert worker.virtual_orders[0]['quote']['amount'] == 100
    assert worker.virtual_orders[0]['price'] == 1


def test_place_virtual_sell_order(worker, init_empty_balances):
    worker.place_virtual_sell_order(100, 1)
    assert len(worker.virtual_orders) == 1
    assert worker.virtual_orders[0]['base']['amount'] == 100
    assert worker.virtual_orders[0]['for_sale']['amount'] == 100
    assert worker.virtual_orders[0]['quote']['amount'] == 100
    assert worker.virtual_orders[0]['price'] == 1


def test_sync_current_orders(orders1):
    """Sync current orders then fetch them back and compare to these orders."""
    worker = orders1
    worker.refresh_orders()
    worker.sync_current_orders()
    fetched = set(worker.fetch_orders_extended(custom='current', return_ids_only=True))
    current_all_orders = worker.buy_orders + worker.sell_orders
    current_ids = set([order['id'] for order in current_all_orders])
    assert fetched == current_ids


def test_dump_initial_orders(orders1):
    worker = orders1
    worker.dump_initial_orders()
    fetched = worker.fetch_orders_extended(custom='initial')
    current = worker.buy_orders + worker.sell_orders
    assert len(fetched) == len(current)

    # Compare orders bases to be identical (cannot compare order ids because they are different for initial orders)
    bases_fetched = [entry['order']['base'] for entry in fetched]
    bases_actual = [dict(order['base']) for order in current]
    for element in bases_actual:
        assert element in bases_fetched


def test_drop_initial_orders(orders1):
    worker = orders1
    worker.dump_initial_orders()
    worker.drop_initial_orders()
    fetched = worker.fetch_orders_extended(custom='initial')
    assert len(fetched) == 0
