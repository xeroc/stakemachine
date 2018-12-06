import sys
import math
import traceback
import bitsharesapi.exceptions
from datetime import datetime, timedelta
from functools import reduce
from bitshares.dex import Dex
from bitshares.amount import Amount

from dexbot.strategies.base import StrategyBase, ConfigElement, DetailElement
from dexbot.qt_queue.idle_queue import idle_add


class Strategy(StrategyBase):
    """ Staggered Orders strategy """

    @classmethod
    def configure(cls, return_base_config=True):
        """ Modes description:

            Mountain:
            - Buy orders same QUOTE
            - Sell orders same BASE

            Neutral:
            - Buy orders lower_order_base * sqrt(1 + increment)
            - Sell orders higher_order_quote * sqrt(1 + increment)

            Valley:
            - Buy orders same BASE
            - Sell orders same QUOTE

            Buy slope:
            - All orders same BASE (profit comes in QUOTE)

            Sell slope:
            - All orders same QUOTE (profit made in BASE)
        """
        modes = [
            ('mountain', 'Mountain'),
            ('neutral', 'Neutral'),
            ('valley', 'Valley'),
            ('buy_slope', 'Buy Slope'),
            ('sell_slope', 'Sell Slope')
        ]

        return StrategyBase.configure(return_base_config) + [
            ConfigElement(
                'mode', 'choice', 'neutral', 'Strategy mode',
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
                'In an immature market, give a center price manually to begin with. BASE/QUOTE',
                (0, 1000000000, 8, '')),
            ConfigElement(
                'lower_bound', 'float', 1, 'Lower bound',
                'The bottom price in the range',
                (0, 1000000000, 8, '')),
            ConfigElement(
                'upper_bound', 'float', 1000000, 'Upper bound',
                'The top price in the range',
                (0, 1000000000, 8, '')),
            ConfigElement(
                'instant_fill', 'bool', True, 'Allow instant fill',
                'Allow to execute orders by market', None),
            ConfigElement(
                'operational_depth', 'int', 10, 'Operational depth',
                'Order depth to maintain on books', (2, None, None))
        ]

    @classmethod
    def configure_details(cls, include_default_tabs=True):
        return StrategyBase.configure_details(include_default_tabs) + []

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
        # This fill threshold prevents too often orders replacements draining fee_asset
        self.partial_fill_threshold = 0.15
        self.is_instant_fill_enabled = self.worker.get('instant_fill', True)
        self.is_center_price_dynamic = self.worker['center_price_dynamic']
        self.operational_depth = self.worker.get('operational_depth', 6)

        if self.is_center_price_dynamic:
            self.center_price = None
        else:
            self.center_price = self.worker['center_price']

        if self.target_spread < self.increment:
            self.log.error('Spread is more than increment, refusing to work because worker will make losses')
            self.disabled = True

        if self.operational_depth < 2:
            self.log.error('Operational depth should be at least 2 orders')
            self.disabled = True

        # Strategy variables
        # Assume we are in bootstrap mode by default. This prevents weird things when bootstrap was interrupted
        self.bootstrapping = True
        self.market_center_price = None
        self.buy_orders = []
        self.sell_orders = []
        self.real_buy_orders = []
        self.real_sell_orders = []
        self.virtual_orders = []
        self.virtual_buy_orders = []
        self.virtual_sell_orders = []
        self.virtual_orders_restored = False
        self.actual_spread = self.target_spread + 1
        self.quote_total_balance = 0
        self.base_total_balance = 0
        self.quote_balance = None
        self.base_balance = None
        self.quote_asset_threshold = 0
        self.base_asset_threshold = 0
        self.min_increase_factor = 1.15
        # Initial balance history elements should not be equal to avoid immediate bootstrap turn off
        self.quote_balance_history = [1, 2, 3]
        self.base_balance_history = [1, 2, 3]
        self.cached_orders = None

        # Dex instance used to get different fees for the market
        self.dex = Dex(self.bitshares)

        # Order expiration time
        self.expiration = 60 * 60 * 24 * 365 * 5
        self.start = datetime.now()
        self.last_check = datetime.now()

        # We do not waiting for order ids to be able to bundle operations
        self.returnOrderId = None

        # Minimal check interval is needed to prevent event queue accumulation
        self.min_check_interval = 1
        self.max_check_interval = 120
        self.current_check_interval = self.min_check_interval

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
        if delta < timedelta(seconds=self.current_check_interval):
            return

        # Get all user's orders on current market
        self.refresh_orders()

        # Check if market center price is calculated
        self.market_center_price = self.get_market_center_price(suppress_errors=True)

        # Set center price to manual value if needed. Manual center price works only when there are no orders
        if self.center_price and not (self.buy_orders or self.sell_orders):
            self.log.debug('Using manual center price because of no sell or buy orders')
            self.market_center_price = self.center_price

        # Still not have market_center_price? Empty market, don't continue
        if not self.market_center_price:
            self.log.warning('Cannot calculate center price on empty market, please set is manually')
            return

        # Calculate balances, and use orders from previous call of self.refresh_orders() to reduce API calls
        self.refresh_balances(use_cached_orders=True)

        # Calculate asset thresholds
        self.quote_asset_threshold = self.quote_total_balance / 20000
        self.base_asset_threshold = self.base_total_balance / 20000

        # Check market's price boundaries
        if self.market_center_price > self.upper_bound:
            self.log.debug('Overriding upper bound by market center price: {} -> {:.8f}'
                           .format(self.upper_bound, self.market_center_price))
            self.upper_bound = self.market_center_price
        elif self.market_center_price < self.lower_bound:
            self.log.debug('Overriding lower bound by market center price: {} -> {:.8f}'
                           .format(self.lower_bound, self.market_center_price))
            self.lower_bound = self.market_center_price

        # Remove orders that exceed boundaries
        success = self.remove_outside_orders(self.sell_orders, self.buy_orders)
        if not success:
            # Return back to beginning
            self.log_maintenance_time()
            return

        # Restore virtual orders on startup if needed
        if not self.virtual_orders_restored:
            self.restore_virtual_orders()

            if self.virtual_orders_restored:
                self.log.info('Virtual orders restored')
                self.log_maintenance_time()
                return

        # Replace excessive real orders with virtual ones, buy side
        if (self.real_buy_orders and len(self.real_buy_orders) > self.operational_depth + 5 and
                self.real_buy_orders[-1]['base']['amount'] == self.real_buy_orders[-2]['base']['amount']):
            # Note: replace should happen only if next order is same-sized. Otherwise it will break proper allocation
            self.replace_real_order_with_virtual(self.real_buy_orders[-1])

        # Replace excessive real orders with virtual ones, sell side
        if (self.real_sell_orders and len(self.real_sell_orders) > self.operational_depth + 5 and
                self.real_sell_orders[-1]['base']['amount'] == self.real_sell_orders[-2]['base']['amount']):
            self.replace_real_order_with_virtual(self.real_sell_orders[-1])

        # Check for operational depth, buy side
        if (self.virtual_buy_orders and
                len(self.real_buy_orders) < self.operational_depth and
                not self.bootstrapping):
            """
                Note: if boostrap is on and there is nothing to allocate, this check would not work until some orders
                will be filled. This means that changing `operational_depth` config param will not work immediately.

                We need to wait until bootstrap is off because during initial orders placement this would start to place
                real orders without waiting until all range will be covered.
            """
            self.replace_virtual_order_with_real(self.virtual_buy_orders[0])
            self.log_maintenance_time()
            return

        # Check for operational depth, sell side
        if (self.virtual_sell_orders and
                len(self.real_sell_orders) < self.operational_depth and
                not self.bootstrapping):
            self.replace_virtual_order_with_real(self.virtual_sell_orders[0])
            self.log_maintenance_time()
            return

        # Prepare to bundle operations into single transaction
        self.bitshares.bundle = True

        # BASE asset check
        if self.base_balance > self.base_asset_threshold:
            # Allocate available BASE funds
            base_allocated = False
            self.allocate_asset('base', self.base_balance)
        else:
            base_allocated = True

        # QUOTE asset check
        if self.quote_balance > self.quote_asset_threshold:
            # Allocate available QUOTE funds
            quote_allocated = False
            self.allocate_asset('quote', self.quote_balance)
        else:
            quote_allocated = True

        # Send pending operations
        if not self.bitshares.txbuffer.is_empty():
            try:
                self.execute()
            except bitsharesapi.exceptions.RPCError:
                """ Handle exception without stopping the worker. The goal is to handle race condition when partially
                    filled order was further filled before we actually replaced them.
                """
                self.log.warning('Got exception during broadcasting trx:')
                traceback.print_exc(file=sys.stdout)
                self.log.warning('Ignoring that exception and continue')
                return
        self.bitshares.bundle = False

        # Maintain the history of free balances after maintenance runs.
        # Save exactly key values instead of full key because it may be modified later on.
        self.refresh_balances(total_balances=False)
        self.base_balance_history.append(self.base_balance['amount'])
        self.quote_balance_history.append(self.quote_balance['amount'])
        if len(self.base_balance_history) > 3:
            del self.base_balance_history[0]
            del self.quote_balance_history[0]

        # Greatly increase check interval to lower CPU load whether there is no funds to allocate or we cannot
        # allocate funds for some reason
        if (self.current_check_interval == self.min_check_interval and
                self.base_balance_history[1] == self.base_balance_history[2] and
                self.quote_balance_history[1] == self.quote_balance_history[2]):
            # Balance didn't changed, so we can reduce maintenance frequency
            self.log.debug('Raising check interval up to {} seconds to reduce CPU usage'.format(
                           self.max_check_interval))
            self.current_check_interval = self.max_check_interval
        elif (self.current_check_interval == self.max_check_interval and
              (self.base_balance_history[1] != self.base_balance_history[2] or
               self.quote_balance_history[1] != self.quote_balance_history[2])):
            # Balance changed, increase maintenance frequency to allocate more quickly
            self.log.debug('Reducing check interval to {} seconds because of changed '
                           'balances'.format(self.min_check_interval))
            self.current_check_interval = self.min_check_interval

        # Do not continue whether balances are changing or bootstrap is on
        if (self.bootstrapping or
                self.base_balance_history[0] != self.base_balance_history[2] or
                self.quote_balance_history[0] != self.quote_balance_history[2]):
            self.last_check = datetime.now()
            self.log_maintenance_time()
            return

        # There are no funds and current orders aren't close enough, try to fix the situation by shifting orders.
        # This is a fallback logic.

        # Get highest buy and lowest sell prices from orders
        highest_buy_price = 0
        lowest_sell_price = 0

        if self.buy_orders:
            highest_buy_price = self.buy_orders[0].get('price')

        if self.sell_orders:
            lowest_sell_price = self.sell_orders[0].get('price')
            # Invert the sell price to BASE so it can be used in comparison
            lowest_sell_price = lowest_sell_price ** -1

        if highest_buy_price and lowest_sell_price:
            self.actual_spread = (lowest_sell_price / highest_buy_price) - 1
            if self.actual_spread < self.target_spread + self.increment:
                # Target spread is reached, no need to cancel anything
                self.last_check = datetime.now()
                self.log_maintenance_time()
                return

        # What amount of quote may be obtained if buy using avail base balance
        can_obtain_quote = self.base_balance['amount'] * self.market_center_price
        side_to_cancel = None

        """ The logic is following: compare on which side we have bigger free balance, then cancel furthest order on
            that side to be able to place closer order. This is for situations when amount obtained from previous trade
            is not enough to place closer order.
        """
        if can_obtain_quote > self.quote_balance['amount'] and not base_allocated:
            side_to_cancel = 'buy'
        elif self.quote_balance['amount'] > can_obtain_quote and not quote_allocated:
            side_to_cancel = 'sell'

        if not side_to_cancel:
            """ Balance-based cancel logic didn't give a result, so use logic based on distance to market center
            """
            # Measure which price is closer to the center
            buy_distance = self.market_center_price - highest_buy_price
            sell_distance = lowest_sell_price - self.market_center_price

            if buy_distance > sell_distance:
                side_to_cancel = 'buy'
            else:
                side_to_cancel = 'sell'

        if side_to_cancel == 'buy':
            self.log.info('Free balances are not changing, bootstrap is off and target spread is not reached. '
                          'Cancelling lowest buy order as a fallback')
            self.cancel_orders_wrapper(self.buy_orders[-1])
        elif side_to_cancel == 'sell':
            self.log.info('Free balances are not changing, bootstrap is off and target spread is not reached. '
                          'Cancelling highest sell order as a fallback')
            self.cancel_orders_wrapper(self.sell_orders[-1])
        else:
            self.log.info('Target spread is not reached but cannot determine what furthest order to cancel')

        self.last_check = datetime.now()
        self.log_maintenance_time()

    def log_maintenance_time(self):
        """ Measure time from self.start and print a log message
        """
        delta = datetime.now() - self.start
        self.log.debug('Maintenance execution took: {:.2f} seconds'.format(delta.total_seconds()))

    def refresh_balances(self, total_balances=True, use_cached_orders=False):
        """ This function is used to refresh account balances
            :param bool | total_balances: refresh total balance or skip it
            :param bool | use_cached_orders: when calculating orders balance, use cached orders from self.cached_orders
        """
        virtual_orders_base_balance = 0
        virtual_orders_quote_balance = 0

        # Get current account balances
        account_balances = self.count_asset(order_ids=[], return_asset=True)

        self.base_balance = account_balances['base']
        self.quote_balance = account_balances['quote']

        # Reserve fees for N orders
        reserve_num_orders = 200
        fee_reserve = reserve_num_orders * self.get_order_creation_fee(self.fee_asset)

        # Finally, reserve only required asset
        if self.fee_asset['id'] == self.market['base']['id']:
            self.base_balance['amount'] = self.base_balance['amount'] - fee_reserve
        elif self.fee_asset['id'] == self.market['quote']['id']:
            self.quote_balance['amount'] = self.quote_balance['amount'] - fee_reserve

        # Exclude balances allocated into virtual orders
        if self.virtual_orders:
            buy_orders = self.filter_buy_orders(self.virtual_orders)
            sell_orders = self.filter_sell_orders(self.virtual_orders, invert=False)
            virtual_orders_base_balance = reduce((lambda x, order: x + order['base']['amount']), buy_orders, 0)
            virtual_orders_quote_balance = reduce((lambda x, order: x + order['base']['amount']), sell_orders, 0)
            self.base_balance['amount'] -= virtual_orders_base_balance
            self.quote_balance['amount'] -= virtual_orders_quote_balance

        if not total_balances:
            # Caller doesn't interesting in balances of real orders
            return

        # Balance per asset from orders
        if use_cached_orders and self.cached_orders:
            orders = self.cached_orders
        else:
            orders = self.get_own_orders
        order_ids = [order['id'] for order in orders]
        orders_balance = self.get_allocated_assets(order_ids)

        # Total balance per asset (orders balance and available balance)
        self.quote_total_balance = orders_balance['quote'] + self.quote_balance['amount'] + virtual_orders_quote_balance
        self.base_total_balance = orders_balance['base'] + self.base_balance['amount'] + virtual_orders_base_balance

    def refresh_orders(self):
        """ Updates buy and sell orders
        """
        orders = self.get_own_orders
        self.cached_orders = orders

        # Sort virtual orders
        self.virtual_buy_orders = self.filter_buy_orders(self.virtual_orders, sort='DESC')
        self.virtual_sell_orders = self.filter_sell_orders(self.virtual_orders, sort='DESC', invert=False)

        # Sort real orders
        self.real_buy_orders = self.filter_buy_orders(orders, sort='DESC')
        self.real_sell_orders = self.filter_sell_orders(orders, sort='DESC', invert=False)

        # Concatenate orders and virtual_orders
        orders = orders + self.virtual_orders

        # Sort orders so that order with index 0 is closest to the center price and -1 is furthers
        self.buy_orders = self.filter_buy_orders(orders, sort='DESC')
        self.sell_orders = self.filter_sell_orders(orders, sort='DESC', invert=False)

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
                self.log.info('Cancelling sell order outside range: {:.8f}'.format(order_price))
                orders_to_cancel.append(order)

        # Remove buy orders that exceed boundaries
        for order in buy_orders:
            order_price = order['price']
            if order_price < self.lower_bound:
                self.log.info('Cancelling buy order outside range: {:.8f}'.format(order_price))
                orders_to_cancel.append(order)

        if orders_to_cancel:
            # We are trying to cancel all orders in one try
            success = self.cancel_orders_wrapper(orders_to_cancel, batch_only=True)
            # Refresh orders to prevent orders outside boundaries being in the future comparisons
            self.refresh_orders()
            # Batch cancel failed, repeat cancelling only one order
            if success:
                return True
            else:
                self.log.debug('Batch cancel failed, failing back to cancelling single order')
                self.cancel_orders_wrapper(orders_to_cancel[0])
                # To avoid GUI hanging cancel only one order and let switch to another worker
                return False

        return True

    def restore_virtual_orders(self):
        """ Create virtual further orders in batch manner. This helps to place further orders quickly on startup.
        """
        if self.buy_orders:
            furthest_order = self.real_buy_orders[-1]
            while furthest_order['price'] > self.lower_bound * (1 + self.increment):
                furthest_order = self.place_further_order('base', furthest_order, virtual=True)
                if not isinstance(furthest_order, VirtualOrder):
                    # Failed to place order
                    break

        if self.sell_orders:
            furthest_order = self.real_sell_orders[-1]
            while furthest_order['price'] ** -1 < self.upper_bound / (1 + self.increment):
                furthest_order = self.place_further_order('quote', furthest_order, virtual=True)
                if not isinstance(furthest_order, VirtualOrder):
                    # Failed to place order
                    break

        # Set "restored" flag anyway to not break initial bootstrap
        self.virtual_orders_restored = True

    def replace_real_order_with_virtual(self, order):
        """ Replace real limit order with virtual order

            :param Order | order: market order to replace
            :return bool | True = order replace success
                           False = order replace failed

            Logic:
            1. Cancel real order
            2. Wait until transaction included in head block
            3. Place virtual order
        """
        success = self.cancel_orders(order)
        if success and order['base']['symbol'] == self.market['base']['symbol']:
            quote_amount = order['quote']['amount']
            price = order['price']
            self.log.info('Replacing real buy order with virtual')
            self.place_virtual_buy_order(quote_amount, price)
        elif success and order['base']['symbol'] == self.market['quote']['symbol']:
            quote_amount = order['base']['amount']
            price = order['price'] ** -1
            self.log.info('Replacing real sell order with virtual')
            self.place_virtual_sell_order(quote_amount, price)
        else:
            return False

    def replace_virtual_order_with_real(self, order):
        """ Replace virtual order with real one

            :param Order | order: market order to replace
            :return bool | True = order replace success
                           False = order replace failed

            Logic:
            1. Place real order instead of virtual
            2. Wait until transaction included in head block
            3. Remove existing virtual order
        """
        if order['base']['symbol'] == self.market['base']['symbol']:
            quote_amount = order['quote']['amount']
            price = order['price']
            self.log.info('Replacing virtual buy order with real order')
            new_order = self.place_market_buy_order(quote_amount, price, returnOrderId=True)
        else:
            quote_amount = order['base']['amount']
            price = order['price'] ** -1
            self.log.info('Replacing virtual sell order with real order')
            new_order = self.place_market_sell_order(quote_amount, price, returnOrderId=True)

        if new_order:
            # Cancel virtual order
            self.cancel_orders_wrapper(order)
            return True
        return False

    def allocate_asset(self, asset, asset_balance):
        """ Allocates available asset balance as buy or sell orders.

            :param str | asset: 'base' or 'quote'
            :param Amount | asset_balance: Amount of the asset available to use
        """
        self.log.debug('Need to allocate {}: {}'.format(asset, asset_balance))
        closest_opposite_order = None
        closest_opposite_price = 0
        opposite_asset_limit = None
        opposite_orders = []
        order_type = ''
        own_asset_limit = None
        own_orders = []
        own_threshold = 0
        own_symbol = ''
        own_precision = 0
        opposite_symbol = ''
        increase_finished = False

        if asset == 'base':
            order_type = 'buy'
            own_symbol = self.base_balance['symbol']
            opposite_symbol = self.quote_balance['symbol']
            own_orders = self.buy_orders
            opposite_orders = self.sell_orders
            own_threshold = self.base_asset_threshold
            own_precision = self.market['base']['precision']
        elif asset == 'quote':
            order_type = 'sell'
            own_symbol = self.quote_balance['symbol']
            opposite_symbol = self.base_balance['symbol']
            own_orders = self.sell_orders
            opposite_orders = self.buy_orders
            own_threshold = self.quote_asset_threshold
            own_precision = self.market['quote']['precision']

        if own_orders:
            # Get currently the furthest and closest orders
            furthest_own_order = own_orders[-1]
            closest_own_order = own_orders[0]
            furthest_own_order_price = furthest_own_order['price']
            if asset == 'quote':
                furthest_own_order_price = furthest_own_order_price ** -1

            # Calculate actual spread
            if opposite_orders:
                closest_opposite_order = opposite_orders[0]
                closest_opposite_price = closest_opposite_order['price'] ** -1
            elif asset == 'base':
                # For one-sided start, calculate closest_opposite_price empirically
                closest_opposite_price = self.market_center_price * (1 + self.target_spread / 2)
            elif asset == 'quote':
                closest_opposite_price = (self.market_center_price / (1 + self.target_spread / 2)) ** -1

            closest_own_price = closest_own_order['price']
            self.actual_spread = (closest_opposite_price / closest_own_price) - 1

            if self.actual_spread >= self.target_spread + self.increment:
                if not self.check_partial_fill(closest_own_order, fill_threshold=0):
                    # Replace closest order if it was partially filled for any %
                    """ Note on partial filled orders handling: if target spread is not reached and we need to place
                        closer order, we need to make sure current closest order is 100% unfilled. When target spread is
                        reached, we are replacing order only if it was filled no less than `self.fill_threshold`. This
                        helps to avoid too often replacements.
                    """
                    self.replace_partially_filled_order(closest_own_order)
                    return

                if (self.bootstrapping and
                        self.base_balance_history[2] == self.base_balance_history[0] and
                        self.quote_balance_history[2] == self.quote_balance_history[0] and
                        opposite_orders):
                    # Turn off bootstrap mode whether we're didn't allocated assets during previous 3 maintenance
                    self.log.debug('Turning bootstrapping off: actual_spread > target_spread, we have free '
                                   'balances and cannot allocate them normally 3 times in a row')
                    self.bootstrapping = False

                """ Note: because we're using operations batching, there is possible a situation when we will have
                    both free balances and `self.actual_spread >= self.target_spread + self.increment`. In such case
                    there will be TWO orders placed, one buy and one sell despite only one would be enough to reach
                    target spread. Sure, we can add a workaround for that by overriding `closest_opposite_price` for
                    second call of allocate_asset(). We are not doing this because we're not doing assumption on
                    which side order (buy or sell) should be placed first. So, when placing two closer orders from
                    both sides, spread will be no less than `target_spread - increment`, thus not making any loss.
                """

                # Place order closer to the center price
                self.log.debug('Placing closer {} order; actual spread: {:.4%}, target + increment: {:.4%}'
                               .format(order_type, self.actual_spread, self.target_spread + self.increment))
                if self.bootstrapping:
                    self.place_closer_order(asset, closest_own_order)
                elif opposite_orders:
                    # Place order limited by size of the opposite-side order
                    if self.mode == 'mountain':
                        opposite_asset_limit = closest_opposite_order['base']['amount'] * (1 + self.increment)
                        own_asset_limit = None
                        self.log.debug('Limiting {} order by opposite order: {} {}'.format(
                                       order_type, opposite_asset_limit, opposite_symbol))
                    elif ((self.mode == 'buy_slope' and asset == 'base') or
                            (self.mode == 'sell_slope' and asset == 'quote')):
                        opposite_asset_limit = None
                        own_asset_limit = closest_opposite_order['quote']['amount']
                        self.log.debug('Limiting {} order by opposite order: {} {}'
                                       .format(order_type, own_asset_limit, own_symbol))
                    elif self.mode == 'neutral':
                        opposite_asset_limit = closest_opposite_order['base']['amount'] * \
                                               math.sqrt(1 + self.increment)
                        own_asset_limit = None
                        self.log.debug('Limiting {} order by opposite order: {} {}'.format(
                                       order_type, opposite_asset_limit, opposite_symbol))
                    elif (self.mode == 'valley' or
                          (self.mode == 'buy_slope' and asset == 'quote') or
                          (self.mode == 'sell_slope' and asset == 'base')):
                            opposite_asset_limit = closest_opposite_order['base']['amount']
                            own_asset_limit = None
                            self.log.debug('Limiting {} order by opposite order: {} {}'.format(
                                           order_type, opposite_asset_limit, opposite_symbol))
                    self.place_closer_order(asset, closest_own_order, own_asset_limit=own_asset_limit,
                                            opposite_asset_limit=opposite_asset_limit, allow_partial=False)
                else:
                    # Opposite side probably reached range bound, allow to place partial order
                    self.place_closer_order(asset, closest_own_order, allow_partial=True)
            elif not opposite_orders:
                # Do not try to do anything than placing closer order whether there is no opposite orders
                return
            else:
                # Target spread is reached, let's allocate remaining funds
                if not self.check_partial_fill(closest_own_order, fill_threshold=0):
                    """ Detect partially filled order on the own side and reserve funds to replace order in case
                        opposite oreder will be fully filled.
                    """
                    funds_to_reserve = closest_own_order['base']['amount']
                    self.log.debug('Partially filled order on own side, reserving funds to replace: '
                                   '{:.{prec}f} {}'.format(funds_to_reserve, own_symbol, prec=own_precision))
                    asset_balance -= funds_to_reserve

                if not self.check_partial_fill(closest_opposite_order, fill_threshold=0):
                    """ Detect partially filled order on the opposite side and reserve appropriate amount to place
                        closer order. We adding some additional reserve to be able to place next order whether
                        new allocation round will be started, this is mostly for valley-like modes.
                    """
                    funds_to_reserve = 0
                    additional_reserve = max(1 + self.increment, self.min_increase_factor) * 1.05
                    closer_own_order = self.place_closer_order(asset, closest_own_order, place_order=False)

                    if asset == 'base':
                        funds_to_reserve = closer_own_order['amount'] * closer_own_order['price'] * additional_reserve
                    elif asset == 'quote':
                        funds_to_reserve = closer_own_order['amount'] * additional_reserve
                    self.log.debug('Partially filled order on opposite side, reserving funds for next {} order: '
                                   '{:.{prec}f} {}'.format(order_type, funds_to_reserve, own_symbol,
                                                           prec=own_precision))
                    asset_balance -= funds_to_reserve

                if asset_balance > own_threshold:
                    # Allocate excess funds
                    if ((asset == 'base' and furthest_own_order_price /
                         (1 + self.increment) < self.lower_bound) or
                            (asset == 'quote' and furthest_own_order_price *
                             (1 + self.increment) > self.upper_bound)):
                        # Lower/upper bound has been reached and now will start allocating rest of the balance.
                        self.bootstrapping = False
                        self.log.debug('Increasing sizes of {} orders'.format(order_type))
                        increase_finished = self.increase_order_sizes(asset, asset_balance, own_orders)
                    else:
                        # Range bound is not reached, we need to add additional orders at the extremes
                        self.bootstrapping = False
                        self.log.debug('Placing further order than current furthest {} order'.format(order_type))
                        self.place_further_order(asset, furthest_own_order, allow_partial=True)
                else:
                    increase_finished = True

            if (increase_finished and not self.check_partial_fill(closest_own_order)
                    and not self.check_partial_fill(closest_opposite_order, fill_threshold=0)):
                """ Replace partially filled closest orders only when allocation of excess funds was finished. This
                    would prevent an abuse case when we are operating inactive market. An attacker can massively dump
                    the price and then he can buy back the asset cheaper. Similar case may happen on the "normal" market
                    on significant price drops or spikes.

                    The logic how it works is following:
                    1. If we have partially filled closest orders, reserve fuds to replace them later
                    2. If we have excess funds, allocate them by increasing order sizes or expand bounds if needed
                    3. When increase is finished, replace partially filled closest orders

                    Thus we are don't need to precisely count how much was filled on closest orders.
                """
                # Refresh balances to make "reserved" funds available
                self.refresh_balances(use_cached_orders=True)
                self.replace_partially_filled_order(closest_own_order)
        else:
            # Place first buy order as close to the lower bound as possible
            self.bootstrapping = True
            order = None
            self.log.debug('Placing first {} order'.format(order_type))
            if asset == 'base':
                order = self.place_lowest_buy_order(asset_balance)
            elif asset == 'quote':
                order = self.place_highest_sell_order(asset_balance)

            # Place all virtual orders at once
            while isinstance(order, VirtualOrder):
                order = self.place_closer_order(asset, order)

        # Get latest orders only when we are not bundling operations
        if self.returnOrderId:
            self.refresh_orders()

    def increase_order_sizes(self, asset, asset_balance, orders):
        """ Checks which order should be increased in size and replaces it
            with a maximum size order, according to global limits. Logic
            depends on mode in question.

            Mountain:
            Maximize order size as close to center as possible. When all orders are max, the new increase round is
            started from the furthest order.

            Neutral:
            Try to flatten everything by increasing order sizes to neutral. When everything is correct, maximize
            closest orders and then increase other orders to match that.

            Valley:
            Maximize order sizes as far as possible from center first. When all orders are max, the new increase round
            is started from the closest-to-center order.

            Buy slope:
            Maximize order size as low as possible. Buy orders maximized as far as possible (same as valley), and sell
            orders as close as possible to cp (same as mountain).

            Sell slope:
            Maximize order size as high as possible. Buy orders as close (same as mountain), and sell orders as far as
            possible from cp (same as valley).

            :param str | asset: 'base' or 'quote', depending if checking sell or buy
            :param Amount | asset_balance: Balance of the account
            :param list | orders: List of buy or sell orders
            :return bool | True = all available funds was allocated
                           False = not all funds was allocated, can increase more orders next time
        """
        total_balance = 0
        order_type = ''
        symbol = ''
        precision = 0
        new_order_amount = 0
        furthest_order_bound = 0

        if asset == 'quote':
            total_balance = self.quote_total_balance
            order_type = 'sell'
            symbol = self.market['quote']['symbol']
            precision = self.market['quote']['precision']
        elif asset == 'base':
            total_balance = self.base_total_balance
            order_type = 'buy'
            symbol = self.market['base']['symbol']
            precision = self.market['base']['precision']

        # Mountain mode:
        if (self.mode == 'mountain' or
                (self.mode == 'buy_slope' and asset == 'quote') or
                (self.mode == 'sell_slope' and asset == 'base')):
            """ Starting from the furthest order. For each order, see if it is approximately
                maximum size.
                If it is, move on to next.
                If not, cancel it and replace with maximum size order. Then return.
                If highest_sell_order is reached, increase it to maximum size

                Maximum size is:
                1. As many "amount * (1 + increment)" as the order further (further_bound)
                AND
                2. As many "amount" as the order closer to center (closer_bound)

                Note: for buy orders "amount" is BASE asset amount, and for sell order "amount" is QUOTE.

                Also when making an order it's size always will be limited by available free balance
            """
            # Get orders and amounts to be compared. Note: orders are sorted from low price to high
            for order in orders:
                order_index = orders.index(order)
                order_amount = order['base']['amount']

                # This check prevents choosing order with index lower than the list length
                if order_index == 0:
                    # In case checking the first order, use the same order, but increased by 1 increment
                    # This allows our closest order amount exceed highest opposite-side order amount
                    closer_order = order
                    closer_bound = closer_order['base']['amount'] * (1 + self.increment)
                else:
                    closer_order = orders[order_index - 1]
                    closer_bound = closer_order['base']['amount']

                # This check prevents choosing order with index higher than the list length
                if order_index + 1 < len(orders):
                    # Current order is a not furthest order
                    further_order = orders[order_index + 1]
                    is_least_order = False
                else:
                    # Current order is furthest order
                    further_order = orders[order_index]
                    is_least_order = True

                further_bound = further_order['base']['amount'] * (1 + self.increment)

                if (further_bound > order_amount * (1 + self.increment / 10) < closer_bound and
                        further_bound - order_amount >= order_amount * self.increment / 2):
                    # Calculate new order size and place the order to the market
                    new_order_amount = further_bound

                    if is_least_order:
                        new_orders_sum = 0
                        amount = order_amount
                        for o in orders:
                            amount = amount * (1 + self.increment)
                            new_orders_sum += amount
                        # To reduce allocation rounds, increase furthest order more
                        new_order_amount = order_amount * (total_balance / new_orders_sum) \
                            * (1 + self.increment * 0.75)

                        if new_order_amount < closer_bound:
                            """ This is for situations when calculated new_order_amount is not big enough to
                                allocate all funds. Use partial-increment increase, so we'll got at least one full
                                increase round.  Whether we will just use `new_order_amount = further_bound`, we will
                                get less than one full allocation round, thus leaving closest-to-center order not
                                increased.
                            """
                            new_order_amount = closer_bound / (1 + self.increment * 0.2)

                    quote_amount = 0
                    price = 0

                    if asset == 'quote':
                        price = (order['price'] ** -1)
                        quote_amount = new_order_amount
                    elif asset == 'base':
                        price = order['price']
                        quote_amount = new_order_amount / price

                    if asset_balance < new_order_amount - order['for_sale']['amount']:
                        # Balance should be enough to replace partially filled order
                        self.log.debug('Not enough balance to increase {} order at price {:.8f}'
                                       .format(order_type, price))
                        return True

                    self.log.info('Increasing {} order at price {:.8f} from {:.{prec}f} to {:.{prec}f} {}'
                                  .format(order_type, price, order_amount, new_order_amount, symbol, prec=precision))
                    self.log.debug('Cancelling {} order in increase_order_sizes(); mode: {}, amount: {}, price: {:.8f}'
                                   .format(order_type, self.mode, order_amount, price))
                    self.cancel_orders_wrapper(order)
                    if asset == 'quote':
                        if isinstance(order, VirtualOrder):
                            self.place_virtual_sell_order(quote_amount, price)
                        else:
                            self.place_market_sell_order(quote_amount, price)
                    elif asset == 'base':
                        if isinstance(order, VirtualOrder):
                            self.place_virtual_buy_order(quote_amount, price)
                        else:
                            self.place_market_buy_order(quote_amount, price)

                    # Only one increase at a time. This prevents running more than one increment round simultaneously
                    return False
        elif (self.mode == 'valley' or
              (self.mode == 'buy_slope' and asset == 'base') or
              (self.mode == 'sell_slope' and asset == 'quote')):
            """ Starting from the furthest order, for each order, see if it is approximately
                maximum size.
                If it is, move on to next.
                If not, cancel it and replace with maximum size order. Maximum order size will be a
                size of closer-to-center order. Then return.
                If furthest is reached, increase it to maximum size.

                Maximum size is (example for buy orders):
                1. As many "base" as the further order (further_order_bound)
                2. As many "base" as the order closer to center (closer_order_bound)
            """
            orders_count = len(orders)
            orders = list(reversed(orders))

            closest_order = orders[-1]
            closest_order_bound = closest_order['base']['amount'] * (1 + self.increment)

            for order in orders:
                order_index = orders.index(order)
                order_amount = order['base']['amount']

                if order_index == 0:
                    # This is a furthest order
                    further_order_bound = order['base']['amount']
                    furthest_order_bound = order['base']['amount']
                else:
                    # Not a furthest order
                    further_order = orders[order_index - 1]
                    further_order_bound = further_order['base']['amount']

                if order_index + 1 < orders_count:
                    # Closer order is an order which one-step closer to the center
                    closer_order = orders[order_index + 1]
                    closer_order_bound = closer_order['base']['amount']
                else:
                    """ Special processing for the closest order.

                        Calculate new order amount based on orders count, but do not allow to perform too small 
                        increase rounds. New lowest buy / highest sell should be higher by at least one increment.
                    """
                    closer_order_bound = closest_order_bound
                    new_amount = (total_balance / orders_count) / (1 + self.increment / 100)
                    if furthest_order_bound < new_amount > closer_order_bound:
                        # Maximize order up to max possible amount if we can
                        closer_order_bound = new_amount

                order_amount_normalized = order_amount * (1 + self.increment / 10)
                need_increase = False

                if (order_amount_normalized < further_order_bound and
                        further_order_bound - order_amount >= order_amount * self.increment / 2 and
                        order_amount_normalized < closest_order_bound):
                    """ Check whether order amount is less than further order and also less than `closer order +
                        increment`. We need this check to be able to increase closer orders more smoothly. Here is the
                        example:

                        [100 100 100 10 10 10] -- starting point, buy orders, result of imbalanced sides
                        [100 100 100 12 10 10]
                        [100 100 100 12 12 10]
                        [100 100 100 12 12 12]

                        Note: This check is taking precedence because we need to begin new increase round only after all
                        orders will be max-sized.
                    """
                    need_increase = True

                    # To speed up the process, use at least N% increases
                    increase_factor = max(1 + self.increment, self.min_increase_factor)
                    # Do not allow to increase more than further order amount
                    new_order_amount = min(closer_order_bound * increase_factor, further_order_bound)

                    if new_order_amount < order_amount_normalized:
                        # Skip order if new amount is less than current for any reason
                        need_increase = False

                elif (order_amount_normalized < closer_order_bound and
                        closer_order_bound - order_amount >= order_amount * self.increment / 2):
                    """ Check whether order amount is less than closer or order and the diff is more than 50% of one
                        increment. Note: we can use only 50% or less diffs. Bigger will not work. For example, with 
                        diff 80% an order may have an actual difference like 30% from closer and 70% from further.
                    """
                    new_order_amount = closer_order_bound
                    need_increase = True

                if need_increase:
                    price = 0
                    quote_amount = 0

                    if asset == 'quote':
                        price = (order['price'] ** -1)
                        quote_amount = new_order_amount
                    elif asset == 'base':
                        price = order['price']
                        quote_amount = new_order_amount / price

                    if asset_balance < new_order_amount - order['for_sale']['amount']:
                        # Balance should be enough to replace partially filled order
                        self.log.debug('Not enough balance to increase {} order at price {:.8f}'
                                       .format(order_type, price))
                        return True

                    self.log.info('Increasing {} order at price {:.8f} from {:.{prec}f} to {:.{prec}f} {}'
                                  .format(order_type, price, order_amount, new_order_amount, symbol, prec=precision))
                    self.log.debug('Cancelling {} order in increase_order_sizes(); mode: {}, amount: {}, price: {:.8f}'
                                   .format(order_type, self.mode, order_amount, price))
                    self.cancel_orders_wrapper(order)
                    if asset == 'quote':
                        if isinstance(order, VirtualOrder):
                            self.place_virtual_sell_order(quote_amount, price)
                        else:
                            self.place_market_sell_order(quote_amount, price)
                    elif asset == 'base':
                        if isinstance(order, VirtualOrder):
                            self.place_virtual_buy_order(quote_amount, price)
                        else:
                            self.place_market_buy_order(quote_amount, price)

                    # One increase at a time. This prevents running more than one increment round simultaneously.
                    return False

        elif self.mode == 'neutral':
            """ Starting from the furthest order, for each order, see if it is approximately
                maximum size.
                If it is, move on to next.
                If not, cancel it and replace with maximum size order. Maximum order size will be a
                size of closer-to-center order. Then return.
                If furthest is reached, increase it to maximum size.

                Maximum size is (example for buy orders):
                1. As many "base * sqrt(1 + increment)" as the further order (further_order_bound)
                2. As many "base / sqrt(1 + increment)" as the order closer to center (closer_order_bound)
            """

            orders_count = len(orders)
            orders = list(reversed(orders))
            closest_order = orders[-1]
            previous_amount = 0

            for order in orders:
                order_index = orders.index(order)
                order_amount = order['base']['amount']

                if order_index == 0:
                    # This is a furthest order
                    further_order_bound = order['base']['amount']
                    furthest_order_bound = order['base']['amount']
                else:
                    # Not a furthest order
                    further_order = orders[order_index - 1]
                    further_order_bound = further_order['base']['amount'] * math.sqrt(1 + self.increment)

                if order_index + 1 < orders_count:
                    # Closer order is an order which one-step closer to the center
                    closer_order = orders[order_index + 1]
                    closer_order_bound = closer_order['base']['amount'] / math.sqrt(1 + self.increment)
                    is_closest_order = False
                else:
                    is_closest_order = True
                    closer_order_bound = order['base']['amount'] * (1 + self.increment)

                    new_orders_sum = 0
                    amount = order_amount
                    for o in orders:
                        new_orders_sum += amount
                        amount = amount / math.sqrt(1 + self.increment)
                    virtual_furthest_order_bound = amount * (total_balance / new_orders_sum)
                    new_amount = order_amount * (total_balance / new_orders_sum)

                    if new_amount > closer_order_bound and virtual_furthest_order_bound > furthest_order_bound:
                        # Maximize order up to max possible amount if we can
                        closer_order_bound = new_amount

                need_increase = False
                order_amount_normalized = order_amount * (1 + self.increment / 10)

                if (order_amount_normalized < further_order_bound and
                        further_order_bound - order_amount >= order_amount * (math.sqrt(1 + self.increment) - 1) / 2):
                    # Order is less than further order and diff is more than `increment / 2`

                    if is_closest_order:
                        new_order_amount = closer_order_bound
                        need_increase = True
                    else:
                        price = closest_order['price']
                        amount = closest_order['base']['amount']
                        while price > order['price'] * (1 + self.increment / 10):
                            # Calculate closer order amount based on current closest order
                            previous_amount = amount
                            price = price / (1 + self.increment)
                            amount = amount / math.sqrt(1 + self.increment)
                        if order_amount_normalized < previous_amount:
                            # Current order is less than virtually calculated next order
                            # Do not allow to increase more than further order amount
                            new_order_amount = min(order['base']['amount'] * (1 + self.increment), further_order_bound)
                            need_increase = True

                elif (order_amount_normalized < closer_order_bound and
                        closer_order_bound - order_amount >= order_amount * (math.sqrt(1 + self.increment) - 1) / 2):
                    # Order is less than closer order and diff is more than `increment / 2`

                    new_order_amount = closer_order_bound
                    need_increase = True

                if need_increase:
                    price = 0
                    quote_amount = 0

                    if asset == 'quote':
                        price = (order['price'] ** -1)
                        quote_amount = new_order_amount
                    elif asset == 'base':
                        price = order['price']
                        quote_amount = new_order_amount / price

                    if asset_balance < new_order_amount - order['for_sale']['amount']:
                        # Balance should be enough to replace partially filled order
                        self.log.debug('Not enough balance to increase {} order at price {:.8f}'
                                       .format(order_type, price))
                        return True

                    self.log.info('Increasing {} order at price {:.8f} from {:.{prec}f} to {:.{prec}f} {}'
                                  .format(order_type, price, order_amount, new_order_amount, symbol, prec=precision))
                    self.log.debug('Cancelling {} order in increase_order_sizes(); mode: {}'
                                   ', amount: {:.8f}, price: {:.8f}'
                                   .format(order_type, self.mode, order_amount, price))
                    self.cancel_orders_wrapper(order)
                    if asset == 'quote':
                        if isinstance(order, VirtualOrder):
                            self.place_virtual_sell_order(quote_amount, price)
                        else:
                            self.place_market_sell_order(quote_amount, price)
                    elif asset == 'base':
                        if isinstance(order, VirtualOrder):
                            self.place_virtual_buy_order(quote_amount, price)
                        else:
                            self.place_market_buy_order(quote_amount, price)

                    # One increase at a time. This prevents running more than one increment round simultaneously.
                    return False

        return None

    def check_partial_fill(self, order, fill_threshold=None):
        """ Checks whether order was partially filled it needs to be replaced

            :param dict | order: Order closest to the center price from buy or sell side
            :param float | fill_threshold: Order fill threshold, relative
            :return: bool | True = Order is correct size or within the threshold
                            False = Order is not right size
        """
        if fill_threshold is None:
            fill_threshold = self.partial_fill_threshold

        if self.is_buy_order(order):
            order_type = 'buy'
            price = order['price']
        else:
            order_type = 'sell'
            price = order['price'] ** -1

        if order['for_sale']['amount'] != order['base']['amount']:
            diff_abs = order['base']['amount'] - order['for_sale']['amount']
            diff_rel = diff_abs / order['base']['amount']
            if diff_rel > fill_threshold:
                self.log.debug('Partially filled {} order: {} {} @ {:.8f}, filled: {:.2%}'.format(
                               order_type, order['base']['amount'], order['base']['symbol'], price, diff_rel))
                return False
        return True

    def replace_partially_filled_order(self, order):
        """ Replace partially filled order

            :param order: Order instance
        """

        if order['base']['symbol'] == self.market['base']['symbol']:
            asset_balance = self.base_balance
            order_type = 'buy'
            precision = self.market['base']['precision']
        else:
            asset_balance = self.quote_balance
            order_type = 'sell'
            precision = self.market['quote']['precision']

        # Make sure we have enough balance to replace partially filled order
        if asset_balance + order['for_sale']['amount'] >= order['base']['amount']:
            # Cancel closest order and immediately replace it with new one.
            self.log.info('Replacing partially filled {} order'.format(order_type))
            self.cancel_orders_wrapper(order)
            if order_type == 'buy':
                self.place_market_buy_order(order['quote']['amount'], order['price'])
            elif order_type == 'sell':
                price = order['price'] ** -1
                self.place_market_sell_order(order['base']['amount'], price)
            if self.returnOrderId:
                self.refresh_balances(total_balances=False)
        else:
            needed = order['base']['amount'] - order['for_sale']['amount']
            self.log.debug('Unable to replace partially filled {} order: avail/needed: {:.{prec}f}/{:.{prec}f} {}'
                           .format(order_type, asset_balance['amount'], needed, order['base']['symbol'],
                                   prec=precision))

    def place_closer_order(self, asset, order, place_order=True, allow_partial=False, own_asset_limit=None,
                           opposite_asset_limit=None):
        """ Place order closer to the center

            :param asset:
            :param order: Previously closest order
            :param bool | place_order: True = Places order to the market, False = returns amount and price
            :param bool | allow_partial: True = Allow to downsize order whether there is not enough balance
            :param float | own_asset_limit: order should be limited in size by amount of order's "base"
            :param float | opposite_asset_limit: order should be limited in size by order's "quote" amount

        """
        if own_asset_limit and opposite_asset_limit:
            self.log.error('Only own_asset_limit or opposite_asset_limit should be specified')
            self.disabled = True
            return None

        balance = 0
        order_type = ''
        quote_amount = 0
        symbol = ''

        # Define asset-dependent variables
        if asset == 'base':
            order_type = 'buy'
            balance = self.base_balance['amount']
            symbol = self.base_balance['symbol']
        elif asset == 'quote':
            order_type = 'sell'
            balance = self.quote_balance['amount']
            symbol = self.quote_balance['symbol']

        # Check for instant fill
        if asset == 'base':
            price = order['price'] * (1 + self.increment)
            if not self.is_instant_fill_enabled and price > float(self.ticker().get('lowestAsk')) and place_order:
                self.log.info('Refusing to place an order which crosses lowest ask')
                return None
        elif asset == 'quote':
            price = (order['price'] ** -1) / (1 + self.increment)
            if not self.is_instant_fill_enabled and price < float(self.ticker().get('highestBid')) and place_order:
                self.log.info('Refusing to place an order which crosses highest bid')
                return None

        # For next steps we do not need inverted price for sell orders
        price = order['price'] * (1 + self.increment)

        # Calculate new order amounts depending on mode
        opposite_asset_amount = 0
        own_asset_amount = 0
        if (self.mode == 'mountain' or
                (self.mode == 'buy_slope' and asset == 'quote') or
                (self.mode == 'sell_slope' and asset == 'base')):
            opposite_asset_amount = order['quote']['amount']
            own_asset_amount = opposite_asset_amount * price
        elif (self.mode == 'valley' or
              (self.mode == 'buy_slope' and asset == 'base') or
              (self.mode == 'sell_slope' and asset == 'quote')):
            own_asset_amount = order['base']['amount']
            opposite_asset_amount = own_asset_amount / price
        elif self.mode == 'neutral':
            own_asset_amount = order['base']['amount'] * math.sqrt(1 + self.increment)
            opposite_asset_amount = own_asset_amount / price

        # Apply limits. Limit order only whether passed limit is less than expected order size
        if own_asset_limit and own_asset_limit < own_asset_amount:
            own_asset_amount = own_asset_limit
            opposite_asset_amount = own_asset_amount / price
        elif opposite_asset_limit and opposite_asset_limit < opposite_asset_amount:
            opposite_asset_amount = opposite_asset_limit
            own_asset_amount = opposite_asset_amount * price

        limiter = 0
        if asset == 'base':
            # Define amounts in terms of BASE and QUOTE
            base_amount = own_asset_amount
            quote_amount = opposite_asset_amount
            limiter = base_amount
        elif asset == 'quote':
            quote_amount = own_asset_amount
            limiter = quote_amount
            price = price ** -1

        # Check whether new order will exceed available balance
        if balance < limiter:
            if place_order and not allow_partial:
                self.log.debug('Not enough balance to place closer {} order; need/avail: {:.8f}/{:.8f}'
                               .format(order_type, limiter, balance))
                place_order = False
            elif allow_partial:
                self.log.debug('Limiting {} order amount to available asset balance: {} {}'
                               .format(order_type, balance, symbol))
                if asset == 'base':
                    quote_amount = balance / price
                elif asset == 'quote':
                    quote_amount = balance

        if place_order and asset == 'base':
            virtual_bound = self.market_center_price / math.sqrt(1 + self.target_spread)
            orders_count = self.calc_buy_orders_count(virtual_bound, price)
            if orders_count > self.operational_depth and isinstance(order, VirtualOrder):
                # Allow to place closer order only if current is virtual

                self.log.info('Placing virtual closer buy order')
                new_order = self.place_virtual_buy_order(quote_amount, price)
            else:
                self.log.info('Placing closer buy order')
                new_order = self.place_market_buy_order(quote_amount, price)
        elif place_order and asset == 'quote':
            virtual_bound = self.market_center_price * math.sqrt(1 + self.target_spread)
            orders_count = self.calc_sell_orders_count(virtual_bound, price)
            if orders_count > self.operational_depth and isinstance(order, VirtualOrder):
                self.log.info('Placing virtual closer sell order')
                new_order = self.place_virtual_sell_order(quote_amount, price)
            else:
                self.log.info('Placing closer sell order')
                new_order = self.place_market_sell_order(quote_amount, price)
        else:
            new_order = {"amount": quote_amount, "price": price}

        return new_order

    def place_further_order(self, asset, order, place_order=True, allow_partial=False, virtual=False):
        """ Place order further from specified order

            :param asset:
            :param order: furthest buy or sell order
            :param bool | place_order: True = Places order to the market, False = returns amount and price
            :param bool | allow_partial: True = Allow to downsize order whether there is not enough balance
            :param bool | virtual: True = Force place a virtual order
        """
        balance = 0
        order_type = ''
        symbol = ''
        virtual_bound = self.market_center_price / math.sqrt(1 + self.target_spread)

        # Define asset-dependent variables
        if asset == 'base':
            order_type = 'buy'
            balance = self.base_balance['amount']
            symbol = self.base_balance['symbol']
        elif asset == 'quote':
            order_type = 'sell'
            balance = self.quote_balance['amount']
            symbol = self.quote_balance['symbol']

        price = order['price'] / (1 + self.increment)

        # Calculate new order amounts depending on mode
        opposite_asset_amount = 0
        own_asset_amount = 0
        if (self.mode == 'mountain' or
                (self.mode == 'buy_slope' and asset == 'quote') or
                (self.mode == 'sell_slope' and asset == 'base')):
            opposite_asset_amount = order['quote']['amount']
            own_asset_amount = opposite_asset_amount * price
        elif (self.mode == 'valley' or
              (self.mode == 'buy_slope' and asset == 'base') or
              (self.mode == 'sell_slope' and asset == 'quote')):
            own_asset_amount = order['base']['amount']
            opposite_asset_amount = own_asset_amount / price
        elif self.mode == 'neutral':
            opposite_asset_amount = own_asset_amount / price

        limiter = 0
        quote_amount = 0
        if asset == 'base':
            base_amount = own_asset_amount
            quote_amount = opposite_asset_amount
            limiter = base_amount
        elif asset == 'quote':
            quote_amount = own_asset_amount
            limiter = quote_amount
            price = price ** -1

        # Check whether new order will exceed available balance
        if balance < limiter:
            if place_order and not allow_partial:
                self.log.debug('Not enough balance to place further {} order; need/avail: {:.8f}/{:.8f}'
                               .format(order_type, limiter, balance))
                place_order = False
            elif allow_partial:
                self.log.debug('Limiting {} order amount to available asset balance: {} {}'
                               .format(order_type, balance, symbol))
                if asset == 'base':
                    quote_amount = balance / price
                elif asset == 'quote':
                    quote_amount = balance

        if place_order and asset == 'base':
            orders_count = self.calc_buy_orders_count(virtual_bound, price)
            if orders_count > self.operational_depth or virtual:
                self.log.info('Placing virtual further buy order')
                new_order = self.place_virtual_buy_order(quote_amount, price)
            else:
                self.log.info('Placing further buy order')
                new_order = self.place_market_buy_order(quote_amount, price)
        elif place_order and asset == 'quote':
            orders_count = self.calc_sell_orders_count(virtual_bound, price)
            if orders_count > self.operational_depth or virtual:
                self.log.info('Placing virtual further sell order')
                new_order = self.place_virtual_sell_order(quote_amount, price)
            else:
                self.log.info('Placing further sell order')
                new_order = self.place_market_sell_order(quote_amount, price)
        else:
            new_order = {"amount": quote_amount, "price": price}

        return new_order

    def place_highest_sell_order(self, quote_balance, place_order=True, market_center_price=None):
        """ Places sell order furthest to the market center price

            :param Amount | quote_balance: Available QUOTE asset balance
            :param bool | place_order: True = Places order to the market, False = returns amount and price
            :param float | market_center_price: Optional market center price, used to to check order
            :return dict | order: Returns highest sell order
        """
        if not market_center_price:
            market_center_price = self.market_center_price

        price = market_center_price * math.sqrt(1 + self.target_spread)

        if price > self.upper_bound:
            self.log.info(
                'Not placing highest sell order because price will exceed higher bound. Market center '
                'price: {:.8f}, closest order price: {:.8f}, upper_bound: {:.8f}'
                    .format(market_center_price, price, self.upper_bound))
            return

        sell_orders_count = self.calc_sell_orders_count(price, self.upper_bound)

        if self.fee_asset['id'] == self.market['quote']['id']:
            buy_orders_count = self.calc_buy_orders_count(price, self.lower_bound)
            fee = self.get_order_creation_fee(self.fee_asset)
            real_orders_count = min(buy_orders_count, self.operational_depth) + min(sell_orders_count,
                                                                                    self.operational_depth)
            # Exclude all further fees from avail balance
            quote_balance = quote_balance - fee * real_orders_count

        # Initialize local variables
        amount_quote = 0
        previous_price = 0
        previous_amount = 0
        if self.mode == 'mountain' or self.mode == 'buy_slope':
            previous_price = price
            orders_sum = 0
            amount = quote_balance['amount'] * self.increment

            while price <= self.upper_bound:
                previous_price = price
                previous_amount = amount
                orders_sum += previous_amount
                price = price * (1 + self.increment)
                amount = amount / (1 + self.increment)

            price = previous_price
            amount_quote = previous_amount * (quote_balance['amount'] / orders_sum)

        elif self.mode == 'neutral':
            previous_price = price
            orders_sum = 0
            amount = quote_balance['amount'] * (math.sqrt(1 + self.increment) - 1)

            while price <= self.upper_bound:
                previous_price = price
                previous_amount = amount
                orders_sum += previous_amount
                price = price * (1 + self.increment)
                amount = amount / math.sqrt(1 + self.increment)

            price = previous_price
            amount_quote = previous_amount * (quote_balance['amount'] / orders_sum)

        elif self.mode == 'valley' or self.mode == 'sell_slope':
            orders_count = 0
            while price <= self.upper_bound:
                previous_price = price
                orders_count += 1
                price = price * (1 + self.increment)

            price = previous_price
            amount_quote = quote_balance['amount'] / orders_count

        precision = self.market['quote']['precision']
        amount_quote = int(float(amount_quote) * 10 ** precision) / (10 ** precision)

        if place_order:
            if sell_orders_count > self.operational_depth:
                order = self.place_virtual_sell_order(amount_quote, price)
            else:
                order = self.place_market_sell_order(amount_quote, price)
        else:
            order = {"amount": amount_quote, "price": price}

        return order

    def place_lowest_buy_order(self, base_balance, place_order=True, market_center_price=None):
        """ Places buy order furthest to the market center price

            Turn BASE amount into QUOTE amount (we will buy this QUOTE amount).
            QUOTE = BASE / price

            Furthest order amount calculations:
            -----------------------------------

            Mountain:
            For asset to be allocated (base for buy and quote for sell orders)
            First order (furthest) = balance * increment
            Next order = previous order / (1 + increment)
            Repeat until last order.

            Neutral:
            For asset to be allocated (base for buy and quote for sell orders)
            First order (furthest) = balance * (sqrt(1 + increment) - 1)
            Next order = previous order / sqrt(1 + increment)
            Repeat until last order

            Valley:
            For asset to be allocated (base for buy and quote for sell orders)
            All orders = balance / number of orders (per side)

            Buy slope:
            Buy orders same as valley
            Sell orders same as mountain

            Sell slope:
            Buy orders same as mountain
            Sell orders same as valley

            :param Amount | base_balance: Available BASE asset balance
            :param bool | place_order: True = Places order to the market, False = returns amount and price
            :param float | market_center_price: Optional market center price, used to to check order
            :return dict | order: Returns lowest buy order
        """
        if not market_center_price:
            market_center_price = self.market_center_price

        price = market_center_price / math.sqrt(1 + self.target_spread)

        if price < self.lower_bound:
            self.log.info(
                'Not placing lowest buy order because price will exceed lower bound. Market center price: '
                '{:.8f}, closest order price: {:.8f}, lower bound: {:.8f}'
                    .format(market_center_price, price, self.lower_bound))
            return

        buy_orders_count = self.calc_buy_orders_count(price, self.lower_bound)

        if self.fee_asset['id'] == self.market['base']['id']:
            fee = self.get_order_creation_fee(self.fee_asset)
            sell_orders_count = self.calc_sell_orders_count(price, self.upper_bound)
            real_orders_count = min(buy_orders_count, self.operational_depth) + min(sell_orders_count,
                                                                                    self.operational_depth)
            # Exclude all further fees from avail balance
            base_balance = base_balance - fee * real_orders_count

        # Initialize local variables
        amount_quote = 0
        previous_price = 0
        previous_amount = 0
        if self.mode == 'mountain' or self.mode == 'sell_slope':
            previous_price = price
            orders_sum = 0
            amount = base_balance['amount'] * self.increment

            while price >= self.lower_bound:
                previous_price = price
                previous_amount = amount
                orders_sum += previous_amount
                price = price / (1 + self.increment)
                amount = amount / (1 + self.increment)

            amount_base = previous_amount * (base_balance['amount'] / orders_sum)
            price = previous_price
            amount_quote = amount_base / price

        elif self.mode == 'neutral':
            previous_price = price
            orders_sum = 0
            amount = base_balance['amount'] * (math.sqrt(1 + self.increment) - 1)

            while price >= self.lower_bound:
                previous_price = price
                previous_amount = amount
                orders_sum += previous_amount
                price = price / (1 + self.increment)
                amount = amount / math.sqrt(1 + self.increment)

            amount_base = previous_amount * (base_balance['amount'] / orders_sum)
            price = previous_price
            amount_quote = amount_base / price

        elif self.mode == 'valley' or self.mode == 'buy_slope':
            orders_count = 0
            while price >= self.lower_bound:
                previous_price = price
                price = price / (1 + self.increment)
                orders_count += 1

            price = previous_price
            amount_base = base_balance['amount'] / orders_count
            amount_quote = amount_base / price

        precision = self.market['quote']['precision']
        amount_quote = int(float(amount_quote) * 10 ** precision) / (10 ** precision)

        if place_order:
            if buy_orders_count > self.operational_depth:
                order = self.place_virtual_buy_order(amount_quote, price)
            else:
                order = self.place_market_buy_order(amount_quote, price)
        else:
            order = {"amount": amount_quote, "price": price}

        return order

    def calc_buy_orders_count(self, price_high, price_low):
        """ Calculate number of buy orders to place between high price and low price

            :param float | price_high: Highest buy price bound
            :param float | price_low: Lowest buy price bound
            :return int | count: Returns number of orders
        """
        orders_count = 0
        while price_high >= price_low:
            orders_count += 1
            price_high = price_high / (1 + self.increment)
        return orders_count

    def calc_sell_orders_count(self, price_low, price_high):
        """ Calculate number of sell orders to place between low price and high price

            :param float | price_low: Lowest sell price bound
            :param float | price_high: Highest sell price bound
            :return int | count: Returns number of orders
        """
        orders_count = 0
        while price_low <= price_high:
            orders_count += 1
            price_low = price_low * (1 + self.increment)
        return orders_count

    def place_virtual_buy_order(self, amount, price):
        """ Place a virtual buy order

            :param float | amount: Order amount in QUOTE
            :param float | price: Order price in BASE
            :return dict | order: Returns virtual order instance
        """
        symbol = self.market['base']['symbol']
        precision = self.market['base']['precision']

        order = VirtualOrder()
        order['price'] = price

        quote_asset = Amount(amount, self.market['quote']['symbol'])
        order['quote'] = quote_asset

        base_asset = Amount(amount * price, self.market['base']['symbol'])
        order['base'] = base_asset
        order['for_sale'] = base_asset

        self.log.info('Placing a virtual buy order for {:.{prec}f} {} @ {:.8f}'
                      .format(order['base']['amount'], symbol, price, prec=precision))
        self.virtual_orders.append(order)

        # Immediately lower avail balance
        self.base_balance['amount'] -= order['base']['amount']

        return order

    def place_virtual_sell_order(self, amount, price):
        """ Place a virtual sell order

            :param float | amount: Order amount in QUOTE
            :param float | price: Order price in BASE
            :return dict | order: Returns virtual order instance
        """
        symbol = self.market['quote']['symbol']
        precision = self.market['quote']['precision']

        order = VirtualOrder()
        order['price'] = price ** -1

        quote_asset = Amount(amount * price, self.market['base']['symbol'])
        order['quote'] = quote_asset

        base_asset = Amount(amount, self.market['quote']['symbol'])
        order['base'] = base_asset
        order['for_sale'] = base_asset

        self.log.info('Placing a virtual sell order for {:.{prec}f} {} @ {:.8f}'
                      .format(amount, symbol, price, prec=precision))
        self.virtual_orders.append(order)

        # Immediately lower avail balance
        self.quote_balance['amount'] -= order['base']['amount']

        return order

    def cancel_orders_wrapper(self, orders, **kwargs):
        """ Cancel specific order(s)
            :param list orders: list of orders to cancel
        """
        if not isinstance(orders, (list, set, tuple)):
            orders = [orders]

        virtual_orders = [order['price'] for order in orders if isinstance(order, VirtualOrder)]
        real_orders = [order for order in orders if 'id' in order]

        # Just rebuild virtual orders list to avoid calling Asset's __eq__ method
        self.virtual_orders = [order for order in self.virtual_orders if order['price'] not in virtual_orders]

        if real_orders:
            return self.cancel_orders(real_orders, **kwargs)

        return True

    def error(self, *args, **kwargs):
        self.disabled = True

    def pause(self):
        """ Override pause() in BaseStrategy """
        pass

    def purge(self):
        """ We are not cancelling orders on save/remove worker from the GUI
            TODO: don't work yet because worker removal is happening via BaseStrategy staticmethod
        """
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


class VirtualOrder(dict):
    """ Wrapper class to handle virtual orders comparison in list index() method
    """
    def __float__(self):
        return self['price']
