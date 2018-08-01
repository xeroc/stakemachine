import math
from datetime import datetime
from datetime import timedelta

from dexbot.basestrategy import BaseStrategy, ConfigElement
from dexbot.qt_queue.idle_queue import idle_add


class Strategy(BaseStrategy):
    """ Staggered Orders strategy """

    @classmethod
    def configure(cls, return_base_config=True):
        # Todo: - Modes don't list in worker add / edit
        # Todo: - Add other modes
        modes = [
            ('mountain', 'Mountain'),
            # ('neutral', 'Neutral'),
            # ('valley', 'Valley'),
            # ('buy_slope', 'Buy Slope'),
            # ('sell_slope', 'Sell Slope')
        ]

        return BaseStrategy.configure(return_base_config) + [
            ConfigElement(
                'mode', 'choice', 'mountain', 'Strategy mode',
                'How to allocate funds and profits. Doesn\'t effect existing orders, only future ones', modes),
            ConfigElement(
                'spread', 'float', 6, 'Spread',
                'The percentage difference between buy and sell', (0, None, 2, '%')),
            ConfigElement(
                'increment', 'float', 4, 'Increment',
                'The percentage difference between staggered orders', (0, None, 2, '%')),
            ConfigElement(
                'center_price_dynamic', 'bool', True, 'Dynamic center price',
                'Always calculate the middle from the closest market orders', None),
            ConfigElement(
                'center_price', 'float', 0, 'Center price',
                'Fixed center price expressed in base asset: base/quote', (0, None, 8, '')),
            ConfigElement(
                'lower_bound', 'float', 1, 'Lower bound',
                'The bottom price in the range', (0, None, 8, '')),
            ConfigElement(
                'upper_bound', 'float', 1000000, 'Upper bound',
                'The top price in the range', (0, None, 8, '')),
            ConfigElement(
                'allow_instant_fill', 'bool', True, 'Allow instant fill',
                'Allow bot to make orders which might fill immediately upon placement', None)
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Tick counter
        self.counter = 0

        # Define callbacks
        self.onMarketUpdate += self.maintain_strategy
        self.onAccount += self.maintain_strategy
        self.ontick += self.tick
        self.error_ontick = self.error
        self.error_onMarketUpdate = self.error
        self.error_onAccount = self.error

        # Worker parameters
        self.worker_name = kwargs.get('name')
        self.view = kwargs.get('view')
        self.mode = self.worker['mode']
        self.spread = self.worker['spread'] / 100
        self.increment = self.worker['increment'] / 100
        self.upper_bound = self.worker['upper_bound']
        self.lower_bound = self.worker['lower_bound']
        self.instant_fill = self.worker['allow_instant_fill']

        # Strategy variables
        self.buy_orders = []
        self.sell_orders = []

        # Order expiration time
        self.expiration = 60 * 60 * 24 * 365 * 5
        self.last_check = datetime.now()

        if self.view:
            self.update_gui_slider()

    def maintain_strategy(self, *args, **kwargs):
        """ Logic of the strategy
            :param args: Order which was added after the bot was started and if there was no market center price
            :param kwargs:
            :return:
        """

        # Calculate market center price
        market_center_price = self.calculate_center_price(suppress_errors=True)

        # Loop until center price appears on the market
        if not market_center_price:
            return

        # Get orders
        orders = self.orders

        # Sort buy and sell orders
        self.buy_orders = self.get_buy_orders('DESC', orders)
        self.sell_orders = self.get_sell_orders('DESC', orders)

        # Get highest buy and lowest sell prices from orders
        if self.buy_orders:
            highest_buy_order = self.buy_orders[0]

        if self.sell_orders:
            lowest_sell_order = self.sell_orders[-1]

        # Get account balances
        account_balances = self.total_balance(order_ids=[], return_asset=True)

        base_balance = account_balances['base']
        quote_balance = account_balances['quote']

        total_value_base = self.asset_total_balance(base_balance['symbol'])
        total_value_quote = self.asset_total_balance(quote_balance['symbol'])

        # Calculate asset thresholds
        base_asset_threshold = total_value_base / 20000
        quote_asset_threshold = total_value_quote / 20000

        # Check boundaries
        if market_center_price > self.upper_bound:
            self.upper_bound = market_center_price
        elif market_center_price < self.lower_bound:
            self.lower_bound = market_center_price

        # Base asset check
        if total_value_base > base_asset_threshold:
            self.allocate_base_asset()
        else:
            if market_center_price > highest_buy_order['base']['amount'] * (1 + self.spread):
                # Cancel lowest buy order
                self.shift_orders_up(self.buy_orders[-0])

        # Quote asset check
        if total_value_quote > quote_asset_threshold:
            self.allocate_quote_asset()
        else:
            if market_center_price < lowest_sell_order['base']['amount'] * (1 - self.spread):
                # Cancel highest sell order
                self.shift_orders_down(self.sell_orders[0])

    def maintain_mountain_mode(self):
        """ Mountain mode
            This structure is not final, but an idea was that each mode has separate function which runs the loop.
        """
        # Todo: Work in progress
        pass

    def allocate_base_asset(self):
        """ Allocates base asset

            :return:

            bid = market_buy_order
            ask = market_sell_order
            buy = own_buy_order
            sell = own_sell_order

            Mountain mode
            Lowest sell price = cp * spread / 2
            Next sell price = previous price + increment
            Lowest sell amount = Balance * increment
            Next sell amount = last amount + increment

        """
        # Todo: Work in progress, this is based on the strategy diagram
        # Placeholders for now
        bid = 0
        order_size_correct = True
        actual_spread = 0

        if bid:
            if order_size_correct:
                # Todo: Make order size check function
                if self.instant_fill:
                    if actual_spread >= self.spread + self.increment:
                        self.place_higher_buy_order(self.buy_orders[0])
                        return
                else:
                    if self.highest_buy + self.increment < self.lowest_ask:
                        pass
            else:
                # Todo: what order should be canceled?
                self.cancel()
        else:
            self.place_lowest_bid()

    def allocate_quote_asset(self):
        """ Allocates quote asset
        """
        # Todo: Work in progress
        pass

    def shift_orders_up(self, order):
        """ Removes lowest buy order and places higher buy order
            :param order: Lowest buy order
            :return:
        """
        self.cancel(order)
        self.place_higher_buy_order(order)

    def shift_orders_down(self, order):
        """ Removes highest sell order and places lower sell order
            :param order: Highest sell order
            :return:
        """
        self.cancel(order)
        self.place_lower_sell_order(order)

    def place_higher_buy_order(self, order):
        """ Place higher buy order

            amount (QUOTE) = lower_buy_order_amount * (1 + increment)
            price (BASE) = lower_buy_order_price * (1 + increment)

            :param order: Previously highest buy order
            :return:
        """
        amount = order['quote']['amount'] * (1 + self.increment)
        price = order['base']['price'] * (1 + self.increment)

        self.market_buy(amount, price)

    def place_higher_sell_order(self, order):
        """ Place higher sell order

            amount (QUOTE) = higher_sell_order_amount / (1 + increment)
            price (BASE) = higher_sell_order_price * (1 + increment)

            :param order: highest_sell_order
            :return:
        """
        amount = order['quote']['amount'] / (1 + self.increment)
        price = order['base']['price'] * (1 + self.increment)

        self.market_sell(amount, price)

    def place_lower_buy_order(self, order):
        """ Place lower buy order

            amount (QUOTE) = lowest_buy_order_amount / (1 + increment)
            price (BASE) = lowest_buy_order_price / (1 + increment)

            :param order: Previously lowest buy order
            :return:
        """
        amount = order['quote']['amount'] / (1 + self.increment)
        price = order['base']['price'] / (1 + self.increment)

        self.market_buy(amount, price)

    def place_lower_sell_order(self, order):
        """ Place lower sell order

            amount (QUOTE) = higher_sell_order_amount * (1 + increment)
            price (BASE) = higher_sell_order_price / (1 + increment)

            :param order: Previously higher sell order
            :return:
        """
        amount = order['quote']['amount'] * (1 + self.increment)
        price = order['base']['price'] / (1 + self.increment)

        self.market_sell(amount, price)

    def place_lowest_bid(self):
        """
            :return:
        """
        # Todo: Work in progress
        pass

    def place_highest_ask(self):
        """
            :return:
        """
        # Todo: Work in progress
        pass

    def error(self, *args, **kwargs):
        self.disabled = True

    def pause(self):
        """ Override pause() in BaseStrategy """
        pass

    def tick(self, d):
        """ Ticks come in on every block """
        if not (self.counter or 0) % 5:
            self.maintain_strategy()
        self.counter += 1

    def update_gui_slider(self):
        ticker = self.market.ticker()
        latest_price = ticker.get('latest', {}).get('price', None)

        if not latest_price:
            return

        orders = self.fetch_orders()
        if orders:
            order_ids = orders.keys()
        else:
            order_ids = None

        total_balance = self.total_balance(order_ids)
        total = (total_balance['quote'] * latest_price) + total_balance['base']

        # Prevent division by zero
        if not total:
            percentage = 50
        else:
            percentage = (total_balance['base'] / total) * 100

        idle_add(self.view.set_worker_slider, self.worker_name, percentage)
