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
                'center_price_dynamic', 'bool', True, 'Market center price',
                'Begin strategy with center price obtained from the market. Use with mature markets', None),
            ConfigElement(
                'center_price', 'float', 0, 'Manual center price',
                'In an immature market, give a center price manually to begin with. BASE/QUOTE', (0, None, 8, '')),
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
        self.market_center_price = None
        self.buy_orders = []
        self.sell_orders = []
        self.actual_spread = 0
        self.market_spread = 0

        # Order expiration time
        self.expiration = 60 * 60 * 24 * 365 * 5
        self.last_check = datetime.now()

        if self.view:
            self.update_gui_slider()

    def maintain_strategy(self, *args, **kwargs):
        """ Logic of the strategy
            :param args: Order which was added after the bot was started and if there was no market center price
            :param args:
            :param kwargs:
        """

        # Calculate market center price
        # Todo: Move market_center_price to another place? It will be recalculated on each loop now.
        self.market_center_price = self.calculate_center_price(suppress_errors=True)

        # Loop until center price appears on the market
        if not self.market_center_price:
            return

        # Get orders
        orders = self.orders
        market_orders = self.market.orderbook(1)

        # Sort buy and sell orders from biggest to smallest
        self.buy_orders = self.get_buy_orders('DESC', orders)
        self.sell_orders = self.get_sell_orders('DESC', orders)

        # Get highest buy and lowest sell prices from orders
        highest_buy_price = None
        lowest_sell_price = None

        if self.buy_orders:
            highest_buy_order = self.buy_orders[0]
            highest_buy_price = self.buy_orders[0]['price']

        if self.sell_orders:
            lowest_sell_order = self.sell_orders[-1]
            lowest_sell_price = self.sell_orders[-1].invert().get('price')

        # Calculate actual spread
        # Todo: Check the calculation for market_spread and actual_spread.
        if lowest_sell_price and highest_buy_price:
            self.actual_spread = 1 - (highest_buy_price / lowest_sell_price)

        # Calculate market spread
        highest_market_buy = market_orders['bids'][0]['price']
        lowest_market_sell = market_orders['asks'][0]['price']

        if highest_market_buy and lowest_market_sell:
            self.market_spread = 1 - (highest_market_buy / lowest_market_sell)

        # Get current account balances
        account_balances = self.total_balance(order_ids=[], return_asset=True)

        base_balance = account_balances['base']
        quote_balance = account_balances['quote']

        total_value_base = self.asset_total_balance(base_balance['symbol'])
        total_value_quote = self.asset_total_balance(quote_balance['symbol'])

        # Calculate asset thresholds
        base_asset_threshold = total_value_base / 20000
        quote_asset_threshold = total_value_quote / 20000

        # Check boundaries
        if self.market_center_price > self.upper_bound:
            self.upper_bound = self.market_center_price
        elif self.market_center_price < self.lower_bound:
            self.lower_bound = self.market_center_price

        # Base asset check
        if base_balance > base_asset_threshold:
            # Allocate available funds
            self.allocate_base_asset(base_balance)
        elif self.market_center_price > highest_buy_order['base']['price'] * (1 + self.spread):
            # Cancel lowest buy order
            self.shift_orders_up(self.buy_orders[-0])

        # Quote asset check
        if quote_balance > quote_asset_threshold:
            # Allocate available funds
            self.allocate_quote_asset(quote_balance)
        elif self.market_center_price < lowest_sell_order['base']['price'] * (1 - self.spread):
            # Cancel highest sell order
            self.shift_orders_down(self.sell_orders[0])

    def maintain_mountain_mode(self):
        """ Mountain mode
            This structure is not final, but an idea was that each mode has separate function which runs the loop.
        """
        # Todo: Work in progress
        pass

    def allocate_base_asset(self, base_balance, *args, **kwargs):
        """ Allocates base asset
            :param base_balance: Amount of the base asset available to use
        """
        # Todo: Work in progress
        if self.buy_orders:
            # Todo: Make order size check function
            lowest_buy_order = self.buy_orders[-1]
            highest_buy_order = self.buy_orders[0]

            # Check if the order size is correct
            # This check doesn't work at this moment.
            if self.is_order_size_correct(lowest_buy_order, base_balance):
                # Is bot allowed to make orders which might fill immediately
                if self.instant_fill:
                    # Todo: Check if actual_spread calculates correct
                    if self.actual_spread >= self.spread + self.increment:
                        # Todo: Places lower instead of higher, looks more valley than mountain
                        self.place_higher_buy_order(highest_buy_order)
                    else:
                        # This was in the diagram, seems wrong.
                        # Todo: Is highest_sell + increment > upper_bound?
                        # YES -> increase_order_size()
                        # NO -> place_higher_sell() // Should this be buy?
                        pass
                else:
                    # This was in the diagram, is it ok?
                    # Todo: Is highest_buy + increment < lowest_ask
                    # YES -> Goes same place where "instant_fill" YES path
                    # NO -> Goes same place where above mentioned commenting is
                    pass
            else:
                # Cancel highest buy order
                self.cancel(self.buy_orders[0])
        else:
            self.place_lowest_buy_order(base_balance)

    def allocate_quote_asset(self, quote_balance, *args, **kwargs):
        """ Allocates quote asset
        """
        # Todo: Work in progress
        # Almost same as the allocate_base() with some differences, this is done after that
        if self.sell_orders:
            pass
        else:
            self.place_highest_sell_order(quote_balance)

    def is_order_size_correct(self, order, balance):
        """ Checks if the order size is correct
            :return:
        """
        # Todo: Work in progress.
        return True
        # previous_order_size = (order['base']['amount'] + balance['amount']) * self.increment
        # order_size = order['quote']['amount']
        #
        # if previous_order_size == order_size:
        #     return True
        # return False

    def shift_orders_up(self, order):
        """ Removes given order and places higher buy order
            :param order: Order to be removed
        """
        self.cancel(order)
        self.place_higher_buy_order(order)

    def shift_orders_down(self, order):
        """ Removes given order and places lower sell order
            :param order: Order to be removed
        """
        self.cancel(order)
        self.place_lower_sell_order(order)

    def place_higher_buy_order(self, order):
        """ Place higher buy order
            Mode: MOUNTAIN
            amount (QUOTE) = lower_buy_order_amount * (1 + increment)
            price (BASE) = lower_buy_order_price * (1 + increment)

            :param order: Previously highest buy order
        """
        amount = order['quote']['amount'] * (1 + self.increment)
        price = order['price'] * (1 + self.increment)

        self.market_buy(amount, price)

    def place_higher_sell_order(self, order):
        """ Place higher sell order
            Mode: MOUNTAIN
            amount (QUOTE) = higher_sell_order_amount / (1 + increment)
            price (BASE) = higher_sell_order_price * (1 + increment)

            :param order: highest_sell_order
        """
        amount = order['quote']['amount'] / (1 + self.increment)
        price = order['base']['price'] * (1 + self.increment)

        self.market_sell(amount, price)

    def place_lower_buy_order(self, order):
        """ Place lower buy order
            Mode: MOUNTAIN
            amount (QUOTE) = lowest_buy_order_amount / (1 + increment)
            price (BASE) = Order's base price

            :param order: Previously lowest buy order
        """
        amount = order['quote']['amount'] / (1 + self.increment)
        price = order['base']['price']

        self.market_buy(amount, price)

    def place_lower_sell_order(self, order):
        """ Place lower sell order
            Mode: MOUNTAIN
            amount (QUOTE) = higher_sell_order_amount * (1 + increment)
            price (BASE) = higher_sell_order_price / (1 + increment)

            :param order: Previously higher sell order
        """
        amount = order['quote']['amount'] * (1 + self.increment)
        price = order['base']['price'] / (1 + self.increment)

        self.market_sell(amount, price)

    def place_highest_sell_order(self, quote_balance, place_order=True):
        """ Places sell order furthest to the market center price
            Mode: MOUNTAIN
            :param Amount | quote_balance: Available QUOTE asset balance
            :param bool | place_order: Default is True, use this to only calculate highest sell order
            :return dict | order: Returns highest sell order
        """
        price = self.market_center_price * math.sqrt(1 + self.spread)
        previous_price = price

        while price <= self.upper_bound:
            previous_price = price
            price = price * (1 + self.increment)
        else:
            amount = quote_balance['amount'] * self.increment
            price = previous_price
            amount = amount / price

            if place_order:
                self.market_sell(amount, price)
            else:
                return {"amount": amount, "price": price}

    def place_lowest_buy_order(self, base_balance, place_order=True):
        """ Places buy order furthest to the market center price
            Mode: MOUNTAIN
            :param Amount | base_balance: Available BASE asset balance
            :param bool | place_order: Default is True, use this to only calculate lowest buy order
            :return dict | order: Returns lowest buy order
        """
        price = self.market_center_price / math.sqrt(1 + self.spread)
        previous_price = price

        while price >= self.lower_bound:
            previous_price = price
            price = price / (1 + self.increment)
        else:
            amount = base_balance['amount'] * self.increment
            price = previous_price
            amount = amount / price

            if place_order:
                self.market_buy(amount, price)
            else:
                return {"amount": amount, "price": price}

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
