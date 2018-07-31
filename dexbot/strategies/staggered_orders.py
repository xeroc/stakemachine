import math
from datetime import datetime
from datetime import timedelta

from dexbot.basestrategy import BaseStrategy, ConfigElement
from dexbot.controllers.strategy_controller import StaggeredOrdersController
from dexbot.qt_queue.idle_queue import idle_add


class Strategy(BaseStrategy):
    """ Staggered Orders strategy """

    @classmethod
    def configure(cls, return_base_config=True):
        return BaseStrategy.configure(return_base_config) + [
            ConfigElement(
                'strategy_mode', 'choice', 'mountain',
                'How to allocate funds and profits. Doesn\'t effect existing orders, only future ones',
                StaggeredOrdersController.strategy_modes_tuples(), (0, None, 0, '')),
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
        self.onMarketUpdate += self.maintain_strategy()
        self.onAccount += self.maintain_strategy()
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

        # Order expiration time
        self.expiration = 60 * 60 * 24 * 365 * 5
        self.last_check = datetime.now()

        if self.view:
            self.update_gui_slider()

    def maintain_strategy(self):
        """ Logic of the strategy """
        # Get orders
        orders = self.orders

        # Calculate market center price
        market_center_price = self.calculate_center_price()

        # Get sorted orders
        buy_orders = self.get_buy_orders('DESC', orders)
        sell_orders = self.get_sell_orders('DESC', orders)

        # Highest buy and lowest sell prices
        highest_buy_price = buy_orders[0]
        lowest_sell_price = sell_orders[-1]

        # Get account balances
        base_asset_balance = self.balance(self.market['base']['symbol'])
        quote_asset_balance = self.balance(self.market['quote']['symbol'])

        # Calculate asset thresholds
        base_asset_threshold = base_asset_balance / 20000
        quote_asset_threshold = quote_asset_balance / 20000

        # Check boundaries
        if market_center_price > self.upper_bound:
            self.upper_bound = market_center_price
        elif market_center_price < self.lower_bound:
            self.lower_bound = market_center_price

        # Base asset check
        # Todo: Check the logic
        if base_asset_balance > base_asset_threshold:
            self.allocate_base()
        else:
            if market_center_price > highest_buy_price * (1 + self.spread):
                self.shift_orders_up()

        # Check which mode is in use
        if self.mode == 'mountain':
            self.maintain_mountain_mode()

    def maintain_mountain_mode(self):
        """ Mountain mode """
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
