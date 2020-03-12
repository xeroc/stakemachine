import logging
import math
import time

import pytest
from bitshares.market import Market

# Turn on debug for dexbot logger
log = logging.getLogger("dexbot")
log.setLevel(logging.DEBUG)


def test_configure(ro_worker, config):
    worker = ro_worker
    cf = worker.config
    assert config == cf


def test_error(ro_worker):
    """ Event method return None
    """
    worker = ro_worker
    worker.error()
    assert worker.disabled is True


def test_amount_to_sell(ro_worker):
    worker = ro_worker
    expected_amount = worker.worker['amount']

    worker.calculate_order_prices()
    amount_to_sell = worker.amount_to_sell
    assert amount_to_sell == expected_amount

    worker.is_relative_order_size = True
    quote_balance = float(worker.balance(worker.market['quote']))
    amount_to_sell = worker.amount_to_sell
    expected_amount = quote_balance * (expected_amount / 100)
    assert amount_to_sell == expected_amount


def test_amount_to_buy(ro_worker):
    worker = ro_worker
    worker.calculate_order_prices()

    expected_amount = worker.worker.get('amount')
    assert worker.amount_to_buy == expected_amount

    worker.is_relative_order_size = True
    base_balance = float(worker.balance(worker.market['base']))
    expected_amount = base_balance * (expected_amount / 100) / worker.buy_price
    assert worker.amount_to_buy == expected_amount


def test_calculate_order_prices(ro_worker):
    worker = ro_worker
    worker.calculate_order_prices()

    expected_buy_price = worker.center_price / math.sqrt(1 + worker.spread)
    expected_sell_price = worker.center_price * math.sqrt(1 + worker.spread)

    assert worker.buy_price == expected_buy_price
    assert worker.sell_price == expected_sell_price


def test_calculate_order_prices_dynamic_spread(ro_worker, other_orders):
    """ Check if dynamic spread is working overall
    """
    worker = ro_worker
    worker.calculate_order_prices()
    buy_price_before = worker.buy_price
    sell_price_before = worker.sell_price

    worker.dynamic_spread = True
    worker.calculate_order_prices()

    # Dynamic spread is calculated according to other_orders fixture, which should give us different prices
    assert worker.buy_price < buy_price_before
    assert worker.sell_price > sell_price_before
    # Also check if dynamic spread is reasonable
    assert worker.sell_price / worker.buy_price - 1 < 0.3


def test_calculate_order_prices_cp_depth(ro_worker, other_orders_random):
    worker = ro_worker
    worker.cancel_all_orders()
    worker.calculate_order_prices()
    buy_price_before = worker.buy_price
    sell_price_before = worker.sell_price

    worker.is_center_price_dynamic = True
    worker.center_price_depth = 10
    worker.calculate_order_prices()
    assert buy_price_before != worker.buy_price
    assert sell_price_before != worker.sell_price

    spread_before = sell_price_before / buy_price_before - 1
    spread_after = worker.sell_price / worker.buy_price - 1
    assert spread_before == pytest.approx(spread_after)


def test_update_orders(ro_worker):
    worker = ro_worker
    worker.update_orders()
    orders = worker.own_orders

    assert len(worker.own_orders) == 2

    for order in orders:
        if order['base']['symbol'] == worker.market['base']['symbol']:
            assert order['price'] == pytest.approx(worker.buy_price, rel=(10 ** -worker.market['base']['precision']))
        else:
            order.invert()
            assert order['price'] == pytest.approx(worker.sell_price, rel=(10 ** -worker.market['base']['precision']))


def test_calculate_center_price(ro_worker, other_orders):
    """ Test dynamic center price calculation
    """
    worker = ro_worker
    highest_bid = float(worker.market.ticker().get('highestBid'))
    lowest_ask = float(worker.market.ticker().get('lowestAsk'))
    cp = highest_bid * math.sqrt(lowest_ask / highest_bid)
    center_price = worker.calculate_center_price()
    assert cp == center_price


@pytest.mark.parametrize('variant', ['no_shift', 'base_shift', 'quote_shift'])
def test_calculate_asset_offset(variant, ro_worker, other_orders, monkeypatch):
    """ Check if automatic asset offset calculation works

        Instead of duplicating offset calculation code, test offset at different balance and see does it make sense or
        not.
    """

    def mocked_balance_b(*args):
        # zero BASE
        return {'quote': float(worker.balance(worker.market['quote'])), 'base': 0}

    def mocked_balance_q(*args):
        # zero QUOTE
        return {'quote': 0, 'base': float(worker.balance(worker.market['base']))}

    worker = ro_worker
    if variant == 'base_shift':
        monkeypatch.setattr(worker, "count_asset", mocked_balance_b)
    elif variant == 'quote_shift':
        monkeypatch.setattr(worker, "count_asset", mocked_balance_q)
    adjusted_cp = worker.calculate_asset_offset(worker.center_price, [], worker.spread)
    log.debug('Adjusted CP: {}'.format(adjusted_cp))
    log.debug(worker.market.ticker())
    # Expect offset shift no more than 30%
    assert abs(worker.center_price - adjusted_cp) < 0.3 * worker.center_price


def test_calculate_center_price_with_manual_offset(ro_worker):
    worker = ro_worker
    center_price = worker.center_price
    manual_offset = 0.1
    calculate_offset = worker.calculate_manual_offset(center_price=center_price, manual_offset=manual_offset)
    assert calculate_offset == center_price * (1 + manual_offset)

    manual_offset = -0.1
    calculate_offset = worker.calculate_manual_offset(center_price=center_price, manual_offset=manual_offset)
    assert calculate_offset == center_price / (1 + abs(manual_offset))


def test_check_orders(ro_worker):
    """ check_orders() should result in 2 orders placed if no own orders
    """
    worker = ro_worker
    worker.check_orders()
    assert len(worker.own_orders) == 2


def test_check_orders_fully_filled(ro_worker, other_worker):
    """ When our order is fully filled, the strategy should place a new one
    """
    worker = ro_worker
    worker2 = other_worker
    log.debug('worker1 account name: {}'.format(worker.account.name))
    log.debug('worker2 account name: {}'.format(worker2.account.name))

    worker.update_orders()

    # Own order fully filled
    own_buy_orders = worker.get_own_buy_orders()
    own_sell_orders = worker.get_own_sell_orders()
    log.debug('RO orders: {}'.format(worker.own_orders))
    log.debug('buy orders: {}'.format(own_buy_orders))
    log.debug('sell orders: {}'.format(own_sell_orders))
    assert len(worker.own_orders) == 2
    to_sell = own_buy_orders[0]['quote']['amount']
    sell_price = own_buy_orders[0]['price'] / 1.01
    log.debug('Sell {} @ {}'.format(to_sell, sell_price))
    worker2.place_market_sell_order(to_sell, sell_price)
    log.debug('RO orders: {}'.format(worker.own_orders))
    assert len(worker.own_orders) == 1

    to_buy = own_sell_orders[0]['base']['amount']
    buy_price = own_sell_orders[0]['price'] * 10
    log.debug('{}'.format(own_sell_orders))
    log.debug('Buy {} @ {}'.format(to_buy, buy_price))
    worker2.place_market_buy_order(to_buy, buy_price)
    log.info('Filled RO orders from another account')
    log.debug('RO orders: {}'.format(worker.own_orders))
    log.debug('worker2 orders: {}'.format(worker2.own_orders))

    assert len(worker.own_orders) == 0

    worker.update_orders()

    # Expect new orders placed
    assert len(worker.own_orders) == 2


def test_check_orders_partially_filled(ro_worker, other_worker):
    """ When our order is partially filled more than threshold, order should be replaced
    """
    worker2 = other_worker
    worker = ro_worker
    worker.update_orders()

    own_buy_orders = worker.get_own_buy_orders()
    own_sell_orders = worker.get_own_sell_orders()
    log.debug('RO orders: {}'.format(worker.own_orders))

    to_sell = own_buy_orders[0]['quote']['amount'] * worker.partial_fill_threshold * 1.02
    sell_price = own_buy_orders[0]['price'] / 1.01
    log.debug('Sell {} @ {}'.format(to_sell, sell_price))
    worker2.place_market_sell_order(to_sell, sell_price)

    to_buy = own_sell_orders[0]['base']['amount'] * worker.partial_fill_threshold * 1.02
    buy_price = own_sell_orders[0]['price'] * 1.01
    log.debug('Buy {} @ {}'.format(to_buy, buy_price))
    worker2.place_market_buy_order(to_buy, buy_price)
    log.info('Filled RO orders from another account')
    log.debug('RO orders: {}'.format(worker.own_orders))

    worker.check_orders()

    # Expect new orders replaced with full-sized ones
    assert len(worker.own_orders) == 2
    for order in worker.own_orders:
        assert order['base']['amount'] == order['for_sale']['amount']


def test_check_orders_reset_on_price_change(ro_worker, other_orders):
    """ Check if orders resetted on center price change
    """
    worker2 = other_orders

    worker = ro_worker
    worker.is_center_price_dynamic = True
    worker.is_reset_on_price_change = True
    worker.price_change_threshold = 0.001
    worker.center_price_depth = 0

    log.debug('worker1 orders: {}'.format(worker.own_orders))
    log.debug('worker2 orders: {}'.format(worker2.own_orders))

    # Significantly shift center price by putting sell order close to worker buy order
    own_buy_orders = worker.get_own_buy_orders()
    to_sell = own_buy_orders[0]['quote']['amount']
    sell_price = own_buy_orders[0]['price'] * 1.01
    log.debug('Sell {} @ {}'.format(to_sell, sell_price))
    worker2.place_market_sell_order(to_sell, sell_price)
    log.debug('worker1 orders: {}'.format(worker.own_orders))
    log.debug('worker2 orders: {}'.format(worker2.own_orders))

    # Expect new orders
    orders_before = worker.own_orders
    worker.check_orders()
    assert worker.own_orders != orders_before


def test_get_own_last_trade(base_account, base_worker, config_multiple_workers_1, other_worker):
    worker1 = base_worker(config_multiple_workers_1, worker_name='ro-worker-1')
    worker2 = base_worker(config_multiple_workers_1, worker_name='ro-worker-2')
    worker3 = base_account()
    market1 = Market(worker1.worker["market"])
    market2 = Market(worker2.worker["market"])

    log.debug('worker1 orders: {}'.format(worker1.own_orders))
    log.debug('worker2 orders: {}'.format(worker2.own_orders))

    # Fill worker's order from different account
    buy_orders1 = worker1.get_own_buy_orders()
    to_sell = buy_orders1[0]['quote']['amount']
    sell_price = buy_orders1[0]['price'] / 1.01
    log.debug('Selling {} @ {} from worker3 to worker1'.format(to_sell, sell_price))
    tx = market1.sell(sell_price, to_sell, account=worker3)
    log.debug(tx)

    # Make a trade on another worker which uses same account
    # The goal is to make a trade on different market BUT using same asset to
    # check if get_own_last_trade() will properly pick up a trade
    buy_orders2 = worker2.get_own_buy_orders()
    to_sell = buy_orders2[0]['quote']['amount']
    sell_price = buy_orders2[0]['price'] / 1.01
    log.debug('Selling {} @ {} from worker3 to worker2'.format(to_sell, sell_price))
    tx = market2.sell(sell_price, to_sell, account=worker3)
    log.debug(tx)

    # Wait some time to populate account history
    time.sleep(1.1)

    # Expect last trade data
    result = worker1.get_own_last_trade()
    assert result['base'] == pytest.approx(buy_orders1[0]['base']['amount'])
    assert result['quote'] == pytest.approx(buy_orders1[0]['quote']['amount'])
    assert result['price'] == pytest.approx(buy_orders1[0]['price'])


def test_get_own_last_trade_taker_buy(base_account, ro_worker, other_worker):
    """ Test for https://github.com/Codaone/DEXBot/issues/708
    """
    worker1 = ro_worker
    worker3 = base_account()
    market1 = Market(worker1.worker["market"])

    # Fill worker's order from different account
    # Note this order is significantly bigger by amount and lower by price than worker's order
    buy_orders1 = worker1.get_own_buy_orders()
    to_sell = buy_orders1[0]['quote']['amount'] * 1.5
    sell_price = buy_orders1[0]['price'] / 1.2
    log.debug('Selling {} @ {} from worker3 to worker1'.format(to_sell, sell_price))
    tx = market1.sell(sell_price, to_sell, account=worker3)
    log.debug(tx)

    # Bot uses last own trade price and acts as a taker
    worker1.is_center_price_dynamic = True
    worker1.cp_from_last_trade = True
    worker1['bootstrapped'] = True
    time.sleep(1.1)
    worker1.check_orders()

    # Expect correct last trade
    result = worker1.get_own_last_trade()
    assert result['price'] == pytest.approx(sell_price)


def test_get_own_last_trade_taker_sell(base_account, ro_worker, other_worker):
    """ Test for https://github.com/Codaone/DEXBot/issues/708
    """
    worker1 = ro_worker
    worker3 = base_account()
    market1 = Market(worker1.worker["market"])

    # Fill worker's order from different account
    # Note this order is significantly bigger by amount and lower by price than worker's order
    sell_orders1 = worker1.get_own_sell_orders()
    to_buy = sell_orders1[0]['base']['amount'] * 1.5
    buy_price = sell_orders1[0]['price'] * 1.2
    log.debug('Buying {} @ {} by worker3 from worker1'.format(to_buy, buy_price))
    tx = market1.buy(buy_price, to_buy, account=worker3)
    log.debug(tx)

    # Bot uses last own trade price and acts as a taker
    worker1.is_center_price_dynamic = True
    worker1.cp_from_last_trade = True
    worker1['bootstrapped'] = True
    time.sleep(1.1)
    worker1.check_orders()

    # Expect correct last trade
    result = worker1.get_own_last_trade()
    assert result['price'] == pytest.approx(buy_price, rel=(10 ** -worker1.market['base']['precision']))


def test_get_external_market_center_price(monkeypatch, ro_worker):
    """ Simply test if get_external_market_center_price does correct proxying to PriceFeed class
    """

    def mocked_cp(*args):
        return 1

    from dexbot.strategies.external_feeds.price_feed import PriceFeed

    monkeypatch.setattr(PriceFeed, 'get_center_price', mocked_cp)

    worker = ro_worker
    cp = worker.get_external_market_center_price('gecko')
    assert cp > 0


def test_mwsa_orders_cancel(base_worker, config_multiple_workers_1):
    """ Test two RO workers using same account, They should not touch each other orders
    """
    worker1 = base_worker(config_multiple_workers_1, worker_name='ro-worker-1')
    worker2 = base_worker(config_multiple_workers_1, worker_name='ro-worker-2')
    assert len(worker1.own_orders) == 2
    assert len(worker2.own_orders) == 2

    # Orders cancel on one worker should not cancel another worker orders
    worker2.cancel_all_orders()
    assert len(worker1.own_orders) == 2
