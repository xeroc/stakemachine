import math
from datetime import datetime

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
                'The top price in the range', (0, None, 8, ''))
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
        self.target_spread = self.worker['spread'] / 100
        self.increment = self.worker['increment'] / 100
        self.upper_bound = self.worker['upper_bound']
        self.lower_bound = self.worker['lower_bound']

        # Strategy variables
        self.market_center_price = None
        self.buy_orders = []
        self.sell_orders = []
        self.actual_spread = self.target_spread + 1
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
        self.sell_orders = self.get_sell_orders('ASC', orders)

        # Get highest buy and lowest sell prices from orders
        highest_buy_price = None
        lowest_sell_price = None

        if self.buy_orders:
            highest_buy_price = self.buy_orders[0]['price']

        if self.sell_orders:
            lowest_sell_order = self.sell_orders[0]
            # Sell orders are inverted by default, this is reversed for price comparison
            lowest_sell_price = lowest_sell_order.invert().get('price')
            lowest_sell_order.invert()

        # Calculate actual spread
        if lowest_sell_price and highest_buy_price:
            self.actual_spread = lowest_sell_price / highest_buy_price - 1

        # Calculate market spread
        highest_market_buy = market_orders['bids'][0]['price']
        lowest_market_sell = market_orders['asks'][0]['price']

        if highest_market_buy and lowest_market_sell:
            self.market_spread = lowest_market_sell / highest_market_buy - 1

        # Get current account balances
        account_balances = self.total_balance(order_ids=[], return_asset=True)

        base_balance = account_balances['base']
        quote_balance = account_balances['quote']

        order_ids = [order['id'] for order in orders]
        orders_balance = self.orders_balance(order_ids)

        # Balance per asset from orders and account balance
        quote_orders_balance = orders_balance['quote'] + quote_balance['amount']
        base_orders_balance = orders_balance['base'] + base_balance['amount']

        # Calculate asset thresholds
        base_asset_threshold = base_orders_balance / 20000
        quote_asset_threshold = quote_orders_balance / 20000

        # Check boundaries
        if self.market_center_price > self.upper_bound:
            self.upper_bound = self.market_center_price
        elif self.market_center_price < self.lower_bound:
            self.lower_bound = self.market_center_price

        # BASE asset check
        if base_balance > base_asset_threshold:
            # Allocate available funds
            self.allocate_base_asset(base_balance)
        elif self.market_center_price > highest_buy_price * (1 + self.target_spread):
            # Cancel lowest buy order
            self.cancel(self.buy_orders[-1])

        # QUOTE asset check
        if quote_balance > quote_asset_threshold:
            # Allocate available funds
            self.allocate_quote_asset(quote_balance)
        if self.market_center_price < lowest_sell_price * (1 - self.target_spread):
            # Cancel highest sell order
            self.cancel(self.sell_orders[-1])

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
            # Get currently the lowest and highest buy orders
            lowest_buy_order = self.buy_orders[-1]
            highest_buy_order = self.buy_orders[0]

            # Check if the order size is correct
            # Todo: This check doesn't work at this moment.
            if self.is_order_size_correct(highest_buy_order, base_balance):
                if self.actual_spread >= self.target_spread + self.increment:
                    self.place_higher_buy_order(highest_buy_order)
                else:
                    if lowest_buy_order['price'] + self.increment < self.lower_bound:
                        self.increase_order_size(highest_buy_order)
                    else:
                        self.place_lower_buy_order(lowest_buy_order)
            else:
                # Cancel highest buy order
                self.cancel(self.buy_orders[0])
        else:
            # Place first buy order to the market
            self.place_lowest_buy_order(base_balance)

    def allocate_quote_asset(self, quote_balance, *args, **kwargs):
        """ Allocates quote asset
        """
        # Todo: Work in progress
        if self.sell_orders:
            # Todo: Make order size check function
            # Todo: Check that the orders are sorted right
            lowest_sell_order = self.sell_orders[0]
            highest_sell_order = self.sell_orders[-1]

            # Check if the order size is correct
            # This check doesn't work at this moment.
            if self.is_order_size_correct(lowest_sell_order, quote_balance):
                if self.actual_spread >= self.target_spread + self.increment:
                    self.place_lower_sell_order(lowest_sell_order)
                else:
                    if highest_sell_order['price'] + self.increment > self.upper_bound:
                        self.increase_order_size(lowest_sell_order)
                    else:
                        self.place_higher_sell_order(highest_sell_order)
            else:
                # Cancel lowest sell order
                self.cancel(self.sell_orders[0])
        else:
            self.place_highest_sell_order(quote_balance)

    def increase_order_size(self, order):
        """ Checks if the order is sell or buy order and then replaces it with a bigger one.
            :param order: Sell / Buy order
        """
        # Todo: Work in progress. pass for now
        pass
        # Cancel order
        self.cancel(order)

        if self.is_sell_order(order):
            # Increase sell order size
            amount = order['base']['amount'] * (1 + self.increment)
            price = order['price']
            self.market_sell(amount, price)
        else:
            # Increase buy order size
            amount = order['quote']['amount'] * (1 + self.increment)
            price = order['price']
            self.market_buy(amount, price)

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


    def place_higher_buy_order(self, order, place_order=True):
        """ Place higher buy order
            Mode: MOUNTAIN
            amount (QUOTE) = lower_buy_order_amount
            price (BASE) = lower_buy_order_price * (1 + increment)

            :param order: Previously highest buy order
            :param bool | place_order: True = Places order to the market, False = returns amount and price
        """
        amount = order['quote']['amount']
        price = order['price'] * (1 + self.increment)

        if place_order:
            self.market_buy(amount, price)
        else:
            return {"amount": amount, "price": price}

    def place_higher_sell_order(self, order, place_order=True):
        """ Place higher sell order
            Mode: MOUNTAIN
            amount (QUOTE) = higher_sell_order_amount / (1 + increment)
            price (BASE) = higher_sell_order_price * (1 + increment)

            :param order: highest_sell_order
            :param bool | place_order: True = Places order to the market, False = returns amount and price
        """
        # Todo: Work in progress.
        amount = order['quote']['amount'] / (1 + self.increment)
        price = order['price'] * (1 + self.increment)

        if place_order:
            self.market_sell(amount, price)
        else:
            return {"amount": amount, "price": price}

    def place_lower_buy_order(self, order, place_order=True):
        """ Place lower buy order
            Mode: MOUNTAIN
            amount (QUOTE) = lowest_buy_order_amount
            price (BASE) = Order's base price / (1 + increment)

            :param order: Previously lowest buy order
            :param bool | place_order: True = Places order to the market, False = returns amount and price
        """
        # Todo: Work in progress.
        amount = order['quote']['amount']
        price = order['price'] / (1 + self.increment)

        if place_order:
            self.market_buy(amount, price)
        else:
            return {"amount": amount, "price": price}

    def place_lower_sell_order(self, order, place_order=True):
        """ Place lower sell order
            Mode: MOUNTAIN
            amount (QUOTE) = higher_sell_order_amount
            price (BASE) = higher_sell_order_price / (1 + increment)

            :param order: Previously higher sell order
            :param bool | place_order: True = Places order to the market, False = returns amount and price
        """
        # Todo: Work in progress.
        amount = order['quote']['amount']
        price = order['price'] / (1 + self.increment)

        if place_order:
            self.market_sell(amount, price)
        else:
            return {"amount": amount, "price": price}

    def place_highest_sell_order(self, quote_balance, place_order=True):
        """ Places sell order furthest to the market center price
            Mode: MOUNTAIN
            :param Amount | quote_balance: Available QUOTE asset balance
            :param bool | place_order: True = Places order to the market, False = returns amount and price
            :return dict | order: Returns highest sell order
        """
        # Todo: Fix edge case where CP is close to upper bound and will go over.
        price = self.market_center_price * math.sqrt(1 + self.target_spread)
        previous_price = price

        amount = quote_balance['amount'] * self.increment
        previous_amount = amount

        while price <= self.upper_bound:
            previous_price = price
            previous_amount = amount

            price = price * (1 + self.increment)
            amount = amount / (1 + self.increment)
            print('Amount, Price ', amount, price)
        else:
            amount = previous_amount
            price = previous_price

            if place_order:
                self.market_sell(amount, price)
            else:
                return {"amount": amount, "price": price}

    def place_lowest_buy_order(self, base_balance, place_order=True):
        """ Places buy order furthest to the market center price
            Mode: MOUNTAIN
            :param Amount | base_balance: Available BASE asset balance
            :param bool | place_order: True = Places order to the market, False = returns amount and price
            :return dict | order: Returns lowest buy order
        """
        # Todo: Fix edge case where CP is close to lower bound and will go over.
        price = self.market_center_price / math.sqrt(1 + self.target_spread)
        previous_price = price

        amount = base_balance['amount'] * self.increment
        previous_amount = amount

        while price >= self.lower_bound:
            previous_price = price
            previous_amount = amount

            price = price / (1 + self.increment)
            amount = amount / (1 + self.increment)
        else:
            amount = previous_amount / price
            price = previous_price

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
