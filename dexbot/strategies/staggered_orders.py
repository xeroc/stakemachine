import math
from datetime import datetime
from datetime import timedelta

from dexbot.basestrategy import BaseStrategy, ConfigElement
from dexbot.qt_queue.idle_queue import idle_add


class Strategy(BaseStrategy):
    """ Staggered Orders strategy """

    @classmethod
    def configure(cls, return_base_config=True):
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
                'instant_fill', 'bool', True, 'Allow instant fill',
                'Allow to execute orders by market', None)
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
        self.partial_fill_threshold = self.increment / 10
        self.is_instant_fill_enabled = self.worker.get('instant_fill', True)
        self.is_center_price_dynamic = self.worker['center_price_dynamic']
        if self.is_center_price_dynamic:
            self.center_price = None
        else:
            self.center_price = self.worker['center_price']

        # Strategy variables
        # Assume we are in bootstrap mode by default. This prevents weird things when bootstrap was interrupted
        self.bootstrapping = True
        self.market_center_price = None
        self.initial_market_center_price = None
        self.buy_orders = []
        self.sell_orders = []
        self.actual_spread = self.target_spread + 1
        # self.market_spread = 0
        self.base_fee_reserve = None
        self.quote_fee_reserve = None
        self.quote_total_balance = 0
        self.base_total_balance = 0
        self.quote_balance = 0
        self.base_balance = 0
        self.ticker = None
        self.quote_asset_threshold = 0
        self.base_asset_threshold = 0

        # Order expiration time
        self.expiration = 60 * 60 * 24 * 365 * 5
        self.last_check = datetime.now()
        # Minimal check interval is needed to prevent event queue accumulation
        self.min_check_interval = 0.05

        if self.view:
            self.update_gui_slider()

    def maintain_strategy(self, *args, **kwargs):
        """ Logic of the strategy
            :param args:
            :param kwargs:
        """
        self.start = datetime.now()
        delta = self.start - self.last_check

        # Only allow to maintain whether minimal time passed.
        if delta < timedelta(seconds=self.min_check_interval):
            self.log.debug('Ignoring event as min_check_interval has not passed')
            return

        # Get all user's orders on current market
        self.refresh_orders()
        # market_orders = self.market.orderbook(1)

        # Check if market center price is calculated
        if not self.bootstrapping:
            self.market_center_price = self.calculate_center_price(suppress_errors=True)
        elif not self.market_center_price:
            # On empty market we have to pass the user specified center price
            self.market_center_price = self.calculate_center_price(center_price=self.center_price, suppress_errors=True)
            self.log_maintenance_time()
            return
        elif self.market_center_price and not self.initial_market_center_price:
            # Save initial market center price
            self.initial_market_center_price = self.market_center_price

        # Get highest buy and lowest sell prices from orders
        highest_buy_price = 0
        lowest_sell_price = 0

        if self.buy_orders:
            highest_buy_price = self.buy_orders[0].get('price')

        if self.sell_orders:
            lowest_sell_price = self.sell_orders[0].get('price')
            # Invert the sell price to BASE so it can be used in comparison
            lowest_sell_price = lowest_sell_price ** -1

        # Todo: Market spread is calculated but never used, can this be removed?
        # Calculate market spread
        # if there are no orders in both side spread cannot be calculated
        # if len(market_orders['bids']) and len(market_orders['asks']):
        #     highest_market_buy = market_orders['bids'][0]['price']
        #     lowest_market_sell = market_orders['asks'][0]['price']
        #
        #     if highest_market_buy and lowest_market_sell:
        #         self.market_spread = lowest_market_sell / highest_market_buy - 1

        # Calculate balances
        self.refresh_balances()

        # Calculate asset thresholds
        self.quote_asset_threshold = self.quote_total_balance / 20000
        self.base_asset_threshold = self.base_total_balance / 20000

        # Check market's price boundaries
        if self.market_center_price > self.upper_bound:
            self.upper_bound = self.market_center_price
        elif self.market_center_price < self.lower_bound:
            self.lower_bound = self.market_center_price

        # Remove orders that exceed boundaries
        success = self.remove_outside_orders(self.sell_orders, self.buy_orders)
        if success:
            # Refresh orders to prevent orders outside boundaries being in the future comparisons
            self.refresh_orders()
        else:
            # Return back to beginning
            self.log_maintenance_time()
            return

        # BASE asset check
        if self.base_balance > self.base_asset_threshold:
            base_allocated = False
            # Allocate available BASE funds
            self.allocate_base_asset(self.base_balance)
        else:
            base_allocated = True

        # QUOTE asset check
        if self.quote_balance > self.quote_asset_threshold:
            quote_allocated = False
            # Allocate available QUOTE funds
            self.allocate_quote_asset(self.quote_balance)
        else:
            quote_allocated = True

        # Do not continue whether assets is not fully allocated
        if (not base_allocated or not quote_allocated) or self.bootstrapping:
            # Further checks should be performed on next maintenance
            self.last_check = datetime.now()
            self.log_maintenance_time()
            return

        # There are no funds and current orders aren't close enough, try to fix the situation by shifting orders.
        # This is a fallback logic.
        # Measure which price is closer to the center
        buy_distance = self.market_center_price - highest_buy_price
        sell_distance = lowest_sell_price - self.market_center_price

        if buy_distance > sell_distance:
            if self.market_center_price > highest_buy_price * (1 + self.target_spread):
                # Cancel lowest buy order because center price moved up.
                # On the next run there will be placed next buy order closer to the new center
                self.log.debug('Cancelling lowest buy order in maintain_strategy')
                self.cancel(self.buy_orders[-1])
        else:
            if self.market_center_price < lowest_sell_price * (1 - self.target_spread):
                # Cancel highest sell order because center price moved down.
                # On the next run there will be placed next sell closer to the new center
                self.log.debug('Cancelling highest sell order in maintain_strategy')
                self.cancel(self.sell_orders[-1])

        self.last_check = datetime.now()
        self.log_maintenance_time()

    def log_maintenance_time(self):
        """ Measure time from self.start and print a log message
        """
        delta = datetime.now() - self.start
        self.log.debug('Maintenance execution took: {:.2f} seconds'.format(delta.total_seconds()))

    def refresh_balances(self):
        """ This function is used to refresh account balances
        """
        # Get current account balances
        account_balances = self.total_balance(order_ids=[], return_asset=True)

        self.base_balance = account_balances['base']
        self.quote_balance = account_balances['quote']

        # Reserve transaction fee equivalent in BTS
        self.ticker = self.market.ticker()
        core_exchange_rate = self.ticker['core_exchange_rate']
        # Todo: order_creation_fee(BTS) = 0.01 for now
        self.quote_fee_reserve = 0.01 * core_exchange_rate['quote']['amount'] * 100
        self.base_fee_reserve = 0.01 * core_exchange_rate['base']['amount'] * 100

        self.quote_balance['amount'] = self.quote_balance['amount'] - self.quote_fee_reserve
        self.base_balance['amount'] = self.base_balance['amount'] - self.base_fee_reserve

        # Balance per asset from orders
        order_ids = [order['id'] for order in self.orders]
        orders_balance = self.orders_balance(order_ids)

        # Total balance per asset (orders balance and available balance)
        self.quote_total_balance = orders_balance['quote'] + self.quote_balance['amount']
        self.base_total_balance = orders_balance['base'] + self.base_balance['amount']

    def refresh_orders(self):
        """ Updates buy and sell orders
        """
        orders = self.orders

        # Sort orders so that order with index 0 is closest to the center price and -1 is furthers
        self.buy_orders = self.get_buy_orders('DESC', orders)
        self.sell_orders = self.get_sell_orders('DESC', orders)

    def remove_outside_orders(self, sell_orders, buy_orders):
        """ Remove orders that exceed boundaries
            :param list | sell_orders: User's sell orders
            :param list | buy_orders: User's buy orders
        """
        orders_to_cancel = []

        # Remove sell orders that exceed boundaries
        for order in sell_orders:
            order_price = order['price'] ** -1
            if order_price > self.upper_bound:
                self.log.debug('Cancelling sell order outside range: {}'.format(order_price))
                orders_to_cancel.append(order)

        # Remove buy orders that exceed boundaries
        for order in buy_orders:
            order_price = order['price']
            if order_price < self.lower_bound:
                self.log.debug('Cancelling buy order outside range: {}'.format(order_price))
                orders_to_cancel.append(order)

        if orders_to_cancel:
            # We are trying to cancel all orders in one try
            success = self.cancel(orders_to_cancel, batch_only=True)
            # Batch cancel failed, repeat cancelling only one order
            if success:
                return True
            else:
                self.log.debug('Batch cancel failed, failing back to cancelling single order')
                self.cancel(orders_to_cancel[0])
                # To avoid GUI hanging cancel only one order and let switch to another worker
                return False

        return True

    def maintain_mountain_mode(self):
        """ Mountain mode
            This structure is not final, but an idea was that each mode has separate function which runs the loop.
        """
        # Todo: Work in progress
        pass

    def allocate_base_asset(self, base_balance, *args, **kwargs):
        """ Allocates available base asset as buy orders.
            :param base_balance: Amount of the base asset available to use
            :param args:
            :param kwargs:
        """
        self.log.debug('Need to allocate base: {}'.format(base_balance))
        if self.buy_orders:
            # Get currently the lowest and highest buy orders
            lowest_buy_order = self.buy_orders[-1]
            highest_buy_order = self.buy_orders[0]
            lowest_buy_order_price = lowest_buy_order['price']

            # Check if the order size is correct
            if self.check_partial_fill(highest_buy_order):
                # Calculate actual spread
                if self.sell_orders:
                    lowest_sell_price = self.sell_orders[0]['price'] ** -1
                else:
                    # For one-sided start, calculate lowest_sell_price empirically
                    lowest_sell_price = self.market_center_price * (1 + self.target_spread / 2)

                highest_buy_price = highest_buy_order['price']
                self.actual_spread = (lowest_sell_price / highest_buy_price) - 1

                if self.actual_spread >= self.target_spread + self.increment:
                    if self.quote_balance <= self.quote_asset_threshold and self.bootstrapping:
                        """ During the bootstrap we're fist placing orders of some amounts, than we are reaching target
                            spread and then turning bootstrap flag off and starting to allocate remaining balance by
                            gradually increasing order sizes. After bootstrap is complete and following order size
                            increase is complete too, we will not have available balance.

                            When we have a different amount of assets (for example, 100 USD for base and 1 BTC for
                            quote), the orders on the one size will be bigger than at the opposite.

                            During the bootstrap we are not allowing to place orders with limited amount by opposite
                            order. Bootstrap is designed to place orders of the same size. But, when the bootstrap is
                            done, we are beginning to limit new orders by opposite side orders. We need this to stay in
                            game when orders on the lower side gets filled. Because they are less than big-side orders,
                            we cannot just place another big order on the big side. So we are limiting the big-side
                            order to amount of a low-side one!

                            Normally we are turning bootstrap off after initial allocation is done and we're biginning
                            to distribute remaining funds. But, whether we will restart the bot after size increase was
                            done, we have no chance to know if bootsrap was done or not. This is where this check comes
                            in! The situation when the target spread is not reached, but we have some available balance
                            on the one side and not have any free balance of the other side, clearly says to us that an
                            order from lower-side was filled! Thus, we can safely turn bootstrap off and thus place an
                            order limited in size by opposite-side order.
                        """
                        self.log.debug('Turning bootstrapping off: actual_spread > target_spread, and not having '
                                       'opposite-side balance')
                        self.bootstrapping = False
                    # Place order closer to the center price
                    self.log.debug('Placing higher buy order; actual spread: {:.8f}, target + increment: {}'.format(
                                   self.actual_spread, self.target_spread + self.increment))
                    if self.bootstrapping:
                        self.place_higher_buy_order(highest_buy_order)
                    else:
                        # Place order limited by size of the opposite-side order
                        lowest_sell_order = self.sell_orders[0]
                        limit = lowest_sell_order['quote']['amount']
                        self.log.debug('Limiting buy order base by opposite order base asset amount: {}'.format(limit))
                        self.place_higher_buy_order(highest_buy_order, base_limit=limit, allow_partial=False)
                elif not self.sell_orders:
                    # Do not try to do anything than placing higher buy whether there is no sell orders
                    return
                elif lowest_buy_order_price / (1 + self.increment) < self.lower_bound:
                    self.bootstrapping = False
                    # Lower bound has been reached and now will start allocating rest of the base balance.
                    self.log.debug('Increasing orders sizes for BASE asset')
                    self.increase_order_sizes('base', base_balance, self.buy_orders)
                else:
                    # Lower bound is not reached, we need to add additional orders at the extremes
                    self.bootstrapping = False
                    self.log.debug('Placing lower order than lowest_buy_order')
                    self.place_lower_buy_order(lowest_buy_order, allow_partial=True)
            else:
                # Make sure we have enough balance to replace partially filled order
                if base_balance + highest_buy_order['for_sale']['amount'] >= highest_buy_order['base']['amount']:
                    # Cancel highest buy order and immediately replace it with new one.
                    self.log.info('Replacing partially filled buy order')
                    self.cancel(highest_buy_order)
                    self.market_buy(highest_buy_order['quote']['amount'], highest_buy_order['price'])
                    self.refresh_balances()
                else:
                    self.log.debug('Not replacing partially filled order because there is not enough funds')
        else:
            # Place first buy order as close to the lower bound as possible
            self.bootstrapping = True
            self.log.debug('Placing first buy order')
            self.place_lowest_buy_order(base_balance)

        # Get latest orders
        self.refresh_orders()

    def allocate_quote_asset(self, quote_balance, *args, **kwargs):
        """ Allocates available quote asset as sell orders.
            :param quote_balance: Amount of the base asset available to use
            :param args:
            :param kwargs:
        """
        self.log.debug('Need to allocate quote: {}'.format(quote_balance))
        if self.sell_orders:
            lowest_sell_order = self.sell_orders[0]
            highest_sell_order = self.sell_orders[-1]
            # Sell price is inverted so it can be compared to the upper bound
            highest_sell_order_price = (highest_sell_order['price'] ** -1)

            # Check if the order size is correct
            if self.check_partial_fill(lowest_sell_order):
                # Calculate actual spread
                if self.buy_orders:
                    highest_buy_price = self.buy_orders[0]['price']
                else:
                    # For one-sided start, calculate highest_buy_price empirically
                    highest_buy_price = self.market_center_price / (1 + self.target_spread / 2)
                lowest_sell_price = lowest_sell_order['price'] ** -1
                self.actual_spread = (lowest_sell_price / highest_buy_price) - 1

                if self.actual_spread >= self.target_spread + self.increment:
                    if self.base_balance <= self.base_asset_threshold and self.bootstrapping:
                        self.log.debug('Turning bootstrapping off: actual_spread > target_spread, and not having '
                                       'opposite-side balance')
                        self.bootstrapping = False
                    # Place order closer to the center price
                    self.log.debug('Placing lower sell order; actual spread: {:.8f}, target + increment: {}'.format(
                                   self.actual_spread, self.target_spread + self.increment))
                    if self.bootstrapping:
                        self.place_lower_sell_order(lowest_sell_order)
                    else:
                        # Place order limited by opposite-side order
                        highest_buy_order = self.buy_orders[0]
                        limit = self.buy_orders[0]['quote']['amount']
                        self.log.debug('Limiting sell order by opposite order quote: {}'.format(limit))
                        self.place_lower_sell_order(lowest_sell_order, limit=limit, allow_partial=False)
                elif not self.buy_orders:
                    # Do not try to do anything than placing lower sell whether there is no buy orders
                    return
                elif highest_sell_order_price * (1 + self.increment) > self.upper_bound:
                    self.bootstrapping = False
                    # Upper bound has been reached and now will start allocating rest of the quote balance.
                    self.log.debug('Increasing orders sizes for QUOTE asset')
                    self.increase_order_sizes('quote', quote_balance, self.sell_orders)
                else:
                    # Higher bound is not reached, we need to add additional orders at the extremes
                    self.bootstrapping = False
                    self.place_higher_sell_order(highest_sell_order, allow_partial=True)
            else:
                # Make sure we have enough balance to replace partially filled order
                if quote_balance + lowest_sell_order['for_sale']['amount'] >= lowest_sell_order['base']['amount']:
                    # Cancel lowest sell order and immediately replace it with new one.
                    self.log.info('Replacing partially filled sell order')
                    self.cancel(lowest_sell_order)
                    price = lowest_sell_order['price'] ** -1
                    self.market_sell(lowest_sell_order['base']['amount'], price)
                    self.refresh_balances()
                else:
                    self.log.debug('Not replacing partially filled order because there is not enough funds')
        else:
            # Place first order as close to the upper bound as possible
            self.bootstrapping = True
            self.log.debug('Placing first sell order')
            self.place_highest_sell_order(quote_balance)

        # Get latest orders
        self.refresh_orders()

    # Todo: Check completely
    def increase_order_sizes(self, asset, asset_balance, orders):
        # Todo: Change asset or separate buy / sell in different functions?
        """ Checks which order should be increased in size and replaces it
            with a maximum size order, according to global limits. Logic
            depends on mode in question

            :param str | asset: 'base' or 'quote', depending if checking sell or buy
            :param Amount | asset_balance: Balance of the account
            :param list | orders: List of buy or sell orders
            :return None
        """
        # Mountain mode:
        if self.mode == 'mountain':
            # Todo: Work in progress.
            if asset == 'quote':
                """ Starting from the lowest SELL order. For each order, see if it is approximately
                    maximum size.
                    If it is, move on to next.
                    If not, cancel it and replace with maximum size order. Then return.
                    If highest_sell_order is reached, increase it to maximum size

                    Maximum size is:
                    1. As many "quote * (1 + increment)" as the order below (higher_bound)
                    AND
                    2. As many "quote as the order above (lower_bound)

                    Also when making an order it's size always will be limited by available free balance
                """
                # Get orders and amounts to be compared. Note: orders are sorted from low price to high
                for order in orders:
                    order_index = orders.index(order)
                    order_amount = order['base']['amount']

                    # This check prevents choosing order with index lower than the list length
                    if order_index == 0:
                        # In case checking the first order, use the same order, but increased by 1 increment
                        # This allows our lowest sell order amount exceed highest buy order
                        lower_order = order
                        lower_bound = lower_order['base']['amount'] * (1 + self.increment)
                    else:
                        lower_order = orders[order_index - 1]
                        lower_bound = lower_order['base']['amount']

                    # This check prevents choosing order with index higher than the list length
                    if order_index + 1 < len(orders):
                        higher_order = orders[order_index + 1]
                        is_least_order = False
                    else:
                        higher_order = orders[order_index]
                        is_least_order = True

                    higher_bound = higher_order['base']['amount'] * (1 + self.increment)

                    self.log.debug('QUOTE: lower_bound: {}, order_amount: {}, higher_bound: {}'.format(
                        lower_bound, order_amount * (1 + self.increment / 10), higher_bound))

                    if lower_bound > order_amount * (1 + self.increment / 10) < higher_bound:
                        # Calculate new order size and place the order to the market
                        new_order_amount = higher_bound

                        if is_least_order:
                            new_orders_sum = 0
                            amount = order_amount
                            for o in orders:
                                amount = amount * (1 + self.increment)
                                new_orders_sum += amount
                            # To reduce allocation rounds, increase furthest order more
                            new_order_amount = order_amount * (self.quote_total_balance / new_orders_sum) \
                                * (1 + self.increment * 0.75)

                            if new_order_amount < lower_bound:
                                """ This is for situations when calculated new_order_amount is not big enough to
                                    allocate all funds. Use partial-increment increase, so we'll got at least one full
                                    increase round.  Whether we will just use `new_order_amount = lower_bound`, we will
                                    get less than one full allocation round, thus leaving lowest sell order not
                                    increased.
                                """
                                new_order_amount = lower_bound / (1 + self.increment * 0.2)

                        # Limit sell order to available balance
                        if asset_balance < new_order_amount - order_amount:
                            new_order_amount = order_amount + asset_balance['amount']
                            self.log.debug('Limiting new sell order to avail asset balance: {}'.format(
                                new_order_amount))

                        price = (order['price'] ** -1)
                        self.log.debug('Cancelling sell order in increase_order_sizes(); ' 
                                       'mode: mountain, quote: {}, price: {:.8f}'.format(order_amount, price))
                        self.cancel(order)
                        self.market_sell(new_order_amount, price)
                        # Only one increase at a time. This prevents running more than one increment round
                        # simultaneously
                        return
            elif asset == 'base':
                # Todo: Work in progress
                """ Starting from the highest BUY order, for each order, see if it is approximately
                    maximum size.
                    If it is, move on to next.
                    If not, cancel it and replace with maximum size order. Maximum order size will be a
                    size of higher order. Then return.
                    If lowest_buy_order is reached, increase it to maximum size.

                    Maximum size is:
                    1. As many "base * (1 + increment)" as the order below (lower_bound)
                    AND
                    2. As many "base" as the order above (higher_bound)

                    Also when making an order it's size always will be limited by available free balance
                """
                # Get orders and amounts to be compared. Note: orders are sorted from high price to low
                for order in orders:
                    order_index = orders.index(order)
                    order_amount = order['base']['amount']

                    # This check prevents choosing order with index lower than the list length
                    if order_index == 0:
                        # In case checking the first order, use the same order, but increased by 1 increment
                        # This allows our highest buy order amount exceed lowest sell order
                        higher_order = order
                        higher_bound = higher_order['base']['amount'] * (1 + self.increment)
                    else:
                        higher_order = orders[order_index - 1]
                        higher_bound = higher_order['base']['amount']

                    # This check prevents choosing order with index higher than the list length
                    if order_index + 1 < len(orders):
                        # If this is not a lowest_buy_order, lower order is a next order down
                        lower_order = orders[order_index + 1]
                        is_least_order = False
                    else:
                        # Current order
                        lower_order = orders[order_index]
                        is_least_order = True

                    lower_bound = lower_order['base']['amount'] * (1 + self.increment)

                    self.log.debug('BASE: lower_bound: {}, order_amount: {}, higher_bound: {}'.format(
                        lower_bound, order_amount * (1 + self.increment / 10), higher_bound))

                    if lower_bound > order_amount * (1 + self.increment / 10) < higher_bound:
                        # Calculate new order size and place the order to the market
                        new_base_amount = lower_bound
                        price = order['price']

                        if is_least_order:
                            # To reduce allocation rounds, increase furthest order more
                            new_orders_sum = 0
                            amount = order_amount
                            for o in orders:
                                amount = amount * (1 + self.increment)
                                new_orders_sum += amount
                            new_base_amount = order_amount * (self.base_total_balance / new_orders_sum) \
                                * (1 + self.increment * 0.75)
                            if new_base_amount < higher_bound:
                                new_base_amount = higher_bound / (1 + self.increment * 0.2)

                        # Limit buy order to available balance
                        if (asset_balance / price) < (new_base_amount - order_amount) / price:
                            new_base_amount = order_amount + asset_balance['amount']
                            self.log.debug('Limiting new buy order to avail asset balance: {}'.format(
                                new_base_amount))

                        new_order_amount = new_base_amount / price
                        self.log.debug('Cancelling buy order in increase_order_sizes(); ' 
                                       'mode: mountain, base: {}, price: {:.8f}'.format(order_amount, order['price']))
                        self.cancel(order)
                        self.market_buy(new_order_amount, price)
                        # Only one increase at a time. This prevents running more than one increaement round
                        # simultaneously
                        return
        elif self.mode == 'valley':
            pass
        elif self.mode == 'neutral':
            pass
        elif self.mode == 'buy_slope':
            pass
        elif self.mode == 'sell_slope':
            pass
        return None

    def check_partial_fill(self, order):
        """ Checks whether order was partially filled it needs to be replaced

            :param order: Order closest to the center price from buy or sell side
            :return: bool | True = Order is correct size or within the threshold
                            False = Order is not right size
        """
        if order['for_sale']['amount'] != order['base']['amount']:
            diff_abs = order['base']['amount'] - order['for_sale']['amount']
            diff_rel = diff_abs / order['base']['amount']
            if diff_rel >= self.partial_fill_threshold:
                self.log.debug('Partially filled order: {} @ {:.8f}, filled: {:.2%}'.format(
                               order['base']['amount'], order['price'], diff_rel))
                return False
        return True

    def is_order_size_correct(self, order, orders):
        """ Checks if the order is big enough. Oversized orders are allowed to enable manual manipulation

            This is old version of check_partial_fill()

            :param order: Order closest to the center price from buy or sell side
            :param orders: List of buy or sell orders
            :return: bool | True = Order is correct size or within the threshold
                            False = Order is not right size
        """
        # Calculate threshold
        order_size = order['quote']['amount']
        if self.is_sell_order(order):
            order_size = order['base']['amount']

        threshold = self.increment / 10
        upper_threshold = order_size * (1 + threshold)
        lower_threshold = order_size / (1 + threshold)

        if self.is_sell_order(order):
            lowest_sell_order = orders[0]
            highest_sell_order = orders[-1]

            # Order is the only sell order, and size must be calculated like initializing
            if lowest_sell_order == highest_sell_order:
                total_balance = self.total_balance(orders, return_asset=True)
                quote_balance = total_balance['quote'] - self.quote_fee_reserve
                highest_sell_order = self.place_highest_sell_order(quote_balance,
                                                                   place_order=False,
                                                                   market_center_price=self.initial_market_center_price)

                # Check if the old order is same size with accuracy of 0.1%
                if lower_threshold <= highest_sell_order['amount'] <= upper_threshold:
                    return True

                self.log.debug('lower_threshold <= highest_sell_order <= upper_threshold: {} <= {} <= {}'.format(
                               lower_threshold, highest_sell_order['amount'], upper_threshold))
                return False
            elif order == highest_sell_order:
                order_index = orders.index(order)
                higher_sell_order = self.place_higher_sell_order(orders[order_index - 1], place_order=False)

                if lower_threshold <= higher_sell_order['amount'] <= upper_threshold:
                    return True

                self.log.debug('lower_threshold <= higher_sell_order <= upper_threshold: {} <= {} <= {}'.format(
                               lower_threshold, higher_sell_order['amount'], upper_threshold))
                return False
            elif order == lowest_sell_order:
                order_index = orders.index(order)
                lower_sell_order = self.place_lower_sell_order(orders[order_index + 1], place_order=False)

                if lower_threshold <= lower_sell_order['amount'] <= upper_threshold:
                    return True

                self.log.debug('lower_threshold <= lower_sell_order <= upper_threshold: {} <= {} <= {}'.format(
                               lower_threshold, lower_sell_order['amount'], upper_threshold))
                return False
        elif self.is_buy_order(order):
            lowest_buy_order = orders[-1]
            highest_buy_order = orders[0]

            # Order is the only buy order, and size must be calculated like initializing
            if highest_buy_order == lowest_buy_order:
                total_balance = self.total_balance(orders, return_asset=True)
                base_balance = total_balance['base'] - self.base_fee_reserve
                lowest_buy_order = self.place_lowest_buy_order(base_balance,
                                                               place_order=False,
                                                               market_center_price=self.initial_market_center_price)

                # Check if the old order is same size with accuracy of 0.1%
                if lower_threshold <= lowest_buy_order['amount'] <= upper_threshold:
                    return True

                self.log.debug('lower_threshold <= lowest_buy_order <= upper_threshold: {} <= {} <= {}'.format(
                               lower_threshold, lowest_buy_order['amount'], upper_threshold))
                return False
            elif order == lowest_buy_order:
                order_index = orders.index(order)
                lower_buy_order = self.place_lower_buy_order(orders[order_index - 1], place_order=False)

                if lower_threshold <= lower_buy_order['amount'] <= upper_threshold:
                    return True

                self.log.debug('lower_threshold <= lower_buy_order <= upper_threshold: {} <= {} <= {}'.format(
                               lower_threshold, lower_buy_order['amount'], upper_threshold))
                return False
            elif order == highest_buy_order:
                order_index = orders.index(order)
                higher_buy_order = self.place_higher_buy_order(orders[order_index + 1], place_order=False)

                if lower_threshold <= higher_buy_order['amount'] <= upper_threshold:
                    return True

                self.log.debug('lower_threshold <= higher_buy_order <= upper_threshold: {} <= {} <= {}'.format(
                               lower_threshold, higher_buy_order['amount'], upper_threshold))
                return False

        return False

    def place_higher_buy_order(self, order, place_order=True, allow_partial=False, base_limit=None, limit=None):
        """ Place higher buy order
            Mode: MOUNTAIN
            amount (QUOTE) = lower_buy_order_amount
            price (BASE) = lower_buy_order_price * (1 + increment)

            :param order: Previously highest buy order
            :param bool | place_order: True = Places order to the market, False = returns amount and price
            :param bool | allow_partial: True = Allow to downsize order whether there is not enough balance
            :param float | base_limit: order should be limited in size by this BASE amount
            :param float | limit: order should be limited in size by this QUOTE amount
        """
        if base_limit and limit:
            self.log.error('Only base_limit or limit should be specified')
            self.disabled = True
            return None

        amount = order['quote']['amount']
        price = order['price'] * (1 + self.increment)
        # How many BASE we need to buy QUOTE `amount`
        base_amount = amount * price

        if not self.is_instant_fill_enabled and price > float(self.ticker['lowestAsk']):
            self.log.info('Refusing to place an order which crosses lowestAsk')
            return None

        if base_limit and base_limit < base_amount:
            base_amount = base_limit
            amount = base_limit / price
        elif limit and limit < amount:
            # Limit order amount only when it is lower than amount
            base_amount = limit * price
            amount = limit

        if base_amount > self.base_balance['amount']:
            if place_order and not allow_partial:
                self.log.debug('Not enough balance to place_higher_buy_order; need/avail: {}/{}'
                               .format(base_amount, self.base_balance['amount']))
                place_order = False
            elif allow_partial:
                self.log.debug('Limiting order amount to available balance: {}'.format(self.base_balance['amount']))
                amount = self.base_balance['amount'] / price

        if place_order:
            self.market_buy(amount, price)

        return {"amount": amount, "price": price}

    def place_higher_sell_order(self, order, place_order=True, allow_partial=False):
        """ Place higher sell order
            Mode: MOUNTAIN
            amount (BASE) = higher_sell_order_amount / (1 + increment)
            price (BASE) = higher_sell_order_price * (1 + increment)

            :param order: highest_sell_order
            :param bool | place_order: True = Places order to the market, False = returns amount and price
            :param bool | allow_partial: True = Allow to downsize order whether there is not enough balance
        """
        amount = order['base']['amount'] / (1 + self.increment)
        price = (order['price'] ** -1) * (1 + self.increment)
        if amount > self.quote_balance['amount']:
            if place_order and not allow_partial:
                self.log.debug('Not enough balance to place_higher_sell_order; need/avail: {}/{}'
                               .format(amount, self.quote_balance['amount']))
                place_order = False
            elif allow_partial:
                self.log.debug('Limiting order amount to available balance: {}'.format(self.quote_balance['amount']))
                amount = self.quote_balance['amount']

        if place_order:
            self.market_sell(amount, price)

        return {"amount": amount, "price": price}

    def place_lower_buy_order(self, order, place_order=True, allow_partial=False):
        """ Place lower buy order
            Mode: MOUNTAIN
            amount (QUOTE) = lowest_buy_order_amount
            price (BASE) = Order's base price / (1 + increment)

            :param order: Previously lowest buy order
            :param bool | place_order: True = Places order to the market, False = returns amount and price
            :param bool | allow_partial: True = Allow to downsize order whether there is not enough balance
        """
        amount = order['quote']['amount']
        price = order['price'] / (1 + self.increment)
        # How many BASE we need to buy QUOTE `amount`
        base_amount = amount * price

        if base_amount > self.base_balance['amount']:
            if place_order and not allow_partial:
                self.log.debug('Not enough balance to place_lower_buy_order; need/avail: {}/{}'
                               .format(base_amount, self.base_balance['amount']))
                place_order = False
            elif allow_partial:
                self.log.debug('Limiting order amount to available balance: {}'.format(self.base_balance['amount']))
                amount = self.base_balance['amount'] / price

        if place_order:
            self.market_buy(amount, price)
        else:
            return {"amount": amount, "price": price}

    def place_lower_sell_order(self, order, place_order=True, allow_partial=False, base_limit=None, limit=None):
        """ Place lower sell order
            Mode: MOUNTAIN
            amount (BASE) = higher_sell_order_amount * (1 + increment)
            price (BASE) = higher_sell_order_price / (1 + increment)

            :param order: Previously higher sell order
            :param bool | place_order: True = Places order to the market, False = returns amount and price
            :param bool | allow_partial: True = Allow to downsize order whether there is not enough balance
            :param float | base_limit: order should be limited in size by this BASE amount
            :param float | limit: order should be limited in size by this QUOTE amount
        """
        if base_limit and limit:
            self.log.error('Only base_limit or limit should be specified')
            self.disabled = True
            return None

        amount = order['base']['amount'] * (1 + self.increment)
        price = (order['price'] ** -1) / (1 + self.increment)

        if not self.is_instant_fill_enabled and price < float(self.ticker['highestBid']):
            self.log.info('Refusing to place an order which crosses highestBid')
            return None

        if base_limit:
            amount = base_limit / price
        elif limit and limit < amount:
            amount = limit

        if amount > self.quote_balance['amount']:
            if place_order and not allow_partial:
                self.log.debug('Not enough balance to place_lower_sell_order; need/avail: {}/{}'
                               .format(amount, self.quote_balance['amount']))
                place_order = False
            elif allow_partial:
                self.log.debug('Limiting order amount to available balance: {}'.format(self.quote_balance['amount']))
                amount = self.quote_balance['amount']

        if place_order:
            self.market_sell(amount, price)

        return {"amount": amount, "price": price}

    def place_highest_sell_order(self, quote_balance, place_order=True, market_center_price=None):
        """ Places sell order furthest to the market center price
            Mode: MOUNTAIN
            :param Amount | quote_balance: Available QUOTE asset balance
            :param bool | place_order: True = Places order to the market, False = returns amount and price
            :param float | market_center_price: Optional market center price, used to to check order
            :return dict | order: Returns highest sell order
        """
        if not market_center_price:
            market_center_price = self.market_center_price

        price = market_center_price * math.sqrt(1 + self.target_spread)
        previous_price = price
        orders_sum = 0

        amount = quote_balance['amount'] * self.increment
        previous_amount = amount

        while price <= self.upper_bound:
            orders_sum += previous_amount
            previous_price = price
            previous_amount = amount

            price = price * (1 + self.increment)
            amount = amount / (1 + self.increment)

        precision = self.market['quote']['precision']
        price = previous_price
        amount_quote = previous_amount * (self.quote_total_balance / orders_sum) * (1 + self.increment * 0.75)
        amount_quote = int(float(amount_quote) * 10 ** precision) / (10 ** precision)

        if place_order:
            self.market_sell(amount_quote, price)
        else:
            return {"amount": amount_quote, "price": price}

    def place_lowest_buy_order(self, base_balance, place_order=True, market_center_price=None):
        """ Places buy order furthest to the market center price

            Turn BASE amount into QUOTE amount (we will buy this QUOTE amount).
            QUOTE = BASE / price

            Mode: MOUNTAIN
            :param Amount | base_balance: Available BASE asset balance
            :param bool | place_order: True = Places order to the market, False = returns amount and price
            :param float | market_center_price: Optional market center price, used to to check order
            :return dict | order: Returns lowest buy order
        """
        if not market_center_price:
            market_center_price = self.market_center_price

        price = market_center_price / math.sqrt(1 + self.target_spread)
        previous_price = price
        orders_sum = 0

        amount = base_balance['amount'] * self.increment
        previous_amount = amount

        while price >= self.lower_bound:
            orders_sum += previous_amount
            previous_price = price
            previous_amount = amount

            price = price / (1 + self.increment)
            amount = amount / (1 + self.increment)

        precision = self.market['quote']['precision']
        amount_base = previous_amount * (self.base_total_balance / orders_sum) * (1 + self.increment * 0.75)
        price = previous_price
        amount_quote = amount_base / price
        amount_quote = int(float(amount_quote) * 10 ** precision) / (10 ** precision)

        if place_order:
            self.market_buy(amount_quote, price)
        else:
            return {"amount": amount_quote, "price": price}

    def error(self, *args, **kwargs):
        self.disabled = True

    def pause(self):
        """ Override pause() in BaseStrategy """
        pass

    def tick(self, d):
        """ Ticks come in on every block """
        if not (self.counter or 0) % 3:
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
