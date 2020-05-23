import copy
from decimal import Decimal

from bitshares.price import Price

from dexbot.decorators import check_last_run
from dexbot.strategies.base import StrategyBase
from dexbot.strategies.config_parts.koth_config import KothConfig

STRATEGY_NAME = 'King of the Hill'


class Strategy(StrategyBase):
    """
    King of the Hill strategy.

    This worker will place a buy or sell order for an asset and update so that the users order stays closest to the
    opposing order book.

    Moving forward: If any other orders are placed closer to the opposing order book the worker will cancel the
    users order and replace it with one that is the smallest possible increment closer to the opposing order book
    than any other orders.

    Moving backward: If the users order is the closest to the opposing order book but a gap opens up on the order
    book behind the users order the worker will cancel the order and place it at the smallest possible increment
    closer to the opposing order book than any other order.
    """

    def __init__(self, *args, **kwargs):
        # Initializes StrategyBase class
        super().__init__(*args, **kwargs)

        self.log.info("Initializing {}...".format(STRATEGY_NAME))

        # Tick counter
        self.counter = 0

        # Define Callbacks
        self.onMarketUpdate += self.maintain_strategy
        self.ontick += self.tick

        self.error_ontick = self.error
        self.error_onMarketUpdate = self.error
        self.error_onAccount = self.error

        # Get view
        self.view = kwargs.get('view')

        self.worker_name = kwargs.get('name')

        self.mode = self.worker.get('mode', 'both')
        self.top_buy_price = 0
        self.top_sell_price = 0
        self.buy_order_amount = float(self.worker.get('buy_order_amount', 0))
        self.sell_order_amount = float(self.worker.get('sell_order_amount', 0))
        self.is_relative_order_size = self.worker.get('relative_order_size', False)
        self.buy_order_size_threshold = self.worker.get('buy_order_size_threshold', 0)
        self.sell_order_size_threshold = self.worker.get('sell_order_size_threshold', 0)
        self.upper_bound = self.worker.get('upper_bound', 0)
        self.lower_bound = self.worker.get('lower_bound', 0)
        self.min_order_lifetime = self.worker.get('min_order_lifetime', 1)

        self.orders = {}
        self.check_interval = self.min_order_lifetime
        self.partial_fill_threshold = 0.8
        # Stubs
        self.highest_bid = 0
        self.lowest_ask = 0
        self.buy_gap = 0
        self.sell_gap = 0

        if self.view:
            self.update_gui_slider()

        # Make sure we're starting from scratch as we don't keeping orders in the db
        self.cancel_all_orders()

        self.call_orders_expected = False
        self.debt_asset = None
        self.check_bitasset_market()

        self.log.info("{} initialized.".format(STRATEGY_NAME))

    @property
    def amount_quote(self):
        """Get quote amount, calculate if order size is relative."""
        amount = self.sell_order_amount
        if self.is_relative_order_size:
            balance = self.get_operational_balance()
            amount = balance['quote'] * (amount / 100)

        return amount

    @property
    def amount_base(self):
        """Get base amount, calculate if order size is relative."""
        amount = self.buy_order_amount
        if self.is_relative_order_size:
            balance = self.get_operational_balance()
            amount = balance['base'] * (amount / 100)

        return amount

    @classmethod
    def configure(cls, return_base_config=True):
        return KothConfig.configure(return_base_config)

    @classmethod
    def configure_details(cls, include_default_tabs=True):
        return KothConfig.configure_details(include_default_tabs)

    def check_bitasset_market(self):
        """Check if worker market is MPA:COLLATERAL market."""
        if not (self.market['base'].is_bitasset or self.market['quote'].is_bitasset):
            # One of the assets must be a bitasset
            return

        if self.market['base'].is_bitasset:
            self.market['base'].ensure_full()
            if self.market['base']['bitasset_data']['is_prediction_market']:
                return
            backing = self.market['base']['bitasset_data']['options']['short_backing_asset']
            if backing == self.market['quote']['id']:
                self.debt_asset = self.market['base']
                self.call_orders_expected = True

        if self.market['quote'].is_bitasset:
            self.market['quote'].ensure_full()
            if self.market['quote']['bitasset_data']['is_prediction_market']:
                return
            backing = self.market['quote']['bitasset_data']['options']['short_backing_asset']
            if backing == self.market['base']['id']:
                self.debt_asset = self.market['quote']
                self.call_orders_expected = True

    @check_last_run
    def maintain_strategy(self, *args):
        """Strategy main logic."""

        if self.orders:
            self.check_orders()
        else:
            self.place_orders()

    def check_orders(self):
        """Check whether own orders needs intervention."""
        self.get_top_prices()

        orders = copy.deepcopy(self.orders)
        for order_type, order_id in orders.items():
            order = self.get_order(order_id)
            need_cancel = False

            if order:
                is_partially_filled = self.is_partially_filled(order, threshold=self.partial_fill_threshold)
                if is_partially_filled:
                    # If own order filled too much, replace it with new order
                    self.log.info('Own {} order filled too much, resetting'.format(order_type))
                    need_cancel = True
                # Check if someone put order above ours or beaten order was canceled
                elif order_type == 'buy':
                    diff = abs(order['price'] - self.top_buy_price)
                    if order['price'] < self.top_buy_price:
                        self.log.debug('Detected an order above ours')
                        need_cancel = True
                    elif diff > self.buy_gap:
                        self.log.debug('Too much gap between our top buy order and next further order: %s', diff)
                        need_cancel = True
                elif order_type == 'sell':
                    diff = abs(order['price'] ** -1 - self.top_sell_price)
                    if order['price'] ** -1 > self.top_sell_price:
                        self.log.debug('Detected an order above ours')
                        need_cancel = True
                    elif diff > self.sell_gap:
                        self.log.debug('Too much gap between our top sell order and further order: %s', diff)
                        need_cancel = True

            # Own order is not there
            else:
                self.log.info('Own {} order filled, placing a new one'.format(order_type))
                self.place_order(order_type)

            if need_cancel and self.cancel_orders(order):
                self.place_order(order_type)

    def get_top_prices(self):
        """Get current top prices (foreign orders)"""
        # Obtain orderbook orders excluding our orders
        market_orders = self.get_market_orders(depth=100)
        own_orders_ids = [order['id'] for order in self.own_orders]
        market_orders = [order for order in market_orders if order['id'] not in own_orders_ids]
        buy_orders = self.filter_buy_orders(market_orders)
        sell_orders = self.filter_sell_orders(market_orders, invert=True)

        # xxx_order_size_threshold indicates order price we need to beat
        sell_order_size_threshold = self.sell_order_size_threshold
        if not sell_order_size_threshold:
            sell_order_size_threshold = self.amount_quote

        buy_order_size_threshold = self.buy_order_size_threshold
        if not buy_order_size_threshold:
            buy_order_size_threshold = self.amount_base

        # Note that we're operating on inverted orders here
        for order in sell_orders:
            if order['quote']['amount'] > sell_order_size_threshold:
                self.top_sell_price = order['price']
                if self.top_sell_price < self.lower_bound:
                    self.log.debug(
                        'Top sell price to be higher {:.8f} < lower bound {:.8f}'.format(
                            self.top_sell_price, self.lower_bound
                        )
                    )
                    self.top_sell_price = self.lower_bound
                else:
                    self.log.debug('Top sell price to be higher: {:.8f}'.format(self.top_sell_price))
                break

        for order in buy_orders:
            if order['base']['amount'] > buy_order_size_threshold:
                self.top_buy_price = order['price']
                if self.top_buy_price > self.upper_bound:
                    self.log.debug(
                        'Top buy price to be higher {:.8f} > upper bound {:.8f}'.format(
                            self.top_buy_price, self.upper_bound
                        )
                    )
                    self.top_buy_price = self.upper_bound
                else:
                    self.log.debug('Top buy price to be higher: {:.8f}'.format(self.top_buy_price))
                break

        if self.call_orders_expected:
            call_order = self.get_cumulative_call_order(self.debt_asset)
            if self.debt_asset == self.market['base'] and call_order['base']['amount'] > sell_order_size_threshold:
                call_price = call_order['price'] ** -1
                self.log.debug('Margin call on market {} at price {:.8f}'.format(self.worker['market'], call_price))
                # If no orders on market, set price to Inf (default is 0 to indicate no orders
                self.top_sell_price = self.top_sell_price or float('Inf')
                if call_price < self.top_sell_price:
                    self.log.debug('Correcting top sell price to {:.8f}'.format(call_price))
                    self.top_sell_price = call_price
            elif self.debt_asset == self.market['quote'] and call_order['base']['amount'] > buy_order_size_threshold:
                call_price = call_order['price']
                self.log.debug('Margin call on market {} at price {:.8f}'.format(self.worker['market'], call_price))
                if call_price > self.top_buy_price:
                    self.log.debug('Correcting top buy price to {:.8f}'.format(call_price))
                    self.top_buy_price = call_price

        # Fill top prices from orderbook because we need to keep in mind own orders too
        # FYI: getting price from self.ticker() doesn't work in local testnet
        orderbook = self.get_orderbook_orders(depth=1)
        try:
            self.highest_bid = orderbook['bids'][0]['price']
            self.lowest_ask = orderbook['asks'][0]['price']
        except IndexError:
            self.log.info('Market has empty orderbook')

    def get_cumulative_call_order(self, asset):
        """
        Get call orders, compound them and return as it was a single limit order.

        :param Asset asset: bitshares asset
        :return: dict representing an order
        """
        # TODO: move this method to price engine to use for center price detection etc
        call_orders = asset.get_call_orders()
        collateral = debt = 0
        for call in call_orders:
            collateral += call['collateral']['amount']
            debt += call['debt']['amount']

        settlement_price = Price(asset['bitasset_data']['current_feed']['settlement_price'])
        maximum_short_squeeze_ratio = asset['bitasset_data']['current_feed']['maximum_short_squeeze_ratio'] / 100
        call_price = settlement_price / maximum_short_squeeze_ratio
        order = {'base': {'amount': collateral}, 'quote': {'amount': debt}, 'price': float(call_price)}
        return order

    def is_too_small_amounts(self, amount_quote, amount_base):
        """
        Check whether amounts are within asset precision limits.

        :param Decimal amount_quote: QUOTE asset amount
        :param Decimal amount_base: BASE asset amount
        :return: bool True = amounts are too small
                      False = amounts are within limits
        """
        if (
            amount_quote < Decimal(10) ** -self.market['quote']['precision']
            or amount_base < Decimal(10) ** -self.market['base']['precision']
        ):
            return True

        return False

    def place_order(self, order_type):
        """Place single order."""
        new_order = None

        if order_type == 'buy':
            if not self.top_buy_price:
                self.log.error('Cannot determine top buy price, correct your bounds and/or ignore thresholds')
                self.disabled = True
                return

            amount_base = Decimal(self.amount_base).quantize(Decimal(0).scaleb(-self.market['base']['precision']))
            if not amount_base:
                if self.mode == 'both':
                    self.log.debug('Not placing %s order in "both" mode due to insufficient balance', order_type)
                else:
                    self.log.error(
                        'Cannot place {} order with 0 amount. Adjust your settings or add balance'.format(order_type)
                    )
                return False

            price = Decimal(self.top_buy_price)
            amount_quote = (amount_base / price).quantize(Decimal(0).scaleb(-self.market['quote']['precision']))
            price = amount_base / amount_quote
            while price <= self.top_buy_price:
                # Decrease quote amount until price will become higher
                amount_quote -= Decimal(10) ** -self.market['quote']['precision']
                price = amount_base / amount_quote

            # Limit price by upper bound
            if price > self.upper_bound:
                price = Decimal(self.upper_bound)
                amount_quote = amount_base / price

            # Prevent too small amounts
            if self.is_too_small_amounts(amount_quote, amount_base):
                self.log.error('Amount for {} order is too small'.format(order_type))
                return

            # Check crossing with opposite orders
            if price >= self.lowest_ask:
                self.log.warning(
                    'Cannot place top {} order because it will cross the opposite side; '
                    'increase your order size to lower price step; my top price: {:.8f}, lowest ast: '
                    '{:.8f}'.format(order_type, price, self.lowest_ask)
                )
                return

            new_order = self.place_market_buy_order(float(amount_quote), float(price))
        elif order_type == 'sell':
            if not self.top_sell_price:
                self.log.error('Cannot determine top sell price, correct your bounds and/or ignore thresholds')
                self.disabled = True
                return

            amount_quote = Decimal(self.amount_quote).quantize(Decimal(0).scaleb(-self.market['quote']['precision']))
            if not amount_quote:
                if self.mode == 'both':
                    self.log.debug('Not placing %s order in "both" mode due to insufficient balance', order_type)
                else:
                    self.log.error(
                        'Cannot place {} order with 0 amount. Adjust your settings or add balance'.format(order_type)
                    )
                return False

            price = Decimal(self.top_sell_price)
            amount_base = (amount_quote * price).quantize(Decimal(0).scaleb(-self.market['base']['precision']))
            price = amount_base / amount_quote
            while price >= self.top_sell_price:
                # Decrease base amount until price will become lower
                amount_base -= Decimal(10) ** -self.market['base']['precision']
                price = amount_base / amount_quote

            # Limit price by lower bound
            if price < self.lower_bound:
                price = Decimal(self.lower_bound)

            # Prevent too small amounts
            if self.is_too_small_amounts(amount_quote, amount_base):
                self.log.error('Amount for {} order is too small'.format(order_type))
                return

            # Check crossing with opposite orders
            if price <= self.highest_bid:
                self.log.warning(
                    'Cannot place top {} order because it will cross the opposite side; '
                    'increase your order size to lower price step; my top price: {:.8f}, highest bid: '
                    '{:.8f}'.format(order_type, price, self.highest_bid)
                )
                return

            new_order = self.place_market_sell_order(float(amount_quote), float(price))

        if new_order:
            # Store own order into dict {order_type: id} to perform checks later
            self.orders[order_type] = new_order['id']
            if order_type == 'buy':
                self.buy_gap = new_order['price'] - self.top_buy_price
            elif order_type == 'sell':
                self.sell_gap = self.top_sell_price - new_order['price'] ** -1
        else:
            self.log.error('Failed to place {} order'.format(order_type))

    def place_orders(self):
        """Place new orders."""
        place_buy = False
        place_sell = False

        self.get_top_prices()

        if self.mode == 'both':
            place_buy = True
            place_sell = True
        elif self.mode == 'buy':
            place_buy = True
        elif self.mode == 'sell':
            place_sell = True

        if place_buy:
            self.place_order('buy')
        if place_sell:
            self.place_order('sell')

    def error(self, *args, **kwargs):
        """Defines what happens when error occurs."""
        self.disabled = True

    def tick(self, block_hash):
        """Ticks come in on every block."""
        if not (self.counter or 0) % 4:
            self.maintain_strategy()
        self.counter += 1
