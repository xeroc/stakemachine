import math
from datetime import datetime

from dexbot.basestrategy import BaseStrategy, ConfigElement
from dexbot.qt_queue.idle_queue import idle_add
from dexbot.helper import truncate


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
        self.initial_market_center_price = None
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

        # Save initial market center price, which is used to make sure that first order is still correct
        if not self.initial_market_center_price:
            self.initial_market_center_price = self.market_center_price

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
            highest_buy_price = self.buy_orders[0].get('price')

        if self.sell_orders:
            self.sell_orders[0].invert()
            lowest_sell_price = self.sell_orders[0].get('price')
            self.sell_orders[0].invert()

        # Calculate actual spread
        if highest_buy_price and lowest_sell_price:
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
        elif self.market_center_price < lowest_sell_price * (1 - self.target_spread):
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
            if self.is_order_size_correct(highest_buy_order, self.buy_orders):
                if self.actual_spread >= self.target_spread + self.increment:
                    self.place_higher_buy_order(highest_buy_order)
                elif lowest_buy_order['price'] / (1 + self.increment) < self.lower_bound:
                    # Todo: Work in progress.
                    self.increase_order_sizes('base')
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
            lowest_sell_order = self.sell_orders[0]
            highest_sell_order = self.sell_orders[-1]

            # Check if the order size is correct
            if self.is_order_size_correct(lowest_sell_order, self.sell_orders):
                if self.actual_spread >= self.target_spread + self.increment:
                    self.place_lower_sell_order(lowest_sell_order.invert())
                elif highest_sell_order['price'] * (1 + self.increment) > self.upper_bound:
                    # Todo: Work in progress.
                    self.increase_order_sizes('quote')
                else:
                    self.place_higher_sell_order(highest_sell_order)
            else:
                # Cancel lowest sell order
                self.cancel(self.sell_orders[0])
        else:
            self.place_highest_sell_order(quote_balance)

    # Todo: Check completely
    def increase_order_sizes(self, asset):
        """ Checks which order should be increased in size and replaces it
            with a maximum size order, according to global limits. Logic
            depends on mode in question
        """
        pass
        # Mountain mode:
        # if self.mode == 'mountain':
        #     if asset == quote:
        #         """ Starting from lowest order, for each order, see if it is approximately
        #             maximum size.
        #             If it is, move on to next.
        #             If not, cancel it and replace with maximum size order. Then return.
        #             If highest_sell_order is reached, increase it to maximum size
        #
        #             Maximum size is:
        #             as many quote as the order below
        #             and
        #             as many quote * (1 + increment) as the order above
        #             When making an order, it must not exceed either of these limits, but be
        #             made according to the more limiting criteria.
        #         """
        #         # get orders and amounts to be compared
        #         higher_order_number = 1
        #         observe_order_number = 0
        #         lower_order_number = 0
        #
        #         can_be_increased = False
        #
        #         # see if order size can be increased
        #         while not can_be_increased:
        #             higher_order = self.sell_orders[higher_order_number]
        #             observe_order = self.sell_orders[observe_order_number]
        #             if observe_order_number == 0:
        #                 lower_order = self.buy_order[0]
        #             else:
        #                 lower_order = self.sell_orders[lower_order_number]
        #             observe_order_amount = observe_order['quote']['amount']
        #             limit_from_below = lower_order['quote']['amount']
        #             limit_from_above = higher_order['quote']['amount'] * (1 + self.increment)
        #
        #             if limit_from_below >= observe_order_amount * (1 + self.increment / 10) <= limit_from_above:
        #                 can_be_increased = True
        #             else:
        #                 observe_order_number += 1
        #                 higher_order_number = observe_order_number + 1
        #                 lower_order_number = observe_order_number - 1
        #                 continue
        #
        #         # calculate new order size and make order
        #
        #         if limit_from_above > limit_from_below:
        #             new_order_amount = limit_from_below
        #         else:
        #             new_order_amount = limit_from_above
        #
        #         if quote_balance - reserve_quote_amount < new_order_amount - observe_order_amount:
        #             new_order_amount = observe_order_amount + quote_balance - reserve_quote_amount
        #
        #         price = observe_order['price']
        #         self.cancel(observe_order)
        #         self.market_sell(new_order_amount, price)
        #
        #     elif asset == base:
        #         """ Starting from highest order, for each order, see if it is approximately
        #             maximum size.
        #             If it is, move on to next.
        #             If not, cancel it and replace with maximum size order. Then return.
        #             If highest_sell_order is reached, increase it to maximum size
        #
        #             Maximum size is:
        #             as many base as the order above
        #             and
        #             as many base * (1 + increment) as the order below
        #             When making an order, it must not exceed either of these limits, but be
        #             made according to the more limiting criteria.
        #         """
        # elif self.mode == 'valley':
        #     pass
        # elif self.mode == 'neutral':
        #     pass
        # elif self.mode == 'buy_slope':
        #     pass
        # elif self.mode == 'sell_slope':
        #     pass
        # return None

    def is_order_size_correct(self, order, orders):
        """ Checks if the order size is correct

            :param order: Order closest to the center price from buy or sell side
            :param orders: List of buy or sell orders
            :return: bool | True = Order is correct size or within the threshold
                            False = Order is not right size
        """
        if self.is_sell_order(order):
            order_size = order['base']['amount']
            threshold = self.increment / 10
            upper_threshold = order_size * (1 + threshold)
            lower_threshold = order_size / (1 + threshold)

            lowest_sell_order = orders[0]
            highest_sell_order = orders[-1]

            # Order is the only sell order, and size must be calculated like initializing
            if lowest_sell_order == highest_sell_order:
                total_balance = self.total_balance(orders, return_asset=True)
                highest_sell_order = self.place_highest_sell_order(total_balance['quote'],
                                                                   place_order=False,
                                                                   market_center_price=self.initial_market_center_price)

                # Check if the old order is same size with accuracy of 0.1%
                if lower_threshold <= highest_sell_order['amount'] <= upper_threshold:
                    return True
                return False
            elif order == highest_sell_order:
                order_index = orders.index(order)
                higher_sell_order = self.place_higher_sell_order(orders[order_index - 1], place_order=False)

                if lower_threshold <= higher_sell_order['amount'] <= upper_threshold:
                    return True
                return False
            elif order == lowest_sell_order:
                order_index = orders.index(order)
                lower_sell_order = self.place_lower_sell_order(orders[order_index + 1], place_order=False)

                if lower_threshold <= lower_sell_order['amount'] <= upper_threshold:
                    return True
                return False
        elif self.is_buy_order(order):
            order_size = order['quote']['amount']
            threshold = self.increment / 10
            upper_threshold = order_size * (1 + threshold)
            lower_threshold = order_size / (1 + threshold)

            lowest_buy_order = orders[-1]
            highest_buy_order = orders[0]

            # Order is the only buy order, and size must be calculated like initializing
            if highest_buy_order == lowest_buy_order:
                total_balance = self.total_balance(orders, return_asset=True)
                lowest_buy_order = self.place_lowest_buy_order(total_balance['base'],
                                                               place_order=False,
                                                               market_center_price=self.initial_market_center_price)

                # Check if the old order is same size with accuracy of 0.1%
                if lower_threshold <= lowest_buy_order['amount'] <= upper_threshold:
                    return True
                return False
            elif order == lowest_buy_order:
                order_index = orders.index(order)
                lower_buy_order = self.place_lower_buy_order(orders[order_index - 1], place_order=False)

                if lower_threshold <= lower_buy_order['amount'] <= upper_threshold:
                    return True
                return False
            elif order == highest_buy_order:
                order_index = orders.index(order)
                higher_buy_order = self.place_higher_buy_order(orders[order_index + 1], place_order=False)

                if lower_threshold <= higher_buy_order['amount'] <= upper_threshold:
                    return True
                return False

        return False

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
        amount = order['quote']['amount']
        price = order['price'] / (1 + self.increment)

        if place_order:
            self.market_sell(amount, price)
        else:
            return {"amount": amount, "price": price}

    def place_highest_sell_order(self, quote_balance, place_order=True, market_center_price=None):
        """ Places sell order furthest to the market center price
            Mode: MOUNTAIN
            :param Amount | quote_balance: Available QUOTE asset balance
            :param bool | place_order: True = Places order to the market, False = returns amount and price
            :return dict | order: Returns highest sell order
        """
        # Todo: Fix edge case where CP is close to upper bound and will go over.
        if not market_center_price:
            market_center_price = self.market_center_price

        price = market_center_price * math.sqrt(1 + self.target_spread)
        previous_price = price

        amount = quote_balance['amount'] * self.increment
        previous_amount = amount

        while price <= self.upper_bound:
            previous_price = price
            previous_amount = amount

            price = price * (1 + self.increment)
            amount = amount / (1 + self.increment)
        else:
            # Todo: Fix precision to match wanted asset
            precision = self.market['quote']['precision']
            amount = int(float(previous_amount) * 10 ** precision) / (10 ** precision)
            price = previous_price

            if place_order:
                self.market_sell(amount, price)
            else:
                amount = truncate(amount, precision)
                return {"amount": amount, "price": price}

    def place_lowest_buy_order(self, base_balance, place_order=True, market_center_price=None):
        """ Places buy order furthest to the market center price
            Mode: MOUNTAIN
            :param Amount | base_balance: Available BASE asset balance
            :param bool | place_order: True = Places order to the market, False = returns amount and price
            :param float | market_center_price: Optional market center price, used to to check order
            :return dict | order: Returns lowest buy order
        """
        # Todo: Fix edge case where CP is close to lower bound and will go over.
        if not market_center_price:
            market_center_price = self.market_center_price

        price = market_center_price / math.sqrt(1 + self.target_spread)
        previous_price = price

        amount = base_balance['amount'] * self.increment
        previous_amount = amount

        while price >= self.lower_bound:
            previous_price = price
            previous_amount = amount

            price = price / (1 + self.increment)
            amount = amount / (1 + self.increment)
        else:
            precision = self.market['base']['precision']
            amount = previous_amount / price
            amount = int(float(amount) * 10 ** precision) / (10 ** precision)

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
