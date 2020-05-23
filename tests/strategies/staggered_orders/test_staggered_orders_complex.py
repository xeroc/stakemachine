import logging
import math
import time
from datetime import datetime

import pytest
from bitshares.amount import Amount

# Turn on debug for dexbot logger
log = logging.getLogger("dexbot")
log.setLevel(logging.DEBUG)

MODES = ['mountain', 'valley', 'neutral', 'buy_slope', 'sell_slope']


###################
# Most complex methods which depends on high-level methods
###################


def test_maintain_strategy_manual_cp_empty_market(worker):
    """On empty market, center price should be set to manual CP."""
    worker.cancel_all_orders()
    # Undefine market_center_price
    worker.market_center_price = None
    # Workaround for https://github.com/Codaone/DEXBot/issues/566
    worker.last_check = datetime(2000, 1, 1)
    worker.maintain_strategy()
    assert worker.market_center_price == worker.center_price


def test_maintain_strategy_no_manual_cp_empty_market(worker):
    """Strategy should not work on empty market if no manual CP was set."""
    worker.cancel_all_orders()
    # Undefine market_center_price
    worker.market_center_price = None
    worker.center_price = None
    # Workaround for https://github.com/Codaone/DEXBot/issues/566
    worker.last_check = datetime(2000, 1, 1)
    worker.maintain_strategy()
    assert worker.market_center_price is None


def test_maintain_strategy_no_operation_results(worker, monkeypatch):
    """https://github.com/Codaone/DEXBot/issues/764."""

    def mock(*args, **kwargs):
        return {'operation_results': None}

    monkeypatch.setattr(worker, 'retry_action', mock)
    worker.maintain_strategy()
    # Run twice!
    worker.maintain_strategy()


@pytest.mark.parametrize('mode', MODES)
def test_maintain_strategy_basic(mode, worker, do_initial_allocation):
    """Check if intial orders placement is correct."""
    worker = do_initial_allocation(worker, mode)

    # Check target spread is reached
    assert worker.get_actual_spread() == pytest.approx(worker.target_spread, abs=(worker.increment / 2))

    # Check number of orders
    price = worker.center_price * math.sqrt(1 + worker.target_spread)
    sell_orders_count = worker.calc_sell_orders_count(price, worker.upper_bound)
    assert len(worker.sell_orders) == sell_orders_count

    price = worker.center_price / math.sqrt(1 + worker.target_spread)
    buy_orders_count = worker.calc_buy_orders_count(price, worker.lower_bound)
    assert len(worker.buy_orders) == buy_orders_count

    # Make sure balances are allocated after full maintenance
    # Unallocated balances are less than closest order amount
    assert worker.base_balance['amount'] < worker.buy_orders[0]['base']['amount']
    assert worker.quote_balance['amount'] < worker.sell_orders[0]['base']['amount']

    # Test how ranges are covered
    # Expect furthest order price to be less than increment x2
    assert worker.buy_orders[-1]['price'] < worker.lower_bound * (1 + worker.increment * 2)
    assert worker.sell_orders[-1]['price'] ** -1 > worker.upper_bound / (1 + worker.increment * 2)


@pytest.mark.parametrize('mode', MODES)
def test_maintain_strategy_one_sided(mode, base_worker, config_only_base, do_initial_allocation):
    """Test for one-sided start (buy only)"""
    worker = base_worker(config_only_base)
    do_initial_allocation(worker, mode)

    # Check number of orders
    price = worker.center_price / math.sqrt(1 + worker.target_spread)
    buy_orders_count = worker.calc_buy_orders_count(price, worker.lower_bound)
    assert len(worker.buy_orders) == buy_orders_count

    # Make sure balances are allocated after full maintenance
    # Unallocated balances are less than closest order amount
    assert worker.base_balance['amount'] < worker.buy_orders[0]['base']['amount']

    # Test how ranges are covered
    # Expect furthest order price to be less than increment x2
    assert worker.buy_orders[-1]['price'] < worker.lower_bound * (1 + worker.increment * 2)


def test_maintain_strategy_1sat(base_worker, config_1_sat, do_initial_allocation):
    worker = base_worker(config_1_sat)
    do_initial_allocation(worker, worker.mode)

    # Check target spread is reached
    assert worker.get_actual_spread() == pytest.approx(worker.target_spread, abs=(worker.increment / 2))

    # Check number of orders
    price = worker.center_price * math.sqrt(1 + worker.target_spread)
    sell_orders_count = worker.calc_sell_orders_count(price, worker.upper_bound)
    assert len(worker.sell_orders) == sell_orders_count

    price = worker.center_price / math.sqrt(1 + worker.target_spread)
    buy_orders_count = worker.calc_buy_orders_count(price, worker.lower_bound)
    assert len(worker.buy_orders) == buy_orders_count

    # Make sure balances are allocated after full maintenance
    # Unallocated balances are less than closest order amount
    assert worker.base_balance['amount'] < worker.buy_orders[0]['base']['amount']
    assert worker.quote_balance['amount'] < worker.sell_orders[0]['base']['amount']

    # Test how ranges are covered
    # Expect furthest order price to be less than increment x2
    assert worker.buy_orders[-1]['price'] < worker.lower_bound * (1 + worker.increment * 2)
    assert worker.sell_orders[-1]['price'] ** -1 > worker.upper_bound / (1 + worker.increment * 2)


# Combine each mode with base and quote
@pytest.mark.parametrize('asset', ['base', 'quote'])
def test_maintain_strategy_fallback_logic(asset, worker, do_initial_allocation):
    """Check fallback logic: when spread is not reached, furthest order should be cancelled to make free funds to close
    spread."""
    do_initial_allocation(worker, worker.mode)
    # TODO: strategy must turn off bootstrapping once target spread is reached
    worker['bootstrapping'] = False

    if asset == 'base':
        worker.cancel_orders_wrapper(worker.buy_orders[0])
        amount = worker.balance(worker.market['base']['symbol'])
        worker.bitshares.reserve(amount, account=worker.account)
    elif asset == 'quote':
        worker.cancel_orders_wrapper(worker.sell_orders[0])
        amount = worker.balance(worker.market['quote']['symbol'])
        worker.bitshares.reserve(amount, account=worker.account)

    worker.refresh_orders()
    spread_before = worker.get_actual_spread()
    assert spread_before > worker.target_spread + worker.increment

    for _ in range(0, 6):
        worker.maintain_strategy()

    worker.refresh_orders()
    spread_after = worker.get_actual_spread()
    assert spread_after <= worker.target_spread + worker.increment


@pytest.mark.parametrize('asset', ['base', 'quote'])
def test_maintain_strategy_fallback_logic_disabled(asset, worker, do_initial_allocation):
    """Check fallback logic: when spread is not reached, furthest order should be cancelled to make free funds to close
    spread."""
    worker.enable_fallback_logic = False
    worker.operational_depth = 2
    do_initial_allocation(worker, 'valley')
    # TODO: strategy must turn off bootstrapping once target spread is reached
    worker['bootstrapping'] = False

    if asset == 'base':
        worker.cancel_orders_wrapper(worker.buy_orders[:3])
        amount = worker.buy_orders[0]['base'] * 3
        worker.bitshares.reserve(amount, account=worker.account)
    elif asset == 'quote':
        worker.cancel_orders_wrapper(worker.sell_orders[:3])
        amount = worker.sell_orders[0]['base'] * 3
        worker.bitshares.reserve(amount, account=worker.account)

    worker.refresh_orders()
    spread_before = worker.get_actual_spread()
    assert spread_before > worker.target_spread + worker.increment

    for _ in range(0, 6):
        worker.maintain_strategy()

    worker.refresh_orders()
    spread_after = worker.get_actual_spread()
    assert spread_after == spread_before

    # Also check that operational depth is proper
    assert len(worker.real_buy_orders) == pytest.approx(worker.operational_depth, abs=1)
    assert len(worker.real_sell_orders) == pytest.approx(worker.operational_depth, abs=1)


def test_check_operational_depth(worker, do_initial_allocation):
    """Test for correct operational depth following."""
    worker.operational_depth = 10
    do_initial_allocation(worker, worker.mode)
    worker['bootstrapping'] = False

    # abs=1 means we're accepting slight error

    assert len(worker.buy_orders) == pytest.approx(worker.operational_depth, abs=1)
    assert len(worker.sell_orders) == pytest.approx(worker.operational_depth, abs=1)

    worker.operational_depth = 2
    worker.refresh_orders()
    worker.check_operational_depth(worker.real_buy_orders, worker.virtual_buy_orders)
    worker.check_operational_depth(worker.real_sell_orders, worker.virtual_sell_orders)
    assert len(worker.real_buy_orders) == pytest.approx(worker.operational_depth, abs=1)
    assert len(worker.real_sell_orders) == pytest.approx(worker.operational_depth, abs=1)

    worker.operational_depth = 8
    worker.refresh_orders()
    worker.check_operational_depth(worker.real_buy_orders, worker.virtual_buy_orders)
    worker.check_operational_depth(worker.real_sell_orders, worker.virtual_sell_orders)
    assert len(worker.real_buy_orders) == pytest.approx(worker.operational_depth, abs=1)
    assert len(worker.real_sell_orders) == pytest.approx(worker.operational_depth, abs=1)


def test_increase_order_sizes_valley_basic(worker, do_initial_allocation, issue_asset, increase_until_allocated):
    """Test increases in valley mode when all orders are equal (new allocation round)."""
    do_initial_allocation(worker, 'valley')
    # Double worker's balance
    issue_asset(worker.market['base']['symbol'], worker.base_total_balance, worker.account.name)
    issue_asset(worker.market['quote']['symbol'], worker.quote_total_balance, worker.account.name)

    increase_until_allocated(worker)

    # All orders must be equal-sized
    for order in worker.buy_orders:
        assert order['base']['amount'] == worker.buy_orders[0]['base']['amount']
    for order in worker.sell_orders:
        assert order['base']['amount'] == worker.sell_orders[0]['base']['amount']


def test_increase_order_sizes_valley_direction(worker, do_initial_allocation, issue_asset, increase_until_allocated):
    """
    Test increase direction in valley mode: new allocation round must be started from closest order.

    Buy side, amounts in BASE:

    100 100 100 100 100
    100 100 100 100 115
    100 100 100 115 115
    100 100 115 115 115
    """
    do_initial_allocation(worker, 'valley')

    # Add balance to increase several orders; 1.01 to mitigate rounding issues
    increase_factor = max(1 + worker.increment, worker.min_increase_factor)
    to_issue = worker.buy_orders[0]['base']['amount'] * (increase_factor - 1) * 3 * 1.01
    issue_asset(worker.market['base']['symbol'], to_issue, worker.account.name)
    to_issue = worker.sell_orders[0]['base']['amount'] * (increase_factor - 1) * 3 * 1.01
    issue_asset(worker.market['quote']['symbol'], to_issue, worker.account.name)

    increase_until_allocated(worker)

    for order in worker.buy_orders:
        assert order['base']['amount'] <= worker.buy_orders[0]['base']['amount']
    for order in worker.sell_orders:
        assert order['base']['amount'] <= worker.sell_orders[0]['base']['amount']


def test_increase_order_sizes_valley_transit_from_mountain(worker, do_initial_allocation, issue_asset):
    """
    Transition from mountain to valley.

    Buy side, amounts in BASE, increase should be like this:

    70 80 90 100 <c>
    80 80 90 100 <c>
    80 90 90 100 <c>
    90 90 90 100 <c>
    """
    # Set up mountain
    do_initial_allocation(worker, 'mountain')
    # Switch to valley
    worker.mode = 'valley'

    for _ in range(0, 6):
        # Add balance to increase ~1 order
        to_issue = worker.buy_orders[0]['base']['amount']
        issue_asset(worker.market['base']['symbol'], to_issue, worker.account.name)
        previous_buy_orders = worker.buy_orders
        worker.refresh_balances()
        worker.increase_order_sizes('base', worker.base_balance, previous_buy_orders)
        worker.refresh_orders()

        for i in range(-1, -6, -1):
            if (
                previous_buy_orders[i]['base']['amount'] < previous_buy_orders[i - 1]['base']['amount']
                and previous_buy_orders[i - 1]['base']['amount'] - previous_buy_orders[i]['base']['amount']
                > previous_buy_orders[i]['base']['amount'] * worker.increment / 2
            ):
                # Expect increased order if closer order is bigger than further
                assert worker.buy_orders[i]['base']['amount'] > previous_buy_orders[i]['base']['amount']
                # Only one check at a time
                break


def test_increase_order_sizes_valley_smaller_closest_orders(worker, do_initial_allocation, increase_until_allocated):
    """
    Test increase when closest-to-center orders are less than further orders. Normal situation when initial sides are
    imbalanced and several orders were filled.

    Buy side, amounts in BASE:

    100 100 100 10 10 10 <center>
    """
    worker = do_initial_allocation(worker, 'valley')
    increase_until_allocated(worker)

    # Cancel several closest orders
    num_orders_to_cancel = 3
    num_orders_before = len(worker.own_orders)
    worker.cancel_orders_wrapper(worker.buy_orders[:num_orders_to_cancel])
    worker.cancel_orders_wrapper(worker.sell_orders[:num_orders_to_cancel])
    worker.refresh_orders()
    worker.refresh_balances()

    # Place limited orders
    initial_base = worker.buy_orders[0]['base']['amount']
    initial_quote = worker.sell_orders[0]['base']['amount']
    base_limit = initial_base / 2
    quote_limit = initial_quote / 2
    for _ in range(0, num_orders_to_cancel):
        worker.place_closer_order('base', worker.buy_orders[0], own_asset_limit=base_limit)
        worker.place_closer_order('quote', worker.sell_orders[0], own_asset_limit=quote_limit)
        worker.refresh_orders()

    increase_until_allocated(worker)

    # Number of orders should be the same
    num_orders_after = len(worker.own_orders)
    assert num_orders_before == num_orders_after

    # New orders amounts should be equal to initial ones
    # TODO: this relaxed test checks next closest orders because due to fp calculations closest orders may remain not
    # increased
    assert worker.buy_orders[1]['base']['amount'] == initial_base
    assert worker.sell_orders[1]['base']['amount'] == initial_quote


def test_increase_order_sizes_valley_imbalaced_small_further(worker, do_initial_allocation, increase_until_allocated):
    """
    If furthest orders are smaller than closest, they should be increased first. See
    https://github.com/Codaone/DEXBot/issues/444 for details.

    Buy side, amounts in BASE:

    5 5 5 100 100 10 10 10 <center>

    Should be:

    10 10 10 100 100 10 10 10 <center>
    """
    worker = do_initial_allocation(worker, 'valley')

    # Cancel several closest orders
    num_orders_to_cancel = 3
    worker.cancel_orders_wrapper(worker.buy_orders[:num_orders_to_cancel])
    # Cancel furthest orders
    worker.cancel_orders_wrapper(worker.buy_orders[-num_orders_to_cancel:])
    worker.refresh_orders()
    worker.refresh_balances()

    # Place limited orders
    initial_base = worker.buy_orders[0]['base']['amount']
    base_limit = initial_base / 2
    for i in range(0, num_orders_to_cancel):
        # Place smaller closer order
        worker.place_closer_order('base', worker.buy_orders[0], own_asset_limit=base_limit)
        # place_further_order() doesn't have own_asset_limit, so do own calculation
        further_order = worker.place_further_order('base', worker.buy_orders[-1], place_order=False)
        # Place smaller further order
        to_buy = base_limit / further_order['price']
        worker.place_market_buy_order(to_buy, further_order['price'])
        worker.refresh_orders()

    # Drop excess balance to only allow one increase round
    worker.refresh_balances()
    increase_factor = max(1 + worker.increment, worker.min_increase_factor)
    to_keep = base_limit * (increase_factor - 1) * num_orders_to_cancel * 2 * 1.01
    to_drop = worker.base_balance['amount'] - to_keep
    amount = Amount(to_drop, worker.market['base']['symbol'], bitshares_instance=worker.bitshares)
    worker.bitshares.reserve(amount, account=worker.account)

    increase_until_allocated(worker)

    for i in range(1, num_orders_to_cancel):
        further_order_amount = worker.buy_orders[-i]['base']['amount']
        closer_order_amount = worker.buy_orders[i - 1]['base']['amount']
        assert further_order_amount == closer_order_amount


def test_increase_order_sizes_valley_closest_order(worker, do_initial_allocation, issue_asset):
    """Should test proper calculation of closest order: order should not be less that min_increase_factor."""
    worker = do_initial_allocation(worker, 'valley')

    # Add balance to increase 2 orders
    increase_factor = max(1 + worker.increment, worker.min_increase_factor)
    to_issue = worker.buy_orders[0]['base']['amount'] * (increase_factor - 1) * 2
    issue_asset(worker.market['base']['symbol'], to_issue, worker.account.name)

    previous_buy_orders = worker.buy_orders
    worker.refresh_balances()
    worker.increase_order_sizes('base', worker.base_balance, previous_buy_orders)
    worker.refresh_orders()

    assert worker.buy_orders[0]['base']['amount'] - previous_buy_orders[0]['base']['amount'] == pytest.approx(
        previous_buy_orders[0]['base']['amount'] * (increase_factor - 1)
    )


def test_increase_order_sizes_mountain_basic(worker, do_initial_allocation, issue_asset, increase_until_allocated):
    """
    Test increases in mountain mode when all orders are equal (new allocation round).

    New orders should be equal in their "quote"
    """
    do_initial_allocation(worker, 'mountain')
    increase_until_allocated(worker)

    # Double worker's balance
    issue_asset(worker.market['base']['symbol'], worker.base_total_balance, worker.account.name)
    issue_asset(worker.market['quote']['symbol'], worker.quote_total_balance, worker.account.name)

    increase_until_allocated(worker)

    # All orders must be equal-sized in their quote, accept difference no more than increase_factor.
    # This means all orders was increased and probably unfinished increase round may remain.
    increase_factor = max(1 + worker.increment, worker.min_increase_factor)
    for order in worker.buy_orders:
        assert order['quote']['amount'] == pytest.approx(worker.buy_orders[0]['quote']['amount'], rel=(increase_factor))
    for order in worker.sell_orders:
        assert order['quote']['amount'] == pytest.approx(
            worker.sell_orders[0]['quote']['amount'], rel=(increase_factor)
        )


def test_increase_order_sizes_mountain_direction(worker, do_initial_allocation, issue_asset, increase_until_allocated):
    """
    Test increase direction in mountain mode.

    Buy side, amounts in QUOTE:

    10 10 10 10 10
    15 10 10 10 10
    15 15 10 10 10
    15 15 15 10 10
    """
    do_initial_allocation(worker, 'mountain')
    increase_until_allocated(worker)
    worker.mode = 'mountain'
    increase_factor = max(1 + worker.increment, worker.min_increase_factor)

    for i in range(-1, -6, -1):
        # Add balance to increase ~1 order
        to_issue = worker.buy_orders[i]['base']['amount'] * (increase_factor - 1)
        issue_asset(worker.market['base']['symbol'], to_issue, worker.account.name)
        previous_buy_orders = worker.buy_orders
        worker.refresh_balances()
        worker.increase_order_sizes('base', worker.base_balance, previous_buy_orders)
        worker.refresh_orders()

        for i in range(-1, -6, -1):
            if (
                previous_buy_orders[i]['quote']['amount'] > previous_buy_orders[i - 1]['quote']['amount']
                and previous_buy_orders[i]['quote']['amount'] - previous_buy_orders[i - 1]['quote']['amount']
                > previous_buy_orders[i - 1]['quote']['amount'] * worker.increment / 2
            ):
                # Expect increased order if further order is bigger than closer
                assert worker.buy_orders[i - 1]['quote']['amount'] > previous_buy_orders[i - 1]['quote']['amount']
                # Only one check at a time
                break


def test_increase_order_sizes_mountain_furthest_order(
    worker, do_initial_allocation, increase_until_allocated, issue_asset
):
    """Should test proper calculation of furthest order: try to maximize, don't allow too small increase."""
    do_initial_allocation(worker, 'mountain')
    previous_buy_orders = worker.buy_orders

    # Add balance to increase ~1 order
    increase_factor = max(1 + worker.increment, worker.min_increase_factor)
    to_issue = worker.buy_orders[-1]['base']['amount'] * (increase_factor - 1) * 1.1
    issue_asset(worker.market['base']['symbol'], to_issue, worker.account.name)

    worker.refresh_balances()
    increase_until_allocated(worker)
    worker.refresh_orders()

    assert worker.buy_orders[-1]['base']['amount'] - previous_buy_orders[-1]['base']['amount'] == pytest.approx(
        previous_buy_orders[-1]['base']['amount'] * (increase_factor - 1),
        rel=(10 ** -worker.market['base']['precision']),
    )


def test_increase_order_sizes_mountain_imbalanced(worker, do_initial_allocation):
    """
    Test situation when sides was imbalances, several orders filled on opposite side. This also tests transition from
    vally to mountain.

    Buy side, amounts in QUOTE:

    100 100 100 10 10 10 <c>
    100 100 100 20 10 10 <c>
    100 100 100 20 20 10 <c>
    """
    do_initial_allocation(worker, 'mountain')
    worker.mode = 'mountain'

    # Cancel several closest orders
    num_orders_to_cancel = 3
    worker.cancel_orders_wrapper(worker.buy_orders[:num_orders_to_cancel])
    worker.refresh_orders()
    worker.refresh_balances()

    # Place limited orders
    initial_base = worker.buy_orders[0]['base']['amount']
    base_limit = initial_base / 2
    # Add own_asset_limit only for first new order
    worker.place_closer_order('base', worker.buy_orders[0], own_asset_limit=base_limit)
    worker.refresh_orders()
    for _ in range(1, num_orders_to_cancel):
        worker.place_closer_order('base', worker.buy_orders[0])
        worker.refresh_orders()

    previous_buy_orders = worker.buy_orders

    for _ in range(0, num_orders_to_cancel):
        worker.refresh_balances()
        worker.increase_order_sizes('base', worker.base_balance, worker.buy_orders)
        worker.refresh_orders()

    for order_index in range(0, num_orders_to_cancel):
        order = worker.buy_orders[order_index]
        if (
            previous_buy_orders[order_index]['quote']['amount']
            < previous_buy_orders[order_index + 1]['quote']['amount']
            and previous_buy_orders[order_index + 1]['base']['amount']
            - previous_buy_orders[order_index]['base']['amount']
            > previous_buy_orders[order_index]['base']['amount'] * worker.increment / 2
        ):
            # If order before increase was smaller than further order, expect to see it increased
            assert order['quote']['amount'] > previous_buy_orders[order_index]['quote']['amount']
            break


def test_increase_order_sizes_neutral_basic(worker, do_initial_allocation, issue_asset, increase_until_allocated):
    """Test increases in neutral mode when all orders are equal (new allocation round)"""
    do_initial_allocation(worker, 'neutral')
    increase_until_allocated(worker)

    # Double worker's balance
    issue_asset(worker.market['base']['symbol'], worker.base_total_balance, worker.account.name)
    issue_asset(worker.market['quote']['symbol'], worker.quote_total_balance, worker.account.name)

    increase_until_allocated(worker)
    increase_factor = max(1 + worker.increment, worker.min_increase_factor)

    for index, order in enumerate(worker.buy_orders):
        if index == 0:
            continue
        # Assume amounts are equal within some tolerance, or accept difference at increase_factor size to detect new
        # unfinished increase round
        assert (
            order['base']['amount']
            == pytest.approx(
                worker.buy_orders[index - 1]['base']['amount'] / math.sqrt(1 + worker.increment),
                rel=(10 ** -worker.market['base']['precision']),
            )
        ) or (
            order['base']['amount']
            == pytest.approx(
                worker.buy_orders[index - 1]['base']['amount'] / math.sqrt(1 + worker.increment) / increase_factor,
                rel=(10 ** -worker.market['base']['precision']),
            )
        )
    for index, order in enumerate(worker.sell_orders):
        if index == 0:
            continue
        assert (
            order['base']['amount']
            == pytest.approx(
                worker.sell_orders[index - 1]['base']['amount'] / math.sqrt(1 + worker.increment),
                rel=(10 ** -worker.market['quote']['precision']),
            )
        ) or (
            order['base']['amount']
            == pytest.approx(
                worker.sell_orders[index - 1]['base']['amount'] / math.sqrt(1 + worker.increment) / increase_factor,
                rel=(10 ** -worker.market['quote']['precision']),
            )
        )


def test_increase_order_sizes_neutral_direction(worker, do_initial_allocation, issue_asset, increase_until_allocated):
    """
    Test increase direction in neutral mode: new allocation round must be started from closest order.

    Buy side, amounts in BASE:

    100 100 100 100 100
    100 100 100 100 115
    100 100 100 114 115
    100 100 113 114 115
    """
    do_initial_allocation(worker, 'neutral')

    # Add balance to increase several orders
    increase_factor = max(1 + worker.increment, worker.min_increase_factor)
    to_issue = worker.buy_orders[0]['base']['amount'] * (increase_factor - 1) * 3
    issue_asset(worker.market['base']['symbol'], to_issue, worker.account.name)
    to_issue = worker.sell_orders[0]['base']['amount'] * (increase_factor - 1) * 3
    issue_asset(worker.market['quote']['symbol'], to_issue, worker.account.name)

    increase_until_allocated(worker)

    for order in worker.buy_orders:
        assert order['base']['amount'] <= worker.buy_orders[0]['base']['amount']
    for order in worker.sell_orders:
        assert order['base']['amount'] <= worker.sell_orders[0]['base']['amount']


def test_increase_order_sizes_neutral_transit_from_mountain(worker, do_initial_allocation, issue_asset):
    """
    Transition from mountain to neutral.

    Buy side, amounts in BASE, increase should be like this:

    70 80 90 100 <c>
    80 80 90 100 <c>
    80 90 90 100 <c>
    90 90 90 100 <c>
    """
    # Set up mountain
    do_initial_allocation(worker, 'mountain')
    # Switch to neutral
    worker.mode = 'neutral'
    # Add balance to increase several orders
    to_issue = worker.buy_orders[0]['base']['amount'] * 10
    issue_asset(worker.market['base']['symbol'], to_issue, worker.account.name)

    for _ in range(0, 6):
        previous_buy_orders = worker.buy_orders
        worker.refresh_balances()
        worker.increase_order_sizes('base', worker.base_balance, previous_buy_orders)
        worker.refresh_orders()

        for i in range(-1, -6, -1):
            if (
                previous_buy_orders[i]['base']['amount'] < previous_buy_orders[i - 1]['base']['amount']
                and previous_buy_orders[i - 1]['base']['amount'] - previous_buy_orders[i]['base']['amount']
                > previous_buy_orders[i]['base']['amount'] * worker.increment / 2
            ):
                # Expect increased order if closer order is bigger than further
                assert worker.buy_orders[i]['base']['amount'] > previous_buy_orders[i]['base']['amount']
                # Only one check at a time
                break


def test_increase_order_sizes_neutral_smaller_closest_orders(worker, do_initial_allocation, increase_until_allocated):
    """
    Test increase when closest-to-center orders are less than further orders. Normal situation when initial sides are
    imbalanced and several orders were filled.

    Buy side, amounts in BASE:

    100 100 100 10 10 10 <center>
    """
    worker = do_initial_allocation(worker, 'neutral')
    increase_until_allocated(worker)

    initial_base = worker.buy_orders[0]['base']['amount']
    initial_quote = worker.sell_orders[0]['base']['amount']

    # Cancel several closest orders
    num_orders_to_cancel = 3
    worker.cancel_orders_wrapper(worker.buy_orders[:num_orders_to_cancel])
    worker.cancel_orders_wrapper(worker.sell_orders[:num_orders_to_cancel])
    worker.refresh_orders()
    worker.refresh_balances()

    # Place limited orders
    base_limit = initial_base / 2
    quote_limit = initial_quote / 2
    worker.place_closer_order('base', worker.buy_orders[0], own_asset_limit=base_limit)
    worker.place_closer_order('quote', worker.sell_orders[0], own_asset_limit=quote_limit)
    worker.refresh_orders()
    for _ in range(1, num_orders_to_cancel):
        worker.place_closer_order('base', worker.buy_orders[0])
        worker.place_closer_order('quote', worker.sell_orders[0])
        worker.refresh_orders()

    increase_until_allocated(worker)
    increase_factor = max(1 + worker.increment, worker.min_increase_factor)

    # New closest orders amount should be equal to initial ones
    assert worker.buy_orders[0]['base']['amount'] == pytest.approx(
        initial_base, rel=(0.1 * increase_factor * initial_base)
    )
    assert worker.sell_orders[0]['base']['amount'] == pytest.approx(
        initial_quote, rel=(0.1 * increase_factor * initial_quote)
    )


def test_increase_order_sizes_neutral_imbalaced_small_further(worker, do_initial_allocation, increase_until_allocated):
    """
    If furthest orders are smaller than closest, they should be increased first. See
    https://github.com/Codaone/DEXBot/issues/444 for details.

    Buy side, amounts in BASE:

    5 5 5 100 100 10 10 10 <center>

    Should be:

    10 10 10 100 100 10 10 10 <center>
    """
    worker = do_initial_allocation(worker, 'neutral')

    # Cancel several closest orders
    num_orders_to_cancel = 3
    worker.cancel_orders_wrapper(worker.buy_orders[:num_orders_to_cancel])
    # Cancel furthest orders
    worker.cancel_orders_wrapper(worker.buy_orders[-num_orders_to_cancel:])
    worker.refresh_orders()
    worker.refresh_balances()

    # Place limited orders
    initial_base = worker.buy_orders[0]['base']['amount']
    base_limit = initial_base / 2
    # Apply limit only for first order
    worker.place_closer_order('base', worker.buy_orders[0], own_asset_limit=base_limit)
    # place_further_order() doesn't have own_asset_limit, so do own calculation
    further_order = worker.place_further_order('base', worker.buy_orders[-1], place_order=False)
    worker.place_market_buy_order(base_limit / further_order['price'], further_order['price'])
    worker.refresh_orders()

    # Place remaining limited orders
    for i in range(1, num_orders_to_cancel):
        worker.place_closer_order('base', worker.buy_orders[0])
        worker.place_further_order('base', worker.buy_orders[-1])
        worker.refresh_orders()

    # Drop excess balance to only allow one increase round
    worker.refresh_balances()
    increase_factor = max(1 + worker.increment, worker.min_increase_factor)
    to_keep = base_limit * (increase_factor - 1) * num_orders_to_cancel * 2
    to_drop = worker.base_balance['amount'] - to_keep
    amount = Amount(to_drop, worker.market['base']['symbol'], bitshares_instance=worker.bitshares)
    worker.bitshares.reserve(amount, account=worker.account)

    increase_until_allocated(worker)

    for i in range(1, num_orders_to_cancel):
        # This is a simple check without precise calculation
        # We're roughly checking that new furthest orders are not exceeds new closest orders
        further_order_amount = worker.buy_orders[-i]['base']['amount']
        closer_order_amount = worker.buy_orders[i - 1]['base']['amount']
        assert further_order_amount < closer_order_amount


def test_increase_order_sizes_neutral_closest_order(
    worker, do_initial_allocation, increase_until_allocated, issue_asset
):
    """Should test proper calculation of closest order: order should not be less that min_increase_factor."""
    worker = do_initial_allocation(worker, 'neutral')
    increase_until_allocated(worker)

    # Add balance to increase 2 orders
    increase_factor = max(1 + worker.increment, worker.min_increase_factor)
    to_issue = worker.buy_orders[0]['base']['amount'] * (increase_factor - 1) * 2
    issue_asset(worker.market['base']['symbol'], to_issue, worker.account.name)

    previous_buy_orders = worker.buy_orders
    worker.refresh_balances()
    worker.increase_order_sizes('base', worker.base_balance, previous_buy_orders)
    worker.refresh_orders()

    assert worker.buy_orders[0]['base']['amount'] - previous_buy_orders[0]['base']['amount'] == pytest.approx(
        previous_buy_orders[0]['base']['amount'] * (increase_factor - 1),
        rel=(10 ** -worker.market['base']['precision']),
    )


def test_increase_order_sizes_buy_slope(worker, do_initial_allocation, issue_asset, increase_until_allocated):
    """Check correct orders sizes on both sides."""
    do_initial_allocation(worker, 'buy_slope')

    # Double worker's balance
    issue_asset(worker.market['base']['symbol'], worker.base_total_balance, worker.account.name)
    issue_asset(worker.market['quote']['symbol'], worker.quote_total_balance, worker.account.name)

    increase_until_allocated(worker)
    increase_factor = max(1 + worker.increment, worker.min_increase_factor)

    for order in worker.buy_orders:
        # All buy orders must be equal-sized in BASE
        assert order['base']['amount'] == worker.buy_orders[0]['base']['amount']
    for index, order in enumerate(worker.sell_orders):
        # Sell orders are equal-sized in BASE asset or diff is equal to increase_factor
        if index == 0:
            continue
        assert (
            order['quote']['amount']
            == pytest.approx(
                worker.sell_orders[index - 1]['quote']['amount'], rel=(10 ** -worker.market['base']['precision'])
            )
        ) or (
            order['quote']['amount']
            == pytest.approx(
                worker.sell_orders[index - 1]['quote']['amount'] * increase_factor,
                rel=(0.1 * increase_factor * order['quote']['amount']),
            )
        )


def test_increase_order_sizes_sell_slope(worker, do_initial_allocation, issue_asset, increase_until_allocated):
    """Check correct orders sizes on both sides."""
    do_initial_allocation(worker, 'sell_slope')

    # Double worker's balance
    issue_asset(worker.market['base']['symbol'], worker.base_total_balance, worker.account.name)
    issue_asset(worker.market['quote']['symbol'], worker.quote_total_balance, worker.account.name)

    increase_until_allocated(worker)
    increase_factor = max(1 + worker.increment, worker.min_increase_factor)

    for index, order in enumerate(worker.buy_orders):
        # All buy orders must be equal-sized in market QUOTE or diff is equal to increase_factor
        if index == 0:
            continue
        assert (
            order['quote']['amount']
            == pytest.approx(
                worker.buy_orders[index - 1]['quote']['amount'], rel=(10 ** -worker.market['quote']['precision'])
            )
        ) or (
            order['quote']['amount']
            == pytest.approx(
                worker.buy_orders[index - 1]['quote']['amount'] * increase_factor,
                rel=(0.1 * increase_factor * order['quote']['amount']),
            )
        )

    for order in worker.sell_orders:
        # All sell orders must be equal-sized in market QUOTE
        assert order['base']['amount'] == worker.sell_orders[0]['base']['amount']


# Note: no other tests for slope modes because they are combined modes. If valley and mountain are ok, so slopes too


def test_allocate_asset_basic(worker):
    """Check that free balance is shrinking after each allocation and spread is decreasing."""

    worker.refresh_balances()
    spread_after = worker.get_actual_spread()

    # Allocate asset until target spread will be reached
    while spread_after >= worker.target_spread + worker.increment:
        free_base = worker.base_balance
        free_quote = worker.quote_balance
        spread_before = worker.get_actual_spread()

        worker.allocate_asset('base', free_base)
        worker.allocate_asset('quote', free_quote)
        worker.refresh_orders()
        worker.refresh_balances(use_cached_orders=True)
        spread_after = worker.get_actual_spread()

        # Update whistory of balance changes
        worker.base_balance_history.append(worker.base_balance['amount'])
        worker.quote_balance_history.append(worker.quote_balance['amount'])
        if len(worker.base_balance_history) > 3:
            del worker.base_balance_history[0]
            del worker.quote_balance_history[0]

        # Free balance is shrinking after each allocation
        assert worker.base_balance < free_base or worker.quote_balance < free_quote

        # Actual spread is decreasing
        assert spread_after < spread_before


def test_allocate_asset_replace_closest_partial_order(worker, other_worker, do_initial_allocation, issue_asset):
    """Test that partially filled order is replaced when target spread is not reached, before placing closer order."""
    do_initial_allocation(worker, worker.mode)

    # Sell some quote from another account to make PF order on buy side
    price = worker.buy_orders[0]['price'] / 1.01
    amount = worker.buy_orders[0]['quote']['amount'] * (1 - worker.partial_fill_threshold * 1.1)
    other_worker.place_market_sell_order(amount, price)

    # Fill sell order
    price = worker.sell_orders[0]['price'] ** -1 * 1.01
    amount = worker.sell_orders[0]['base']['amount']
    other_worker.place_market_buy_order(amount, price)

    # Expect replaced closest buy order
    worker.refresh_orders()
    worker.refresh_balances(use_cached_orders=True)
    worker.allocate_asset('base', worker.base_balance)
    worker.refresh_orders()
    assert worker.buy_orders[0]['base']['amount'] == worker.buy_orders[0]['for_sale']['amount']


def test_allocate_asset_replace_partially_filled_orders(
    worker, other_worker, do_initial_allocation, issue_asset, maintain_until_allocated
):
    """
    Check replacement of partially filled orders on both sides.

    Simple check.
    """
    do_initial_allocation(worker, worker.mode)
    # TODO: automatically turn off bootstrapping after target spread is closed?
    worker['bootstrapping'] = False

    # Partially fill closest orders
    price = worker.buy_orders[0]['price']
    amount = worker.buy_orders[0]['quote']['amount'] / 2
    log.debug('Filling {} @ {}'.format(amount, price))
    other_worker.place_market_sell_order(amount, price)

    price = worker.sell_orders[0]['price'] ** -1
    amount = worker.sell_orders[0]['base']['amount'] / 2
    log.debug('Filling {} @ {}'.format(amount, price))
    other_worker.place_market_buy_order(amount, price)

    # Add some balance to worker
    to_issue = worker.buy_orders[0]['base']['amount']
    issue_asset(worker.market['base']['symbol'], to_issue, worker.account.name)
    to_issue = worker.sell_orders[0]['base']['amount']
    issue_asset(worker.market['quote']['symbol'], to_issue, worker.account.name)

    maintain_until_allocated(worker)
    worker.refresh_orders()
    assert worker.buy_orders[0]['base']['amount'] == worker.buy_orders[0]['for_sale']['amount']
    assert worker.sell_orders[0]['base']['amount'] == worker.sell_orders[0]['for_sale']['amount']


def test_allocate_asset_increase_orders(worker, do_initial_allocation, maintain_until_allocated, issue_asset):
    """Add balance, expect increased orders."""
    do_initial_allocation(worker, worker.mode)
    order_ids = [order['id'] for order in worker.own_orders]
    balance_in_orders_before = worker.get_allocated_assets(order_ids)
    to_issue = worker.buy_orders[0]['base']['amount'] * 3
    issue_asset(worker.market['base']['symbol'], to_issue, worker.account.name)
    to_issue = worker.sell_orders[0]['base']['amount'] * 3
    issue_asset(worker.market['quote']['symbol'], to_issue, worker.account.name)
    # Use maintain_strategy() here for simplicity
    maintain_until_allocated(worker)
    order_ids = [order['id'] for order in worker.own_orders]
    balance_in_orders_after = worker.get_allocated_assets(order_ids)
    assert balance_in_orders_after['base'] > balance_in_orders_before['base']
    assert balance_in_orders_after['quote'] > balance_in_orders_before['quote']


def test_allocate_asset_dust_order_simple(
    worker, other_worker, do_initial_allocation, maintain_until_allocated, base_account
):
    """Make dust order, check if it canceled and closer opposite order placed."""
    do_initial_allocation(worker, worker.mode)
    num_sell_orders_before = len(worker.sell_orders)
    num_buy_orders_before = len(worker.buy_orders)

    # Partially fill order from another account
    sell_price = worker.buy_orders[0]['price'] / 1.01
    sell_amount = worker.buy_orders[0]['quote']['amount'] * (1 - worker.partial_fill_threshold) * 1.1
    other_worker.place_market_sell_order(sell_amount, sell_price)

    worker.refresh_balances()
    worker.refresh_orders()
    worker.allocate_asset('quote', worker.quote_balance)
    worker.refresh_orders()
    num_sell_orders_after = len(worker.sell_orders)
    num_buy_orders_after = len(worker.buy_orders)

    assert num_buy_orders_before - num_buy_orders_after == 1
    assert num_sell_orders_after - num_sell_orders_before == 1


def test_allocate_asset_dust_order_excess_funds(
    worker, other_worker, do_initial_allocation, maintain_until_allocated, issue_asset
):
    """Make dust order, add additional funds, these funds should be allocated and then dust order should be canceled and
    closer opposite order placed."""
    do_initial_allocation(worker, worker.mode)
    num_sell_orders_before = len(worker.sell_orders)
    num_buy_orders_before = len(worker.buy_orders)

    # Partially fill order from another account
    sell_price = worker.buy_orders[0]['price'] / 1.01
    sell_amount = worker.buy_orders[0]['quote']['amount'] * (1 - worker.partial_fill_threshold) * 1.1
    other_worker.place_market_sell_order(sell_amount, sell_price)

    # Add some balance to the worker
    issue_asset(worker.market['quote']['symbol'], worker.sell_orders[0]['base']['amount'], worker.account.name)

    worker.refresh_balances()
    worker.refresh_orders()
    worker.allocate_asset('quote', worker.quote_balance)
    worker.refresh_orders()
    num_sell_orders_after = len(worker.sell_orders)
    num_buy_orders_after = len(worker.buy_orders)

    assert num_buy_orders_before - num_buy_orders_after == 1
    assert num_sell_orders_after - num_sell_orders_before == 1


def test_allocate_asset_dust_order_increase_race(worker, other_worker, do_initial_allocation, issue_asset):
    """
    Test for https://github.com/Codaone/DEXBot/issues/587.

    Check if cancelling dust orders on opposite side will not cause a race for allocate_asset() on opposite side
    """
    do_initial_allocation(worker, worker.mode)
    num_buy_orders_before = len(worker.buy_orders)

    # Make closest sell order small enough to be a most likely candidate for increase
    worker.cancel_orders_wrapper(worker.sell_orders[0])
    worker.refresh_orders()
    worker.refresh_balances()
    worker.place_closer_order(
        'quote', worker.sell_orders[0], own_asset_limit=(worker.sell_orders[0]['base']['amount'] / 2)
    )
    worker.refresh_orders()

    # Partially fill order from another account
    buy_price = worker.sell_orders[0]['price'] ** -1 * 1.01
    buy_amount = worker.sell_orders[0]['base']['amount'] * (1 - worker.partial_fill_threshold) * 1.1
    log.debug('{}, {}'.format(buy_price, buy_amount))
    other_worker.place_market_buy_order(buy_amount, buy_price)

    # PF fill sell order should be cancelled and closer buy placed
    worker.maintain_strategy()
    worker.refresh_orders()
    num_buy_orders_after = len(worker.buy_orders)
    assert num_buy_orders_after - num_buy_orders_before == 1


def test_allocate_asset_filled_orders(worker, other_worker, do_initial_allocation, base_account):
    """Fill an order and check if opposite order placed."""
    do_initial_allocation(worker, worker.mode)
    # TODO: automatically turn off bootstrapping after target spread is closed?
    worker['bootstrapping'] = False
    num_sell_orders_before = len(worker.sell_orders)

    # Fill sell order
    price = worker.buy_orders[0]['price']
    amount = worker.buy_orders[0]['quote']['amount']
    other_worker.place_market_sell_order(amount, price)
    worker.refresh_balances()
    worker.refresh_orders()
    worker.allocate_asset('quote', worker.quote_balance)
    worker.refresh_orders()
    num_sell_orders_after = len(worker.sell_orders)
    assert num_sell_orders_after - num_sell_orders_before == 1


def test_allocate_asset_filled_order_on_massively_imbalanced_sides(
    worker, other_worker, do_initial_allocation, base_account
):
    """
    When sides are massively imbalanced, make sure that spread will be closed after filling one order on smaller side.
    The goal is to test a situation when one side has a big-sized orders, and other side has much smaller orders.
    Correct behavior: when order on smaller side filled, big side should place closer order.

    Test for https://github.com/Codaone/DEXBot/issues/588
    """
    do_initial_allocation(worker, worker.mode)
    spread_before = worker.get_actual_spread()
    log.info('Worker spread after bootstrap: {}'.format(spread_before))
    # TODO: automatically turn off bootstrapping after target spread is closed?
    worker['bootstrapping'] = False

    # Cancel several closest orders
    num_orders_to_cancel = 3
    worker.cancel_orders_wrapper(worker.sell_orders[:num_orders_to_cancel])
    worker.refresh_orders()
    worker.refresh_balances()

    # Place limited orders; the goal is to limit order amount to be much smaller than opposite
    quote_limit = worker.buy_orders[0]['quote']['amount'] * worker.partial_fill_threshold / 2
    spread_after = worker.get_actual_spread()
    while spread_after >= worker.target_spread + worker.increment:
        # We're using spread check because we cannot just place same number of orders as num_orders_to_cancel because
        # it may result in too close spread because of price shifts
        worker.place_closer_order('quote', worker.sell_orders[0], own_asset_limit=quote_limit)
        worker.refresh_orders()
        spread_after = worker.get_actual_spread()

    log.info('Worker spread: {}'.format(worker.get_actual_spread()))

    # Fill only one newly placed order from another account
    num_orders_to_fill = 1
    for i in range(0, num_orders_to_fill):
        price = worker.sell_orders[i]['price'] ** -1 * 1.01
        amount = worker.sell_orders[i]['base']['amount'] * 1.01
        log.debug('Filling {} @ {}'.format(amount, price))
        other_worker.place_market_buy_order(amount, price)

    # Cancel unmatched dust
    other_worker.cancel_all_orders()
    worker.refresh_orders()
    worker.refresh_balances(use_cached_orders=True)

    # Filling of one order should result in spread > target spread, othewise allocate_asset will not place closer prder
    spread_after = worker.get_actual_spread()
    assert spread_after >= worker.target_spread + worker.increment

    # Allocate obtained BASE
    counter = 0
    while spread_after >= worker.target_spread + worker.increment:
        worker.allocate_asset('base', worker.base_balance)
        worker.refresh_orders()
        worker.refresh_balances(use_cached_orders=True)
        spread_after = worker.get_actual_spread()
        counter += 1
        # Counter is for preventing infinity loop
        assert counter < 20


def test_allocate_asset_partially_filled_order_on_massively_imbalanced_sides(
    worker, other_worker, do_initial_allocation, base_account
):
    """
    When sides are massively imbalanced, make sure that spread will be closed after filling one order on smaller side.
    The goal is to test a situation when one side has a big-sized orders, and other side has much smaller orders.
    Correct behavior: when order on smaller side filled, big side should place closer order.

    This test is similar to test_allocate_asset_filled_order_on_massively_imbalanced_sides, but tests partially
    filled order where "calncel dust order" logic is in action.

    Test for https://github.com/Codaone/DEXBot/issues/588
    """
    do_initial_allocation(worker, worker.mode)
    spread_before = worker.get_actual_spread()
    log.info('Worker spread after bootstrap: {}'.format(spread_before))
    # TODO: automatically turn off bootstrapping after target spread is closed?
    worker['bootstrapping'] = False

    # Cancel several closest orders
    num_orders_to_cancel = 3
    worker.cancel_orders_wrapper(worker.sell_orders[:num_orders_to_cancel])
    worker.refresh_orders()
    worker.refresh_balances()

    # Place limited orders; the goal is to limit order amount to be much smaller than opposite
    quote_limit = worker.buy_orders[0]['quote']['amount'] * worker.partial_fill_threshold / 2
    spread_after = worker.get_actual_spread()
    while spread_after >= worker.target_spread + worker.increment:
        # We're using spread check because we cannot just place same number of orders as num_orders_to_cancel because
        # it may result in too close spread because of price shifts
        worker.place_closer_order('quote', worker.sell_orders[0], own_asset_limit=quote_limit)
        worker.refresh_orders()
        spread_after = worker.get_actual_spread()

    log.info('Worker spread: {}'.format(worker.get_actual_spread()))

    # Fill only one newly placed order from another account
    num_orders_to_fill = 1
    for i in range(0, num_orders_to_fill):
        price = worker.sell_orders[i]['price'] ** -1 * 1.01
        # Make partially filled order (dust order)
        amount = worker.sell_orders[i]['base']['amount'] * (1 - worker.partial_fill_threshold) * 1.01
        log.debug('Filling {} @ {}'.format(amount, price))
        other_worker.place_market_buy_order(amount, price)

    # Cancel unmatched dust
    other_worker.cancel_all_orders()
    worker.refresh_orders()
    worker.refresh_balances(use_cached_orders=True)

    # Check that we filled enough
    assert not worker.check_partial_fill(worker.sell_orders[0], fill_threshold=(1 - worker.partial_fill_threshold))

    # Expect dust order cancel + closer order
    log.info('spread before allocate_asset(): {}'.format(worker.get_actual_spread()))
    worker.allocate_asset('base', worker.base_balance)
    worker.refresh_orders()
    spread_after = worker.get_actual_spread()
    assert spread_after < worker.target_spread + worker.increment


@pytest.mark.parametrize('mode', MODES)
def test_allocate_asset_several_filled_orders_on_massively_imbalanced_sides(
    mode, worker, other_worker, do_initial_allocation, base_account
):
    """
    When sides are massively imbalanced, make sure that spread will be closed after filling several orders on smaller
    side. The goal is to test a situation when one side has a big-sized orders, and other side has much smaller orders.
    Correct behavior: when multiple orders on smaller side filled at once, big side should place appropriate number of
    closer orders to close the spread.

    Test for https://github.com/Codaone/DEXBot/issues/601
    """
    worker.mode = mode
    do_initial_allocation(worker, worker.mode)
    spread_before = worker.get_actual_spread()
    log.info('Worker spread after bootstrap: {}'.format(spread_before))
    # TODO: automatically turn off bootstrapping after target spread is closed?
    worker['bootstrapping'] = False

    # Cancel several closest orders
    num_orders_to_cancel = 3
    worker.cancel_orders_wrapper(worker.sell_orders[:num_orders_to_cancel])
    worker.refresh_orders()
    worker.refresh_balances()

    # Place limited orders; the goal is to limit order amount to be much smaller than opposite
    quote_limit = worker.buy_orders[0]['quote']['amount'] * worker.partial_fill_threshold / 2
    place_limited_order = True
    spread_after = worker.get_actual_spread()
    while spread_after >= worker.target_spread + worker.increment:
        # We're using spread check because we cannot just place same number of orders as num_orders_to_cancel because
        # it may result in too close spread because of price shifts
        limit = quote_limit if place_limited_order else None
        worker.place_closer_order('quote', worker.sell_orders[0], own_asset_limit=limit)
        worker.refresh_orders()
        worker.sync_current_orders()
        spread_after = worker.get_actual_spread()
        place_limited_order = False  # only first order should be limited

    log.info('Worker spread: {}'.format(worker.get_actual_spread()))

    # Fill only one newly placed order from another account
    num_orders_to_fill = num_orders_to_cancel
    for i in range(0, num_orders_to_fill):
        price = worker.sell_orders[i]['price'] ** -1 * 1.01
        amount = worker.sell_orders[i]['base']['amount'] * 1.01
        log.debug('Filling {} @ {}'.format(amount, price))
        other_worker.place_market_buy_order(amount, price)

    # Cancel unmatched dust
    other_worker.cancel_all_orders()
    worker.refresh_orders()
    worker.refresh_balances(use_cached_orders=True)

    # Allocate obtained BASE
    counter = 0
    spread_after = worker.get_actual_spread()
    while spread_after >= worker.target_spread + worker.increment:
        worker.allocate_asset('base', worker.base_balance)
        worker.refresh_orders()
        worker.refresh_balances(use_cached_orders=True)
        spread_after = worker.get_actual_spread()
        counter += 1
        # Counter is for preventing infinity loop
        # Success execution means target spread is reached
        assert counter < 20


@pytest.mark.parametrize('mode', MODES)
def test_allocate_asset_limiting_on_sell_side(mode, worker, other_worker, do_initial_allocation, base_account):
    """Check order size limiting when placing closer order on side which is bigger (using funds obtained from filled
    orders on side which is smaller)"""
    do_initial_allocation(worker, mode)
    # TODO: automatically turn off bootstrapping after target spread is closed?
    worker['bootstrapping'] = False

    # Fill several orders
    num_orders_to_fill = 4
    for i in range(0, num_orders_to_fill):
        price = worker.buy_orders[i]['price'] / 1.01
        amount = worker.buy_orders[i]['quote']['amount']
        log.debug('Filling buy order buys {} QUOTE @ {}'.format(amount, price))
        other_worker.place_market_sell_order(amount, price)

    # Cancel unmatched dust
    other_worker.cancel_all_orders()

    # Allocate asset until target spread will be reached
    worker.refresh_orders()
    worker.refresh_balances(use_cached_orders=True)
    spread_after = worker.get_actual_spread()
    counter = 0
    while spread_after >= worker.target_spread + worker.increment:
        worker.allocate_asset('quote', worker.quote_balance)
        worker.refresh_orders()
        worker.refresh_balances(use_cached_orders=True)
        spread_after = worker.get_actual_spread()
        counter += 1
        # Counter is for preventing infinity loop
        assert counter < 20

    # Check 2 closest orders to match mode
    if worker.mode == 'valley' or worker.mode == 'sell_slope':
        assert worker.sell_orders[0]['base']['amount'] == pytest.approx(worker.sell_orders[1]['base']['amount'])
    elif worker.mode == 'mountain':
        assert (
            worker.sell_orders[0]['base']['amount']
            == pytest.approx(worker.sell_orders[1]['base']['amount'], abs=(10 ** -worker.market['quote']['precision']))
            or worker.sell_orders[0]['base']['amount'] >= worker.sell_orders[1]['base']['amount']
        )
    elif worker.mode == 'buy_slope':
        assert worker.sell_orders[0]['quote']['amount'] == pytest.approx(
            worker.sell_orders[1]['quote']['amount'], rel=(10 ** -worker.market['base']['precision'])
        )
    elif worker.mode == 'neutral':
        assert worker.sell_orders[0]['base']['amount'] == pytest.approx(
            worker.sell_orders[1]['base']['amount'] * math.sqrt(1 + worker.increment),
            rel=(10 ** -worker.market['quote']['precision']),
        )


@pytest.mark.parametrize('mode', MODES)
def test_allocate_asset_limiting_on_buy_side(mode, worker, other_worker, do_initial_allocation, issue_asset):
    """Check order size limiting when placing closer order on side which is bigger (using funds obtained from filled
    orders on side which is smaller)"""
    worker.center_price = 1
    worker.lower_bound = 0.4
    worker.upper_bound = 1.4
    do_initial_allocation(worker, mode)
    # TODO: automatically turn off bootstrapping after target spread is closed?
    worker['bootstrapping'] = False

    # Fill several orders
    num_orders_to_fill = 5
    for i in range(0, num_orders_to_fill):
        price = worker.sell_orders[i]['price'] ** -1 * 1.01
        amount = worker.sell_orders[i]['base']['amount']
        log.debug('Filling {} QUOTE @ {}'.format(amount, price))
        other_worker.place_market_buy_order(amount, price)

    # Cancel unmatched dust
    other_worker.cancel_all_orders()

    # Allocate asset until target spread will be reached
    worker.refresh_orders()
    worker.refresh_balances(use_cached_orders=True)
    spread_after = worker.get_actual_spread()
    counter = 0
    while spread_after >= worker.target_spread + worker.increment:
        worker.allocate_asset('base', worker.base_balance)
        worker.refresh_orders()
        worker.refresh_balances(use_cached_orders=True)
        spread_after = worker.get_actual_spread()
        counter += 1
        # Counter is for preventing infinity loop
        assert counter < 20

    # Check 2 closest orders to match mode
    if worker.mode == 'valley' or worker.mode == 'buy_slope':
        assert worker.buy_orders[0]['base']['amount'] == worker.buy_orders[1]['base']['amount']
    elif worker.mode == 'mountain':
        # In mountain mode allow both equal orders and increased closest order - it may be placed without limiting
        assert (
            worker.buy_orders[0]['base']['amount']
            == pytest.approx(worker.buy_orders[1]['base']['amount'], abs=(10 ** -worker.market['base']['precision']))
            or worker.buy_orders[0]['base']['amount'] >= worker.buy_orders[1]['base']['amount']
        )
    elif worker.mode == 'sell_slope':
        assert worker.buy_orders[0]['quote']['amount'] == pytest.approx(
            worker.buy_orders[1]['quote']['amount'], rel=(10 ** -worker.market['base']['precision'])
        )
    elif worker.mode == 'neutral':
        assert worker.buy_orders[0]['base']['amount'] == pytest.approx(
            worker.buy_orders[1]['base']['amount'] * math.sqrt(1 + worker.increment),
            rel=(10 ** -worker.market['base']['precision']),
        )


def test_get_actual_spread(worker):
    worker.maintain_strategy()
    # Twice run needed
    worker.maintain_strategy()
    worker.refresh_orders()
    spread = worker.get_actual_spread()
    assert float('Inf') > spread > 0


def test_stop_loss_check(worker, other_worker, do_initial_allocation, issue_asset):
    worker.operational_depth = 100
    worker.target_spread = 0.1  # speed up allocation
    do_initial_allocation(worker, worker.mode)
    # Issue additional QUOTE to 2nd account
    issue_asset(worker.market['quote']['symbol'], 500, other_worker.account.name)

    # Sleep is needed to allow node to update ticker
    time.sleep(2)

    # Normal conditions - stop loss should not be executed
    worker.stop_loss_check()
    assert worker.disabled is False

    # Place bid below lower bound
    other_worker.place_market_buy_order(1, worker.lower_bound / 1.01)

    # Fill all orders pushing price below lower bound
    other_worker.place_market_sell_order(500, worker.lower_bound)

    time.sleep(2)
    worker.refresh_orders()
    worker.stop_loss_check()
    worker.refresh_orders()
    assert len(worker.sell_orders) == 1
    order = worker.sell_orders[0]
    assert order['price'] ** -1 < worker.lower_bound
    assert worker.disabled is True


def test_tick(worker):
    """Check tick counter increment."""
    counter_before = worker.counter
    worker.tick('foo')
    counter_after = worker.counter
    assert counter_after - counter_before == 1
