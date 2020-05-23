import math
import time
import uuid
from functools import reduce

import bitsharesapi.exceptions
from bitshares.amount import Amount
from bitshares.dex import Dex

from dexbot.decorators import check_last_run
from dexbot.strategies.base import StrategyBase
from dexbot.strategies.config_parts.staggered_config import StaggeredConfig


class Strategy(StrategyBase):
    """Staggered Orders strategy."""

    @classmethod
    def configure(cls, return_base_config=True):
        return StaggeredConfig.configure(return_base_config)

    @classmethod
    def configure_details(cls, include_default_tabs=True):
        return StaggeredConfig.configure_details(include_default_tabs)

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
        self.enable_fallback_logic = self.worker.get('enable_fallback_logic', True)
        self.enable_stop_loss = self.worker.get('enable_stop_loss', False)
        self.stop_loss_discount = self.worker.get('stop_loss_discount', 5) / 100
        self.stop_loss_amount = self.worker.get('stop_loss_amount', 50) / 100

        if self.is_center_price_dynamic:
            self.center_price = None
        else:
            self.center_price = self.worker['center_price']

        fee_sum = self.market['base'].market_fee_percent + self.market['quote'].market_fee_percent
        if self.target_spread - self.increment <= fee_sum:
            self.log.error(
                'Spread must be greater than increment by at least {}, refusing to work because worker'
                ' will make losses'.format(fee_sum)
            )
            self.disabled = True

        if self.operational_depth < 2:
            self.log.error('Operational depth should be at least 2 orders')
            self.disabled = True

        # Strategy variables
        self.market_center_price = None
        self.old_center_price = None
        self.buy_orders = []
        self.sell_orders = []
        self.real_buy_orders = []
        self.real_sell_orders = []
        self.virtual_orders = []
        self.virtual_buy_orders = []
        self.virtual_sell_orders = []
        self.virtual_orders_restored = False
        self.quote_total_balance = 0
        self.base_total_balance = 0
        self.quote_balance = None
        self.base_balance = None
        self.quote_asset_threshold = 0
        self.base_asset_threshold = 0
        self.min_increase_factor = 1.05
        # Initial balance history elements should not be equal to avoid immediate bootstrap turn off
        self.quote_balance_history = [1, 2, 3]
        self.base_balance_history = [1, 2, 3]
        self.cached_orders = None

        # Dex instance used to get different fees for the market
        self.dex = Dex(self.bitshares)

        # Order expiration time
        self.expiration = 60 * 60 * 24 * 365 * 5

        # We do not waiting for order ids to be able to bundle operations
        self.returnOrderId = None

        # Minimal order amounts depending on defined increment
        self.order_min_base = 0
        self.order_min_quote = 0

        # Minimal check interval is needed to prevent event queue accumulation
        self.min_check_interval = 1
        self.max_check_interval = 120
        self.check_interval = self.min_check_interval

        # If no bootstrap state is recorded, assume we're in bootstrap
        self.get('bootstrapping', True)

        if self.view:
            self.update_gui_profit()
            self.update_gui_slider()

    @check_last_run
    def maintain_strategy(self, *args, **kwargs):
        """
        Logic of the strategy.

        :param args:
        :param kwargs:
        """
        # Get all user's orders on current market
        self.refresh_orders()

        # Check if market center price is calculated
        self.market_center_price = self.get_market_center_price(suppress_errors=True)

        # Set center price to manual value if needed. Manual center price works only when there are no orders
        if self.center_price and not (self.buy_orders or self.sell_orders):
            self.log.debug('Using manual center price because of no sell or buy orders')
            self.market_center_price = self.center_price

        # On empty market we need manual center price anyway
        if not self.market_center_price:
            if self.center_price:
                self.market_center_price = self.center_price
            else:
                # Still not have market_center_price? Empty market, don't continue
                self.log.warning('Cannot calculate center price on empty market, please set it manually')
                return

        # Calculate balances, and use orders from previous call of self.refresh_orders() to reduce API calls
        self.refresh_balances(use_cached_orders=True)

        # Store balance entry for profit estimation if needed
        self.store_profit_estimation_data()

        # Remove orders that exceed boundaries
        success = self.remove_outside_orders(self.sell_orders, self.buy_orders)
        if not success:
            # Return back to beginning
            return

        # Restore virtual orders on startup if needed
        if not self.virtual_orders_restored:
            self.restore_virtual_orders()

            if self.virtual_orders_restored:
                self.log.info('Virtual orders restored')
                return

        # Ensure proper operational depth
        if self.get_actual_spread() < self.target_spread + self.increment:
            self.check_operational_depth(self.real_buy_orders, self.virtual_buy_orders)
            self.check_operational_depth(self.real_sell_orders, self.virtual_sell_orders)

        # Remember current boostrapping state before sending transactions
        previous_bootstrap_state = self['bootstrapping']

        # Prepare to bundle operations into single transaction
        self.bitshares.bundle = True

        # BASE asset check
        if self.base_balance > self.base_asset_threshold:
            # Allocate available BASE funds
            self.allocate_asset('base', self.base_balance)

        # QUOTE asset check
        if self.quote_balance > self.quote_asset_threshold:
            # Allocate available QUOTE funds
            self.allocate_asset('quote', self.quote_balance)

        # Send pending operations
        trx_executed = False
        if not self.bitshares.txbuffer.is_empty():
            trx_executed = True
            try:
                trx = self.retry_action(self.execute)
            except bitsharesapi.exceptions.RPCError as exception:
                """
                Handle exception without stopping the worker.

                The goal is to handle race condition when partially filled order was further filled before we actually
                replaced them.
                """
                if str(exception).startswith('Assert Exception: maybe_found != nullptr: Unable to find Object'):
                    self.log.warning(exception)
                    self.bitshares.txbuffer.clear()
                    return
                else:
                    raise
            try:
                order_ids = [result[1] for result in trx['operation_results']]
            except TypeError:
                # For some reason 'operation_results' may be None, this should not fail us
                order_ids = []
            self.log.debug('Placed orders: %s', order_ids)
            self.refresh_orders()
            self.sync_current_orders()

        self.bitshares.bundle = False

        # Maintain the history of free balances after maintenance runs.
        # Save exactly key values instead of full key because it may be modified later on.
        self.refresh_balances()
        self.base_balance_history.append(self.base_balance['amount'])
        self.quote_balance_history.append(self.quote_balance['amount'])
        if len(self.base_balance_history) > 3:
            del self.base_balance_history[0]
            del self.quote_balance_history[0]

        # Ensure proper operational depth
        self.check_operational_depth(self.real_buy_orders, self.virtual_buy_orders)
        self.check_operational_depth(self.real_sell_orders, self.virtual_sell_orders)

        # Greatly increase check interval to lower CPU load whether there is no funds to allocate or we cannot
        # allocate funds for some reason
        if (
            self.check_interval == self.min_check_interval
            and self.base_balance_history[1] == self.base_balance_history[2]
            and self.quote_balance_history[1] == self.quote_balance_history[2]
        ):
            # Balance didn't changed, so we can reduce maintenance frequency
            self.log.debug(
                'Raising check interval up to {} seconds to reduce CPU usage'.format(self.max_check_interval)
            )
            self.check_interval = self.max_check_interval
        elif self.check_interval == self.max_check_interval and (
            self.base_balance_history[1] != self.base_balance_history[2]
            or self.quote_balance_history[1] != self.quote_balance_history[2]
        ):
            # Balance changed, increase maintenance frequency to allocate more quickly
            self.log.debug(
                'Reducing check interval to {} seconds because of changed ' 'balances'.format(self.min_check_interval)
            )
            self.check_interval = self.min_check_interval

        if previous_bootstrap_state is True and self['bootstrapping'] is False:
            # Bootstrap was turned off, dump initial orders
            self.dump_initial_orders()

        if self.enable_stop_loss:
            self.stop_loss_check()

        # Do not continue whether balances are changing or bootstrap is on
        if (
            self['bootstrapping']
            or self.base_balance_history[0] != self.base_balance_history[2]
            or self.quote_balance_history[0] != self.quote_balance_history[2]
            or trx_executed
            or not self.enable_fallback_logic
        ):
            return

        # There are no funds and current orders aren't close enough, try to fix the situation by shifting orders.
        # This is a fallback logic.

        actual_spread = self.get_actual_spread()
        if actual_spread < self.target_spread + self.increment:
            # Target spread is reached, no need to cancel anything
            return
        elif self.buy_orders:
            # If target spread is not reached and no balance to allocate, cancel lowest buy order
            self.log.info(
                'Free balances are not changing, bootstrap is off and target spread is not reached. '
                'Cancelling lowest buy order as a fallback'
            )
            self.cancel_orders_wrapper(self.buy_orders[-1])

        # Update profit estimate
        if self.view:
            self.update_gui_profit()

    def get_actual_spread(self, buy_price=None, sell_price=None):
        """Calculates current spread on own orders using cached orders."""
        if buy_price and sell_price:
            highest_buy_price = buy_price
            lowest_sell_price = sell_price
        else:
            try:
                highest_buy_price = self.buy_orders[0].get('price')
                lowest_sell_price = self.sell_orders[0].get('price')
                # Invert the sell price to BASE so it can be used in comparison
                lowest_sell_price = lowest_sell_price ** -1
            except IndexError:
                return float('Inf')
        spread = (lowest_sell_price / highest_buy_price) - 1
        return spread

    def calculate_min_amounts(self):
        """Calculate minimal order amounts depending on defined increment."""
        self.order_min_base = 2 * 10 ** -self.market['base']['precision'] / self.increment
        self.order_min_quote = 2 * 10 ** -self.market['quote']['precision'] / self.increment

    def stop_loss_check(self):
        """Check for Stop Loss condition and execute SL if needed."""
        if self.buy_orders:
            return

        highest_bid = float(self.ticker().get('highestBid'))
        if not highest_bid < self.lower_bound:
            return

        if not highest_bid:
            # highest_bid is 0
            highest_bid = self.lower_bound

        stop_loss_price = highest_bid / (1 + self.stop_loss_discount)
        amount = self.quote_total_balance * self.stop_loss_amount
        self.cancel_all_orders()
        self.log.warning(
            'Executing Stop Loss, selling {:.{prec}f} {} @ {:.8f}'.format(
                amount, self.market['quote']['symbol'], stop_loss_price, prec=self.market['quote']['precision']
            )
        )
        self.place_market_sell_order(amount, stop_loss_price, returnOrderId=True)
        self.error()

    def refresh_balances(self, use_cached_orders=False):
        """
        This function is used to refresh account balances.

        :param bool use_cached_orders (optional): when calculating orders
            balance, use cached orders from self.cached_orders

        This version supports usage of same bitshares account across multiple workers with assets intersections.
        """
        # Balances in orders on all related markets
        orders = self.get_all_own_orders(refresh=not use_cached_orders)
        order_ids = [order['id'] for order in orders]
        orders_balance = self.get_allocated_assets(order_ids)

        # Balances in own orders
        own_orders = self.get_own_orders(refresh=False)
        order_ids = [order['id'] for order in own_orders]
        own_orders_balance = self.get_allocated_assets(order_ids)

        # Get account free balances (not allocated into orders)
        account_balances = self.count_asset(order_ids=[], return_asset=True)

        # Calculate full asset balance on account
        quote_full_balance = account_balances['quote']['amount'] + orders_balance['quote']
        base_full_balance = account_balances['base']['amount'] + orders_balance['base']

        # Calculate operational balance for current worker
        # Operational balance is a part of the whole account balance which should be designated to this worker
        op_quote_balance = quote_full_balance
        op_base_balance = base_full_balance
        op_percent_quote = self.get_worker_share_for_asset(self.market['quote']['symbol'])
        op_percent_base = self.get_worker_share_for_asset(self.market['base']['symbol'])
        if op_percent_quote < 1:
            op_quote_balance *= op_percent_quote
            self.log.debug(
                'Using {:.2%} of QUOTE balance ({:.{prec}f} {})'.format(
                    op_percent_quote,
                    op_quote_balance,
                    self.market['quote']['symbol'],
                    prec=self.market['quote']['precision'],
                )
            )
        if op_percent_base < 1:
            op_base_balance *= op_percent_base
            self.log.debug(
                'Using {:.2%} of BASE balance ({:.{prec}f} {})'.format(
                    op_percent_base,
                    op_base_balance,
                    self.market['base']['symbol'],
                    prec=self.market['base']['precision'],
                )
            )

        # Count balances allocated into virtual orders
        virtual_orders_base_balance = 0
        virtual_orders_quote_balance = 0
        if self.virtual_orders:
            # Todo: can we use filtered orders from refresh_orders() here?
            buy_orders = self.filter_buy_orders(self.virtual_orders)
            sell_orders = self.filter_sell_orders(self.virtual_orders, invert=False)
            virtual_orders_base_balance = reduce((lambda x, order: x + order['base']['amount']), buy_orders, 0)
            virtual_orders_quote_balance = reduce((lambda x, order: x + order['base']['amount']), sell_orders, 0)

        # Total balance per asset (orders balance and available balance)
        # Total balance should be: max(operational, real_orders + virtual_orders)
        # Total balance used when increasing least/closest orders
        self.quote_total_balance = max(op_quote_balance, own_orders_balance['quote'] + virtual_orders_quote_balance)
        self.base_total_balance = max(op_base_balance, own_orders_balance['base'] + virtual_orders_base_balance)

        # Prepare variables with free balance available to the worker
        self.quote_balance = account_balances['quote']
        self.base_balance = account_balances['base']

        # Calc avail balance; avail balances used in maintain_strategy to pass into allocate_asset
        # avail = total - real_orders - virtual_orders
        self.quote_balance['amount'] = (
            self.quote_total_balance - own_orders_balance['quote'] - virtual_orders_quote_balance
        )
        self.base_balance['amount'] = self.base_total_balance - own_orders_balance['base'] - virtual_orders_base_balance

        # Reserve fees for N orders
        reserve_num_orders = 200
        fee_reserve = reserve_num_orders * self.get_order_creation_fee(self.fee_asset)

        # Finally, reserve only required asset
        if self.fee_asset['id'] == self.market['base']['id']:
            self.base_balance['amount'] -= fee_reserve
        elif self.fee_asset['id'] == self.market['quote']['id']:
            self.quote_balance['amount'] -= fee_reserve

    def refresh_orders(self):
        """Updates buy and sell orders."""
        orders = self.get_own_orders()

        # Sort virtual orders
        self.virtual_buy_orders = self.filter_buy_orders(self.virtual_orders, sort='DESC')
        self.virtual_sell_orders = self.filter_sell_orders(self.virtual_orders, sort='DESC', invert=False)

        # Sort real orders
        # (order with index 0 is closest to the center price and -1 is furthers)
        self.real_buy_orders = self.filter_buy_orders(orders, sort='DESC')
        self.real_sell_orders = self.filter_sell_orders(orders, sort='DESC', invert=False)

        # Concatenate real orders and virtual_orders
        self.buy_orders = self.real_buy_orders + self.virtual_buy_orders
        self.sell_orders = self.real_sell_orders + self.virtual_sell_orders

    def sync_current_orders(self):
        """Sync current orders to the db."""
        current_real_orders = self.real_buy_orders + self.real_sell_orders
        current_all_orders = self.buy_orders + self.sell_orders
        current_real_ids = set([order['id'] for order in current_real_orders])
        current_all_ids = set([order['id'] for order in current_all_orders])
        stored_ids = set(self.fetch_orders_extended(custom='current', return_ids_only=True))
        # We need to remove both virtual and real orders
        to_remove_ids = stored_ids.difference(current_all_ids)
        # We need to add only real orders ids because virtual are added in place_virtual_xxx_order()
        to_add_ids = current_real_ids.difference(stored_ids)
        to_add_orders = [order for order in current_real_orders if order['id'] in to_add_ids]

        for _id in to_remove_ids:
            self.remove_order(_id)

        for order in to_add_orders:
            self.save_order_extended(order, custom='current')

    def dump_initial_orders(self):
        """Save orders after initial placement for later use (visualization and so on)"""
        self.refresh_orders()
        orders = self.buy_orders + self.sell_orders
        self.log.info('Dumping initial orders into db')
        # Ids should be changed to avoid ids intersection with "current" orders
        for order in orders:
            order['id'] = str(uuid.uuid4())
            if isinstance(order, VirtualOrder):
                self.save_order_extended(order, virtual=True, custom='initial')
            else:
                self.save_order_extended(order, virtual=False, custom='initial')

    def drop_initial_orders(self):
        """Drop old "initial" orders from the db."""
        self.log.debug('Removing initial orders from the db')
        self.clear_orders_extended(custom='initial')

    def remove_outside_orders(self, sell_orders, buy_orders):
        """
        Remove orders that exceed boundaries.

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
        """
        Create virtual further orders in batch manner. This helps to place further orders quickly on startup.

        If we have both buy and sell real orders, restore both. If we have only one type of orders, restore
        corresponding virtual orders and purge opposite orders.
        """

        def place_further_buy_orders():
            furthest_order = self.real_buy_orders[-1]
            while furthest_order['price'] > self.lower_bound * (1 + self.increment):
                furthest_order = self.place_further_order('base', furthest_order, virtual=True)
                if not isinstance(furthest_order, VirtualOrder):
                    # Failed to place order
                    break

        def place_further_sell_orders():
            furthest_order = self.real_sell_orders[-1]
            while furthest_order['price'] ** -1 < self.upper_bound / (1 + self.increment):
                furthest_order = self.place_further_order('quote', furthest_order, virtual=True)
                if not isinstance(furthest_order, VirtualOrder):
                    # Failed to place order
                    break

        # Load orders from the database
        result = self.fetch_orders_extended(only_virtual=True, custom='current')
        stored_orders = [entry['order'] for entry in result] if result else []
        stored_buy_orders = self.filter_buy_orders(stored_orders)
        stored_sell_orders = self.filter_sell_orders(stored_orders, invert=False)

        if not self.buy_orders and not self.sell_orders:
            # No real orders, assume we need to bootstrap, purge old orders
            self.log.info('No real orders, purging old virtual orders')
            self.clear_orders_extended(custom='current')
        elif self.buy_orders and self.sell_orders:
            if stored_orders:
                self.log.info('Loading virtual orders from database')
                for order in stored_orders:
                    self.virtual_orders.append(VirtualOrder(order))
            else:
                self.log.info('Recreating virtual orders')
                place_further_buy_orders()
                place_further_sell_orders()
        elif self.buy_orders and not self.sell_orders:
            # Only buy orders, purge stored sell orders
            if stored_sell_orders:
                self.log.info('Purging virtual sell orders because of no real sell orders')
                for order in stored_sell_orders:
                    self.remove_order(order)

            if stored_buy_orders:
                self.log.info('Loading virtual buy orders from database')
                for order in stored_buy_orders:
                    self.virtual_orders.append(VirtualOrder(order))
            else:
                place_further_buy_orders()
        elif not self.buy_orders and self.sell_orders:
            if stored_buy_orders:
                self.log.info('Purging virtual buy orders because of no real buy orders')
                for order in stored_buy_orders:
                    self.remove_order(order)

            if stored_sell_orders:
                self.log.info('Loading virtual sell orders from database')
                for order in stored_sell_orders:
                    self.virtual_orders.append(VirtualOrder(order))
            else:
                place_further_sell_orders()

        # Set "restored" flag anyway to not break initial bootstrap
        self.virtual_orders_restored = True

    def check_operational_depth(self, real_orders, virtual_orders):
        """
        Ensure proper operational depth. Replace excessive real orders or put real orders if needed.

        :param list real_orders: list of real orders
        :param list virtual_orders: list of virtual orders
        """
        num_real_orders = len(real_orders)
        num_virtual_orders = len(virtual_orders)

        if num_real_orders > self.operational_depth:
            for i in range(1, num_real_orders - self.operational_depth + 1):
                self.replace_real_order_with_virtual(real_orders[-i])
        elif num_real_orders < self.operational_depth and not self['bootstrapping']:
            # We need to wait until bootstrap is off because during initial orders placement this would start to place
            # real orders without waiting until all range will be covered.

            # Note: if boostrap is on and there is nothing to allocate, this check would not work until some orders
            # will be filled. This means that changing `operational_depth` config param will not work immediately.

            to_replace = min(num_virtual_orders, self.operational_depth - num_real_orders)
            for i in range(0, to_replace):
                self.replace_virtual_order_with_real(virtual_orders[i])
        else:
            return

        # Orders and balances needs to be refreshed to avoid races
        self.refresh_orders()
        self.refresh_balances(use_cached_orders=True)

    def replace_real_order_with_virtual(self, order):
        """
        Replace real limit order with virtual order.

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
        """
        Replace virtual order with real one.

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
            try:
                new_order = self.place_market_buy_order(quote_amount, price, returnOrderId=True)
            except bitsharesapi.exceptions.RPCError:
                self.log.exception('Error broadcasting trx:')
                return False
        else:
            quote_amount = order['base']['amount']
            price = order['price'] ** -1
            self.log.info('Replacing virtual sell order with real order')
            try:
                new_order = self.place_market_sell_order(quote_amount, price, returnOrderId=True)
            except bitsharesapi.exceptions.RPCError:
                self.log.exception('Error broadcasting trx:')
                return False

        if new_order:
            # Cancel virtual order
            self.cancel_orders_wrapper(order)
            return True
        return False

    def store_profit_estimation_data(self, force=False):
        """
        Stores balance history entry if center price moved enough.

        :param bool | force: True = force store data, False = store data only on center price change

        Todo: this method is inaccurate when using single account accross multiple workers
        """
        need_store = False
        account = self.config['workers'][self.worker_name].get('account')

        if force:
            need_store = True

        # If old center price is not set, try fetch from the db
        if not self.old_center_price and not force:
            old_data = self.get_recent_balance_entry(account, self.worker_name, self.base_asset, self.quote_asset)
            if old_data:
                self.old_center_price = old_data.center_price
            else:
                need_store = True

        if self.old_center_price and self.market_center_price and not force:
            # Check if center price changed more than increment
            diff = abs(self.old_center_price - self.market_center_price) / self.old_center_price
            if diff > self.increment:
                self.log.debug('Center price change is {:.2%}, need to store balance data'.format(diff))
                need_store = True

        if need_store and self.market_center_price:
            timestamp = time.time()
            self.log.debug('Storing balance data at center price {:.8f}'.format(self.market_center_price))
            self.store_balance_entry(
                account,
                self.worker_name,
                self.base_total_balance,
                self.base_asset,
                self.quote_total_balance,
                self.quote_asset,
                self.market_center_price,
                timestamp,
            )
            # Cache center price for later comparisons
            self.old_center_price = self.market_center_price

    def allocate_asset(self, asset, asset_balance):
        """
        Allocates available asset balance as buy or sell orders.

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
        opposite_precision = 0
        opposite_symbol = ''
        increase_status = None

        if asset == 'base':
            order_type = 'buy'
            own_symbol = self.base_balance['symbol']
            opposite_symbol = self.quote_balance['symbol']
            own_orders = self.buy_orders
            opposite_orders = self.sell_orders
            own_threshold = self.base_asset_threshold
            own_precision = self.market['base']['precision']
            opposite_precision = self.market['quote']['precision']
        elif asset == 'quote':
            order_type = 'sell'
            own_symbol = self.quote_balance['symbol']
            opposite_symbol = self.base_balance['symbol']
            own_orders = self.sell_orders
            opposite_orders = self.buy_orders
            own_threshold = self.quote_asset_threshold
            own_precision = self.market['quote']['precision']
            opposite_precision = self.market['quote']['precision']

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
            actual_spread = self.get_actual_spread(buy_price=closest_own_price, sell_price=closest_opposite_price)

            if actual_spread >= self.target_spread + self.increment:
                if not self.check_partial_fill(closest_own_order, fill_threshold=0):
                    # Replace closest order if it was partially filled for any %
                    """
                    Note on partial filled orders handling: if target spread is not reached and we need to place closer
                    order, we need to make sure current closest order is 100% unfilled.

                    When target spread is reached, we are replacing order only if it was filled no less than
                    `self.fill_threshold`. This helps to avoid too often replacements.
                    """
                    self.replace_partially_filled_order(closest_own_order)
                    return

                if (
                    self['bootstrapping']
                    and self.base_balance_history[2] == self.base_balance_history[0]
                    and self.quote_balance_history[2] == self.quote_balance_history[0]
                    and opposite_orders
                ):
                    # Turn off bootstrap mode whether we're didn't allocated assets during previous 3 maintenance
                    self.log.debug(
                        'Turning bootstrapping off: actual_spread > target_spread, we have free '
                        'balances and cannot allocate them normally 3 times in a row'
                    )
                    self['bootstrapping'] = False

                """ Note: because we're using operations batching, there is possible a situation when we will have
                    both free balances and `actual_spread >= self.target_spread + self.increment`. In such case
                    there will be TWO orders placed, one buy and one sell despite only one would be enough to reach
                    target spread. Sure, we can add a workaround for that by overriding `closest_opposite_price` for
                    second call of allocate_asset(). We are not doing this because we're not doing assumption on
                    which side order (buy or sell) should be placed first. So, when placing two closer orders from
                    both sides, spread will be no less than `target_spread - increment`, thus not making any loss.
                """

                # Place order closer to the center price
                self.log.debug(
                    'Placing closer {} order; actual spread: {:.4%}, target + increment: {:.4%}'.format(
                        order_type, actual_spread, self.target_spread + self.increment
                    )
                )

                if self['bootstrapping']:
                    self.place_closer_order(asset, closest_own_order)
                elif opposite_orders and actual_spread - self.increment < self.target_spread + self.increment:
                    """Place max-sized closer order if only one order needed to reach target spread (avoid unneeded
                    increases)"""
                    self.place_closer_order(asset, closest_own_order, allow_partial=True)
                # Place order limited by size of the opposite-side order
                elif opposite_orders:
                    # Load previously stored opposite orders
                    result = self.fetch_orders_extended(custom='current')
                    stored_orders = [entry['order'] for entry in result]
                    if asset == 'base':
                        opposite_orders = self.filter_sell_orders(stored_orders, sort='DESC', invert=False)
                    elif asset == 'quote':
                        opposite_orders = self.filter_buy_orders(stored_orders, sort='DESC')

                    try:
                        opposite_order = opposite_orders[0]
                        self.log.debug('Using stored opposite order')
                    except IndexError:
                        self.log.debug('Using real opposite order')
                        opposite_order = closest_opposite_order

                    if (
                        self.mode == 'mountain'
                        or (self.mode == 'buy_slope' and asset == 'base')
                        or (self.mode == 'sell_slope' and asset == 'quote')
                    ):
                        opposite_asset_limit = None
                        own_asset_limit = opposite_order['quote']['amount']
                        self.log.debug(
                            'Limiting {} order by opposite order: {:.{prec}f} {}'.format(
                                order_type, own_asset_limit, own_symbol, prec=own_precision
                            )
                        )
                    elif (
                        self.mode == 'valley'
                        or self.mode == 'neutral'
                        or (self.mode == 'buy_slope' and asset == 'quote')
                        or (self.mode == 'sell_slope' and asset == 'base')
                    ):
                        opposite_asset_limit = opposite_order['base']['amount']
                        own_asset_limit = None
                        self.log.debug(
                            'Limiting {} order by opposite order: {:.{prec}f} {}'.format(
                                order_type, opposite_asset_limit, opposite_symbol, prec=opposite_precision
                            )
                        )
                    allow_partial = True if asset == 'quote' else False
                    self.place_closer_order(
                        asset,
                        closest_own_order,
                        own_asset_limit=own_asset_limit,
                        opposite_asset_limit=opposite_asset_limit,
                        allow_partial=allow_partial,
                    )
                else:
                    # Opposite side probably reached range bound, allow to place partial order
                    self.place_closer_order(asset, closest_own_order, allow_partial=True)

                # Store balance data whether new actual spread will match target spread
                if actual_spread + self.increment >= self.target_spread and not self.bitshares.txbuffer.is_empty():
                    # Transactions are not yet sent, so balance refresh is not needed
                    self.store_profit_estimation_data(force=True)
            elif not opposite_orders:
                # Do not try to do anything than placing closer order whether there is no opposite orders
                return
            else:
                # Target spread is reached, let's allocate remaining funds
                if not self.check_partial_fill(closest_own_order, fill_threshold=0):
                    """Detect partially filled order on the own side and reserve funds to replace order in case opposite
                    order will be fully filled."""
                    funds_to_reserve = closest_own_order['base']['amount']
                    self.log.debug(
                        'Partially filled order on own side, reserving funds to replace: '
                        '{:.{prec}f} {}'.format(funds_to_reserve, own_symbol, prec=own_precision)
                    )
                    asset_balance -= funds_to_reserve

                if not self.check_partial_fill(closest_opposite_order, fill_threshold=0):
                    """
                    Detect partially filled order on the opposite side and reserve appropriate amount to place closer
                    order.

                    We adding some additional reserve to be able to place next order whether new allocation round will
                    be started, this is mostly for valley-like modes.
                    """
                    funds_to_reserve = 0
                    additional_reserve = max(1 + self.increment, self.min_increase_factor) * 1.05
                    closer_own_order = self.place_closer_order(asset, closest_own_order, place_order=False)

                    if asset == 'base':
                        funds_to_reserve = closer_own_order['amount'] * closer_own_order['price'] * additional_reserve
                    elif asset == 'quote':
                        funds_to_reserve = closer_own_order['amount'] * additional_reserve
                    self.log.debug(
                        'Partially filled order on opposite side, reserving funds for next {} order: '
                        '{:.{prec}f} {}'.format(order_type, funds_to_reserve, own_symbol, prec=own_precision)
                    )
                    asset_balance -= funds_to_reserve

                if asset_balance > own_threshold:
                    # Allocate excess funds
                    if (asset == 'base' and furthest_own_order_price / (1 + self.increment) < self.lower_bound) or (
                        asset == 'quote' and furthest_own_order_price * (1 + self.increment) > self.upper_bound
                    ):
                        # Lower/upper bound has been reached and now will start allocating rest of the balance.
                        self['bootstrapping'] = False
                        self.log.debug('Increasing sizes of {} orders'.format(order_type))
                        increase_status = self.increase_order_sizes(asset, asset_balance, own_orders)
                    else:
                        # Range bound is not reached, we need to add additional orders at the extremes
                        self['bootstrapping'] = False
                        self.log.debug('Placing further order than current furthest {} order'.format(order_type))
                        self.place_further_order(asset, furthest_own_order, allow_partial=True)
                else:
                    increase_status = 'done'

            if (
                increase_status == 'done'
                and not self.check_partial_fill(closest_own_order)
                and not self.check_partial_fill(closest_opposite_order, fill_threshold=0)
            ):
                """
                Replace partially filled closest orders only when allocation of excess funds was finished. This would
                prevent an abuse case when we are operating inactive market. An attacker can massively dump the price
                and then he can buy back the asset cheaper. Similar case may happen on the "normal" market on
                significant price drops or spikes.

                The logic how it works is following:
                1. If we have partially filled closest orders, reserve fuds to replace them later
                2. If we have excess funds, allocate them by increasing order sizes or expand bounds if needed
                3. When increase is finished, replace partially filled closest orders

                Thus we are don't need to precisely count how much was filled on closest orders.
                """
                # Refresh balances to make "reserved" funds available
                self.refresh_balances(use_cached_orders=True)
                self.replace_partially_filled_order(closest_own_order)
            elif increase_status == 'done' and not self.check_partial_fill(
                closest_opposite_order, fill_threshold=(1 - self.partial_fill_threshold)
            ):
                # Dust order on opposite side, cancel dust order and place closer order
                # Require empty txbuffer to avoid rare condition when order may be already canceled from
                # replace_partially_filled_order() call.
                # Note: we cannot use such check for own side because we will not have the balance to allocate
                self.log.info('Cancelling dust order at opposite side, placing closer {} order'.format(order_type))
                previous_bundle = self.bitshares.bundle
                self.bitshares.bundle = False
                self.cancel_orders_wrapper(closest_opposite_order)
                self.refresh_balances(use_cached_orders=True)
                self.place_closer_order(asset, closest_own_order, allow_partial=True)
                self.refresh_orders()
                self.bitshares.bundle = previous_bundle
        else:
            # Place furthest order as close to the bound as possible
            if not opposite_orders:
                self['bootstrapping'] = True
                self.drop_initial_orders()
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

    def _increase_single_order(self, asset, asset_balance, order, new_order_amount):
        """
        To avoid code doubling, use this unified function to increase single order.

        :param str asset: 'base' or 'quote', depending if checking sell or buy
        :param Amount asset_balance: asset balance available for increase
        :param order order: order needed to be increased
        :param float new_order_amount: BASE or QUOTE amount of a new order (depending on asset)
        :return: True = available funds were allocated, cannot allocate remainder
                 False = not all funds were allocated, can increase more orders next time
        :rtype: bool
        """
        quote_amount = 0
        base_amount = 0
        price = 0
        order_amount = order['base']['amount']
        order_type = ''
        symbol = ''
        precision = 0

        if asset == 'quote':
            order_type = 'sell'
            symbol = self.market['quote']['symbol']
            precision = self.market['quote']['precision']
            price = order['price'] ** -1
            # New order amount must be at least x2 precision bigger
            new_order_amount = max(
                new_order_amount, order['base']['amount'] + 2 * 10 ** -self.market['quote']['precision']
            )
            quote_amount = new_order_amount
            base_amount = quote_amount * price
        elif asset == 'base':
            order_type = 'buy'
            symbol = self.market['base']['symbol']
            precision = self.market['base']['precision']
            price = order['price']
            # New order amount must be at least x2 precision bigger
            new_order_amount = max(
                new_order_amount, order['base']['amount'] + 2 * 10 ** -self.market['base']['precision']
            )
            base_amount = new_order_amount
            quote_amount = base_amount / price

        needed_balance = new_order_amount - order['for_sale']['amount']
        if asset_balance < needed_balance:
            # Balance should be enough to replace partially filled order
            self.log.debug(
                'Not enough balance to increase {} order at price {:.8f}: {:.{prec}f}/{:.{prec}f} {}'.format(
                    order_type, price, asset_balance['amount'], needed_balance, symbol, prec=precision
                )
            )
            if asset == 'quote':
                self.quote_asset_threshold = needed_balance
            elif asset == 'base':
                self.base_asset_threshold = needed_balance
            # Increase finished
            return True

        self.log.debug(
            'Pre-increasing {} order at price {:.8f} from {:.{prec}f} to {:.{prec}f} {}'.format(
                order_type, price, order_amount, new_order_amount, symbol, prec=precision
            )
        )

        if asset == 'quote':
            order['base']['amount'] = quote_amount
            order['for_sale']['amount'] += needed_balance
            order['quote']['amount'] = base_amount
            asset_balance -= quote_amount - order_amount
        elif asset == 'base':
            order['base']['amount'] = base_amount
            order['for_sale']['amount'] += needed_balance
            order['quote']['amount'] = quote_amount
            asset_balance -= base_amount - order_amount

        # Increase not finished
        return False

    def _calc_increase(self, asset, asset_balance, orders):
        """
        Calculate increased order sizes for specified orders with inplace replacement of order amounts. Only one
        increase is performed at a time.

        :param str asset: 'base' or 'quote', depending if checking sell or buy
        :param Amount asset_balance: Balance of the account
        :param list orders: List of buy or sell orders
        :return: True = all available funds were allocated
                 False = not all funds was allocated, can increase more orders next time
        :rtype: bool
        """

        new_order_amount = 0
        furthest_order_bound = 0
        total_balance = 0

        if asset == 'quote':
            total_balance = self.quote_total_balance
        elif asset == 'base':
            total_balance = self.base_total_balance

        # Mountain mode:
        if (
            self.mode == 'mountain'
            or (self.mode == 'buy_slope' and asset == 'quote')
            or (self.mode == 'sell_slope' and asset == 'base')
        ):
            """
            Starting from the furthest order. For each order, see if it is approximately maximum size. If it is, move on
            to next. If not, cancel it and replace with maximum size order. Then return. If highest_sell_order is
            reached, increase it to maximum size.

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
                increase_factor = max(1 + self.increment, self.min_increase_factor)

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
                    further_bound = further_order['base']['amount'] * (1 + self.increment)
                else:
                    # Current order is furthest order
                    further_order = orders[order_index]
                    further_bound = further_order['base']['amount'] * increase_factor

                if (
                    further_bound > order_amount * (1 + self.increment / 10) < closer_bound
                    and further_bound - order_amount >= order_amount * self.increment / 2
                ):
                    # Calculate new order size and place the order to the market
                    """
                    To prevent moving liquidity away from center, let new order be no more than `order_amount *
                    increase_factor`. This is for situations when we increasing order on side which was previously
                    bigger. Example: buy side, amounts in QUOTE:

                    [1000 1000 1000 100 100 100 <center>]

                    Without increase_factor:
                    [1000 1000 1000 1000 100 100 <center>]

                    With increase_factor:
                    [1000 1000 1000 200 100 100 <center>]
                    [1000 1000 1000 200 200 100 <center>]
                    [1000 1000 1000 200 200 200 <center>]
                    """
                    new_order_amount = further_bound
                    increase_factor = max(1 + self.increment, self.min_increase_factor)
                    # Smooth increase for orders between furthest and closest (see docstring example)
                    new_order_amount = min(further_bound, order_amount * increase_factor)

                    return self._increase_single_order(asset, asset_balance, order, new_order_amount)

        elif (
            self.mode == 'valley'
            or (self.mode == 'buy_slope' and asset == 'base')
            or (self.mode == 'sell_slope' and asset == 'quote')
        ):
            """
            Starting from the furthest order, for each order, see if it is approximately maximum size. If it is, move on
            to next. If not, cancel it and replace with maximum size order. Maximum order size will be a size of closer-
            to-center order. Then return. If furthest is reached, increase it to maximum size.

            Maximum size is (example for buy orders):
            1. As many "base" as the further order (further_order_bound)
            2. As many "base" as the order closer to center (closer_order_bound)
            """
            orders_count = len(orders)
            orders = list(reversed(orders))

            # To speed up the process, use at least N% increases
            increase_factor = max(1 + self.increment, self.min_increase_factor)

            closest_order = orders[-1]
            closest_order_bound = closest_order['base']['amount'] * increase_factor

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
                    """
                    Special processing for the closest order.

                    Calculate new order amount based on orders count, but do not allow to perform too small increase
                    rounds. New lowest buy / highest sell should be higher by at least one increment.
                    """
                    closer_order_bound = closest_order_bound
                    new_amount = (total_balance / orders_count) / (1 + self.increment / 100)
                    if furthest_order_bound < new_amount > closer_order_bound:
                        # Maximize order up to max possible amount if we can
                        closer_order_bound = closest_order_bound = new_amount

                order_amount_normalized = order_amount * (1 + self.increment / 10)
                need_increase = False

                if (
                    order_amount_normalized < further_order_bound
                    and further_order_bound - order_amount >= order_amount * self.increment / 2
                    and order_amount_normalized < closest_order_bound
                ):
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

                    # Do not allow to increase more than further order amount
                    new_order_amount = min(closer_order_bound * increase_factor, further_order_bound)

                    if new_order_amount < order_amount_normalized:
                        # Skip order if new amount is less than current for any reason
                        need_increase = False

                elif (
                    order_amount_normalized < closer_order_bound
                    and order_amount_normalized < closest_order_bound
                    and closer_order_bound - order_amount >= order_amount * self.increment / 2
                ):
                    """
                    Check whether order amount is less than closer or order and the diff is more than 50% of one
                    increment. Note: we can use only 50% or less diffs. Bigger will not work. For example, with diff 80%
                    an order may have an actual difference like 30% from closer and 70% from further.

                    Also prevent moving liqudity away from closer-to-center orders. Instead of increasing "80"
                    orders, increase closer-to-center orders first:

                    [80 80 80 100 100 100 60 50 40 40]
                    [80 80 80 100 100 100 60 50 50 40]
                    [80 80 80 100 100 100 60 50 50 50]
                    ...
                    [80 80 80 100 100 100 60 60 60 60]
                    ...
                    [80 80 80 100 100 100 80 80 80 80]
                    """
                    new_order_amount = min(closest_order_bound, closer_order_bound)
                    need_increase = True

                if need_increase:
                    return self._increase_single_order(asset, asset_balance, order, new_order_amount)

        elif self.mode == 'neutral':
            """
            Starting from the furthest order, for each order, see if it is approximately maximum size. If it is, move on
            to next. If not, cancel it and replace with maximum size order. Maximum order size will be a size of closer-
            to-center order. Then return. If furthest is reached, increase it to maximum size.

            Maximum size is (example for buy orders):
            1. As many "base * sqrt(1 + increment)" as the further order (further_order_bound)
            2. As many "base / sqrt(1 + increment)" as the order closer to center (closer_order_bound)
            """

            orders_count = len(orders)
            orders = list(reversed(orders))
            closest_order = orders[-1]
            increase_factor = max(1 + self.increment, self.min_increase_factor)
            initial_closest_order_bound = closest_order['base']['amount'] * increase_factor

            for order in orders:
                order_index = orders.index(order)
                reverse_index = orders_count - order_index
                order_amount = order['base']['amount']
                closest_order_bound = initial_closest_order_bound

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
                    # What size current order may be based on initial closest order bound
                    closest_order_bound = initial_closest_order_bound / (math.sqrt(1 + self.increment) ** reverse_index)
                else:
                    is_closest_order = True
                    closer_order_bound = initial_closest_order_bound

                need_increase = False
                order_amount_normalized = order_amount * (1 + self.increment / 10)

                if (
                    order_amount_normalized < further_order_bound
                    and order_amount_normalized < closest_order_bound
                    and further_order_bound - order_amount >= order_amount * (math.sqrt(1 + self.increment) - 1) / 2
                ):
                    # Order is less than further order and diff is more than `increment / 2`
                    # Order is also less than previously calculated closest_order_bound
                    if is_closest_order:
                        # At first, maximize order up to further_order_bound
                        new_order_amount = min(closer_order_bound, further_order_bound)
                    else:
                        # Current order is less than virtually calculated next order (closest_order_bound)
                        # Do not allow to increase more than further order amount
                        new_order_amount = min(order['base']['amount'] * increase_factor, further_order_bound)
                    need_increase = True

                elif (
                    order_amount_normalized < closer_order_bound
                    and order_amount_normalized < closest_order_bound
                    and closer_order_bound - order_amount >= order_amount * (math.sqrt(1 + self.increment) - 1) / 2
                ):
                    # Order is less than closer order and diff is more than `increment / 2`
                    # Order is also less than virtually calculated closest_order_bound, this prevents moving liquidity
                    # away from center, see similar code in Valley mode for description
                    new_order_amount = min(closer_order_bound, closest_order_bound)
                    need_increase = True

                if need_increase:
                    return self._increase_single_order(asset, asset_balance, order, new_order_amount)

    def increase_order_sizes(self, asset, asset_balance, orders):
        """
        Checks which order should be increased in size and replaces it with a maximum size order, according to global
        limits. Logic depends on mode in question.

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

        :param str asset: 'base' or 'quote', depending if checking sell or buy
        :param Amount asset_balance: Balance of the account
        :param list orders: List of buy or sell orders
        :return: status of funds allocation
                done = all funds were allocated
                done_with_ops = all funds were allocated, operations are pending in txbuffer
                in_progress = not all funds were allocated, can increase more orders next time
        :rtype: str
        """

        # Create temp order list (copy.deepcopy() doesn't work here)
        temp_orders = []
        for order in orders:
            tmp_order = {
                'base': {'amount': order['base']['amount']},
                'quote': {'amount': order['quote']['amount']},
                'for_sale': {'amount': order['for_sale']['amount']},
                'price': order['price'],
            }
            temp_orders.append(tmp_order)

        # Get calculated increased orders
        increase_finished = False
        while not increase_finished:
            increase_finished = self._calc_increase(asset, asset_balance, temp_orders)

        price = 0
        order_type = ''
        symbol = ''
        opposite_symbol = ''
        precision = 0
        opposite_precision = 0
        ops_num = 0

        if asset == 'quote':
            order_type = 'sell'
            symbol = self.market['quote']['symbol']
            opposite_symbol = self.market['base']['symbol']
            precision = self.market['quote']['precision']
            opposite_precision = self.market['base']['precision']
        elif asset == 'base':
            order_type = 'buy'
            symbol = self.market['base']['symbol']
            opposite_symbol = self.market['quote']['symbol']
            precision = self.market['base']['precision']
            opposite_precision = self.market['quote']['precision']

        # We're iterating in reverse manner to place further orders first
        orders = list(reversed(orders))
        temp_orders = list(reversed(temp_orders))

        for index, order in enumerate(temp_orders):
            if order['base']['amount'] != orders[index]['base']['amount']:
                price = order['price'] if asset == 'base' else order['price'] ** -1
                old_amount = orders[index]['base']['amount']
                new_amount = order['base']['amount']
                old_opposite_amount = orders[index]['quote']['amount']
                new_opposite_amount = order['quote']['amount']
                self.log.info(
                    'Increasing {} order at price {:.8f}: {:.{prec}f} -> {:.{prec}f} {} '
                    '({:.{opposite_prec}f} -> {:.{opposite_prec}f} {})'.format(
                        order_type,
                        price,
                        old_amount,
                        new_amount,
                        symbol,
                        old_opposite_amount,
                        new_opposite_amount,
                        opposite_symbol,
                        prec=precision,
                        opposite_prec=opposite_precision,
                    )
                )
                self.log.debug(
                    'Cancelling {} order in increase_order_sizes(); mode: {}, amount: {}, price: {:.8f}'.format(
                        order_type, self.mode, old_amount, price
                    )
                )
                self.cancel_orders_wrapper(orders[index])

                if asset == 'quote':
                    if isinstance(orders[index], VirtualOrder):
                        self.place_virtual_sell_order(order['base']['amount'], price)
                    else:
                        self.place_market_sell_order(order['base']['amount'], price)
                elif asset == 'base':
                    if isinstance(orders[index], VirtualOrder):
                        self.place_virtual_buy_order(order['quote']['amount'], price)
                    else:
                        self.place_market_buy_order(order['quote']['amount'], price)

                # Limit number of operations to send at once
                ops_num = len(self.bitshares.txbuffer.ops)
                if ops_num > 10:
                    return 'in_progress'

        if 0 < ops_num < 10:
            return 'done_with_ops'

        # All funds were used
        return 'done'

    def check_partial_fill(self, order, fill_threshold=None):
        """
        Checks whether order was partially filled it needs to be replaced.

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
                self.log.debug(
                    'Partially filled {} order: {} {} @ {:.8f}, filled: {:.2%}'.format(
                        order_type, order['base']['amount'], order['base']['symbol'], price, diff_rel
                    )
                )
                return False
        return True

    def replace_partially_filled_order(self, order):
        """
        Replace partially filled order.

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
                self.refresh_balances()
        else:
            needed = order['base']['amount'] - order['for_sale']['amount']
            self.log.debug(
                'Unable to replace partially filled {} order: avail/needed: {:.{prec}f}/{:.{prec}f} {}'.format(
                    order_type, asset_balance['amount'], needed, order['base']['symbol'], prec=precision
                )
            )

    def place_closer_order(
        self, asset, order, place_order=True, allow_partial=False, own_asset_limit=None, opposite_asset_limit=None
    ):
        """
        Place order closer to the center.

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
        precision = 0

        # Define asset-dependent variables
        if asset == 'base':
            order_type = 'buy'
            balance = self.base_balance['amount']
            symbol = self.base_balance['symbol']
            precision = self.market['base']['precision']
        elif asset == 'quote':
            order_type = 'sell'
            balance = self.quote_balance['amount']
            symbol = self.quote_balance['symbol']
            precision = self.market['quote']['precision']

        # Check for instant fill
        if asset == 'base':
            price = order['price'] * (1 + self.increment)
            lowest_ask = float(self.ticker().get('lowestAsk'))
            if not self.is_instant_fill_enabled and price > lowest_ask and lowest_ask > 0 and place_order:
                self.log.info('Refusing to place an order which crosses lowest ask')
                return None
            if price > self.upper_bound:
                self.log.warning('Refusing to place buy order which crosses upper bound')
                return None
        elif asset == 'quote':
            price = (order['price'] ** -1) / (1 + self.increment)
            highest_bid = float(self.ticker().get('highestBid'))
            if not self.is_instant_fill_enabled and price < highest_bid and highest_bid > 0 and place_order:
                self.log.info('Refusing to place an order which crosses highest bid')
                return None
            if price < self.lower_bound:
                self.log.warning('Refusing to place sell order which crosses lower bound')
                return None

        # For next steps we do not need inverted price for sell orders
        price = order['price'] * (1 + self.increment)

        # Calculate new order amounts depending on mode
        opposite_asset_amount = 0
        own_asset_amount = 0
        if (
            self.mode == 'mountain'
            or (self.mode == 'buy_slope' and asset == 'quote')
            or (self.mode == 'sell_slope' and asset == 'base')
        ):
            opposite_asset_amount = order['quote']['amount']
            own_asset_amount = opposite_asset_amount * price
        elif (
            self.mode == 'valley'
            or (self.mode == 'buy_slope' and asset == 'base')
            or (self.mode == 'sell_slope' and asset == 'quote')
        ):
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
            base_amount = limiter = own_asset_amount
            quote_amount = opposite_asset_amount
        elif asset == 'quote':
            quote_amount = limiter = own_asset_amount
            price = price ** -1

        # Check whether new order will excess the limiter. Limiter is set based on own_aseet_limit or
        # opposite_asset_limit kwargs
        if balance < limiter:
            missing = limiter - balance
            if allow_partial or (
                # Accept small inaccuracy for full-sized closer order
                place_order
                and not allow_partial
                and missing / limiter < 0.05
            ):
                self.log.debug(
                    'Limiting {} order amount to available asset balance: {:.{prec}f} {}'.format(
                        order_type, balance, symbol, prec=precision
                    )
                )
                if asset == 'base':
                    quote_amount = balance / price
                elif asset == 'quote':
                    quote_amount = balance
            elif place_order and not allow_partial:
                self.log.debug(
                    'Not enough balance to place closer {} order; need/avail: {:.{prec}f}/{:.{prec}f}'.format(
                        order_type, limiter, balance, prec=precision
                    )
                )
                place_order = False

        # Make sure new order is bigger than allowed minimum
        hard_limit = 0
        if place_order:
            corrected_quote_amount = self.check_min_order_size(quote_amount, price)
            if corrected_quote_amount > quote_amount:
                self.log.debug('Correcting closer order amount to minimal allowed')
                quote_amount = corrected_quote_amount
                base_amount = quote_amount * price
                if asset == 'base':
                    hard_limit = base_amount
                elif asset == 'quote':
                    hard_limit = quote_amount
            if balance < hard_limit:
                self.log.debug(
                    'Not enough balance to place minimal allowed order: {:.{prec}f}/{:.{prec}f} {}'.format(
                        balance, hard_limit, symbol, prec=precision
                    )
                )
                place_order = False

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
        """
        Place order further from specified order.

        :param asset:
        :param order: furthest buy or sell order
        :param bool | place_order: True = Places order to the market, False = returns amount and price
        :param bool | allow_partial: True = Allow to downsize order whether there is not enough balance
        :param bool | virtual: True = Force place a virtual order
        """
        balance = 0
        order_type = ''
        symbol = ''
        precision = 0
        virtual_bound = self.market_center_price / math.sqrt(1 + self.target_spread)

        # Define asset-dependent variables
        if asset == 'base':
            order_type = 'buy'
            balance = self.base_balance['amount']
            symbol = self.base_balance['symbol']
            precision = self.market['base']['precision']
        elif asset == 'quote':
            order_type = 'sell'
            balance = self.quote_balance['amount']
            symbol = self.quote_balance['symbol']
            precision = self.market['quote']['precision']

        price = order['price'] / (1 + self.increment)

        # Calculate new order amounts depending on mode
        opposite_asset_amount = 0
        own_asset_amount = 0
        if (
            self.mode == 'mountain'
            or (self.mode == 'buy_slope' and asset == 'quote')
            or (self.mode == 'sell_slope' and asset == 'base')
        ):
            opposite_asset_amount = order['quote']['amount']
            own_asset_amount = opposite_asset_amount * price
        elif (
            self.mode == 'valley'
            or (self.mode == 'buy_slope' and asset == 'base')
            or (self.mode == 'sell_slope' and asset == 'quote')
        ):
            own_asset_amount = order['base']['amount']
            opposite_asset_amount = own_asset_amount / price
        elif self.mode == 'neutral':
            own_asset_amount = order['base']['amount'] / math.sqrt(1 + self.increment)
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
                self.log.debug(
                    'Not enough balance to place further {} order; need/avail: {:.{prec}f}/{:.{prec}f}'.format(
                        order_type, limiter, balance, prec=precision
                    )
                )
                place_order = False
            elif allow_partial:
                self.log.debug(
                    'Limiting {} order amount to available asset balance: {:.{prec}f} {}'.format(
                        order_type, balance, symbol, prec=precision
                    )
                )
                if asset == 'base':
                    quote_amount = balance / price
                elif asset == 'quote':
                    quote_amount = balance

        # Make sure new order is bigger than allowed minimum
        hard_limit = 0
        if place_order:
            corrected_quote_amount = self.check_min_order_size(quote_amount, price)
            if corrected_quote_amount > quote_amount:
                self.log.debug('Correcting further order amount to minimal allowed')
                quote_amount = corrected_quote_amount
                base_amount = quote_amount * price
                if asset == 'base':
                    hard_limit = base_amount
                elif asset == 'quote':
                    hard_limit = quote_amount
            if balance < hard_limit:
                self.log.debug(
                    'Not enough balance to place minimal allowed order: {:.{prec}f}/{:.{prec}f} {}'.format(
                        balance, hard_limit, symbol, prec=precision
                    )
                )
                place_order = False

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
        """
        Places sell order furthest to the market center price.

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
                'price: {:.8f}, closest order price: {:.8f}, upper_bound: {:.8f}'.format(
                    market_center_price, price, self.upper_bound
                )
            )
            return

        sell_orders_count = self.calc_sell_orders_count(price, self.upper_bound)

        if self.fee_asset['id'] == self.market['quote']['id']:
            buy_orders_count = self.calc_buy_orders_count(price, self.lower_bound)
            fee = self.get_order_creation_fee(self.fee_asset)
            real_orders_count = min(buy_orders_count, self.operational_depth) + min(
                sell_orders_count, self.operational_depth
            )
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
            # Make sure new order is bigger than allowed minimum
            corrected_amount = self.check_min_order_size(amount_quote, price)
            if corrected_amount > amount_quote:
                if quote_balance >= corrected_amount:
                    self.log.warning('Placing increased order because calculated size is less than allowed minimum')
                    amount_quote = corrected_amount
                else:
                    self.log.debug('Insufficient balance to place sell order')
                    return

            if sell_orders_count > self.operational_depth:
                order = self.place_virtual_sell_order(amount_quote, price)
            else:
                order = self.place_market_sell_order(amount_quote, price)
        else:
            order = {"amount": amount_quote, "price": price}

        return order

    def place_lowest_buy_order(self, base_balance, place_order=True, market_center_price=None):
        """
        Places buy order furthest to the market center price.

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
                '{:.8f}, closest order price: {:.8f}, lower bound: {:.8f}'.format(
                    market_center_price, price, self.lower_bound
                )
            )
            return

        buy_orders_count = self.calc_buy_orders_count(price, self.lower_bound)

        if self.fee_asset['id'] == self.market['base']['id']:
            fee = self.get_order_creation_fee(self.fee_asset)
            sell_orders_count = self.calc_sell_orders_count(price, self.upper_bound)
            real_orders_count = min(buy_orders_count, self.operational_depth) + min(
                sell_orders_count, self.operational_depth
            )
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
            # Make sure new order is bigger than allowed minimum
            corrected_amount = self.check_min_order_size(amount_quote, price)
            if corrected_amount > amount_quote:
                if base_balance >= corrected_amount:
                    self.log.warning('Placing increased order because calculated size is less than allowed minimum')
                    amount_quote = corrected_amount
                else:
                    self.log.debug('Insufficient balance to place buy order')
                    return

            if buy_orders_count > self.operational_depth:
                order = self.place_virtual_buy_order(amount_quote, price)
            else:
                order = self.place_market_buy_order(amount_quote, price)
        else:
            order = {"amount": amount_quote, "price": price}

        return order

    def calc_buy_orders_count(self, price_high, price_low):
        """
        Calculate number of buy orders to place between high price and low price.

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
        """
        Calculate number of sell orders to place between low price and high price.

        :param float | price_low: Lowest sell price bound
        :param float | price_high: Highest sell price bound
        :return int | count: Returns number of orders
        """
        orders_count = 0
        while price_low <= price_high:
            orders_count += 1
            price_low = price_low * (1 + self.increment)
        return orders_count

    def check_min_order_size(self, amount, price):
        """
        Check if order size is less than minimal allowed size.

        :param float | amount: Order amount in QUOTE
        :param float | price: Order price in BASE
        :return float | new_amount: passed amount or minimal allowed amount
        """
        # Calculate minimal orders amounts based on asset precision
        if not self.order_min_base or not self.order_min_quote:
            self.calculate_min_amounts()

        if amount < self.order_min_quote or amount * price < self.order_min_base:
            self.log.debug(
                'Too small order, base: {:.8f}/{:.8f}, quote: {}/{}'.format(
                    amount * price, self.order_min_base, amount, self.order_min_quote
                )
            )
            return max(self.order_min_quote, self.order_min_base / price)
        return amount

    def place_virtual_buy_order(self, amount, price):
        """
        Place a virtual buy order.

        :param float | amount: Order amount in QUOTE
        :param float | price: Order price in BASE
        :return dict | order: Returns virtual order instance
        """
        symbol = self.market['base']['symbol']
        order = VirtualOrder()
        order['id'] = str(uuid.uuid4())

        precise_quote_amount = round(amount, self.market['quote']['precision'])
        quote_asset = Amount(precise_quote_amount, self.market['quote']['symbol'], bitshares_instance=self.bitshares)
        order['quote'] = quote_asset

        precise_base_amount = round(amount * price, self.market['base']['precision'])
        base_asset = Amount(precise_base_amount, self.market['base']['symbol'], bitshares_instance=self.bitshares)
        order['base'] = base_asset
        order['for_sale'] = base_asset
        order['price'] = precise_base_amount / precise_quote_amount

        self.log.info(
            'Placing a virtual buy order with {:.{prec}f} {} @ {:.8f}'.format(
                order['base']['amount'], symbol, order['price'], prec=self.market['base']['precision']
            )
        )
        self.virtual_orders.append(order)

        # Immediately lower avail balance
        self.base_balance['amount'] -= order['base']['amount']

        self.save_order_extended(order, virtual=True, custom='current')

        return order

    def place_virtual_sell_order(self, amount, price):
        """
        Place a virtual sell order.

        :param float | amount: Order amount in QUOTE
        :param float | price: Order price in BASE
        :return dict | order: Returns virtual order instance
        """
        symbol = self.market['quote']['symbol']
        order = VirtualOrder()
        order['id'] = str(uuid.uuid4())

        precise_quote_amount = round(amount * price, self.market['base']['precision'])
        quote_asset = Amount(precise_quote_amount, self.market['base']['symbol'], bitshares_instance=self.bitshares)
        order['quote'] = quote_asset

        precise_base_amount = round(amount, self.market['quote']['precision'])
        base_asset = Amount(precise_base_amount, self.market['quote']['symbol'], bitshares_instance=self.bitshares)
        order['base'] = base_asset
        order['for_sale'] = base_asset
        order['price'] = precise_base_amount / precise_quote_amount

        self.log.info(
            'Placing a virtual sell order with {:.{prec}f} {} @ {:.8f}'.format(
                amount, symbol, order['price'] ** -1, prec=self.market['quote']['precision']
            )
        )
        self.virtual_orders.append(order)

        # Immediately lower avail balance
        self.quote_balance['amount'] -= order['base']['amount']

        self.save_order_extended(order, virtual=True, custom='current')

        return order

    def cancel_orders_wrapper(self, orders, **kwargs):
        """
        Cancel specific order(s)

        :param list orders: list of orders to cancel
        """
        if not isinstance(orders, (list, set, tuple)):
            orders = [orders]

        virtual_orders = [order for order in orders if isinstance(order, VirtualOrder)]
        real_orders = [order for order in orders if not isinstance(order, VirtualOrder)]

        if virtual_orders:
            # Just rebuild virtual orders list to avoid calling Asset's __eq__ method
            self.virtual_orders = [order for order in self.virtual_orders if order not in virtual_orders]
            # Also remove virtual order from database
            for order in virtual_orders:
                self.remove_order(order)

        if real_orders:
            return self.cancel_orders(real_orders, **kwargs)

        return True

    def error(self, *args, **kwargs):
        self.disabled = True

    def pause(self):
        """Override pause()"""

    def purge(self):
        """ We are not cancelling orders on save/remove worker from the GUI
            TODO: don't work yet because worker removal is happening via BaseStrategy staticmethod
        """

    def tick(self, d):
        """Ticks come in on every block."""
        if not (self.counter or 0) % 3:
            self.maintain_strategy()
        self.counter += 1


class VirtualOrder(dict):
    """Wrapper class to handle virtual orders comparison in list index() method."""

    def __float__(self):
        return self['price']
