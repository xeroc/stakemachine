import datetime
import copy
import collections
import logging
import math
import time

from dexbot.config import Config
from dexbot.storage import Storage
from dexbot.statemachine import StateMachine
from dexbot.helper import truncate

from events import Events
import bitshares.exceptions
import bitsharesapi
import bitsharesapi.exceptions
from bitshares.account import Account
from bitshares.amount import Amount, Asset
from bitshares.instance import shared_bitshares_instance
from bitshares.market import Market
from bitshares.price import FilledOrder, Order, UpdateCallOrder

# Number of maximum retries used to retry action before failing
MAX_TRIES = 3

""" Strategies need to specify their own configuration values, so each strategy can have a class method 'configure' 
    which returns a list of ConfigElement named tuples.
    
    Tuple fields as follows:
        - Key: The key in the bot config dictionary that gets saved back to config.yml
        - Type: "int", "float", "bool", "string" or "choice"
        - Default: The default value, must be same type as the Type defined
        - Title: Name shown to the user, preferably not too long
        - Description: Comments to user, full sentences encouraged
        - Extra:
              :int: a (min, max, suffix) tuple
              :float: a (min, max, precision, suffix) tuple
              :string: a regular expression, entries must match it, can be None which equivalent to .*
              :bool, ignored
              :choice: a list of choices, choices are in turn (tag, label) tuples.
              labels get presented to user, and tag is used as the value saved back to the config dict
"""
ConfigElement = collections.namedtuple('ConfigElement', 'key type default title description extra')


class StrategyBase(Storage, StateMachine, Events):
    """ A strategy based on this class is intended to work in one market. This class contains
        most common methods needed by the strategy.

        All prices are passed and returned as BASE/QUOTE.
        (In the BREAD:USD market that would be USD/BREAD, 2.5 USD / 1 BREAD).
         - Buy orders reserve BASE
         - Sell orders reserve QUOTE

        Todo: This is copy / paste from old, update this if needed!
        Strategy inherits:
            * :class:`dexbot.storage.Storage` : Stores data to sqlite database
            * :class:`dexbot.statemachine.StateMachine`
            * ``Events``

        Todo: This is copy / paste from old, update this if needed!
        Available attributes:
            * ``worker.bitshares``: instance of ´`bitshares.BitShares()``
            * ``worker.add_state``: Add a specific state
            * ``worker.set_state``: Set finite state machine
            * ``worker.get_state``: Change state of state machine
            * ``worker.account``: The Account object of this worker
            * ``worker.market``: The market used by this worker
            * ``worker.orders``: List of open orders of the worker's account in the worker's market
            * ``worker.balance``: List of assets and amounts available in the worker's account
            * ``worker.log``: a per-worker logger (actually LoggerAdapter) adds worker-specific context:
                worker name & account (Because some UIs might want to display per-worker logs)

        Also, Worker inherits :class:`dexbot.storage.Storage`
        which allows to permanently store data in a sqlite database
        using:

        ``worker["key"] = "value"``

        .. note:: This applies a ``json.loads(json.dumps(value))``!

        Workers must never attempt to interact with the user, they must assume they are running unattended.
        They can log events. If a problem occurs they can't fix they should set self.disabled = True and
        throw an exception. The framework catches all exceptions thrown from event handlers and logs appropriately.
    """

    __events__ = [
        'onAccount',
        'onMarketUpdate',
        'onOrderMatched',
        'onOrderPlaced',
        'ontick',
        'onUpdateCallOrder',
        'error_onAccount',
        'error_onMarketUpdate',
        'error_ontick',
    ]

    @classmethod
    def configure(cls, return_base_config=True):
        """ Return a list of ConfigElement objects defining the configuration values for this class.

            User interfaces should then generate widgets based on these values, gather data and save back to
            the config dictionary for the worker.

            NOTE: When overriding you almost certainly will want to call the ancestor and then
            add your config values to the list.

            :param return_base_config: bool:
            :return: Returns a list of config elements
        """

        # Common configs
        base_config = [
            ConfigElement('account', 'string', '', 'Account',
                          'BitShares account name for the bot to operate with',
                          ''),
            ConfigElement('market', 'string', 'USD:BTS', 'Market',
                          'BitShares market to operate on, in the format ASSET:OTHERASSET, for example \"USD:BTS\"',
                          r'[A-Z\.]+[:\/][A-Z\.]+'),
            ConfigElement('fee_asset', 'string', 'BTS', 'Fee asset',
                          'Asset to be used to pay transaction fees',
                          r'[A-Z\.]+')
        ]

        # Todo: Is there any case / strategy where the base config would NOT be needed, making this unnecessary?
        if return_base_config:
            return base_config
        return []

    def __init__(self,
                 name,
                 config=None,
                 onAccount=None,
                 onOrderMatched=None,
                 onOrderPlaced=None,
                 onMarketUpdate=None,
                 onUpdateCallOrder=None,
                 ontick=None,
                 bitshares_instance=None,
                 *args,
                 **kwargs):

        # BitShares instance
        self.bitshares = bitshares_instance or shared_bitshares_instance()

        # Storage
        Storage.__init__(self, name)

        # Statemachine
        StateMachine.__init__(self, name)

        # Events
        Events.__init__(self)

        if ontick:
            self.ontick += ontick
        if onMarketUpdate:
            self.onMarketUpdate += onMarketUpdate
        if onAccount:
            self.onAccount += onAccount
        if onOrderMatched:
            self.onOrderMatched += onOrderMatched
        if onOrderPlaced:
            self.onOrderPlaced += onOrderPlaced
        if onUpdateCallOrder:
            self.onUpdateCallOrder += onUpdateCallOrder

        # Redirect this event to also call order placed and order matched
        self.onMarketUpdate += self._callbackPlaceFillOrders

        if config:
            self.config = config
        else:
            self.config = config = Config.get_worker_config_file(name)

        # Get worker's parameters from the config
        self.worker = config["workers"][name]

        # Get Bitshares account and market for this worker
        self._account = Account(self.worker["account"], full=True, bitshares_instance=self.bitshares)
        self._market = Market(config["workers"][name]["market"], bitshares_instance=self.bitshares)

        # Recheck flag - Tell the strategy to check for updated orders
        self.recheck_orders = False

        # Set fee asset
        fee_asset_symbol = self.worker.get('fee_asset')

        if fee_asset_symbol:
            try:
                self.fee_asset = Asset(fee_asset_symbol)
            except bitshares.exceptions.AssetDoesNotExistsException:
                self.fee_asset = Asset('1.3.0')
        else:
            # If there is no fee asset, use BTS
            self.fee_asset = Asset('1.3.0')

        # Settings for bitshares instance
        self.bitshares.bundle = bool(self.worker.get("bundle", False))

        # Disabled flag - this flag can be flipped to True by a worker and will be reset to False after reset only
        self.disabled = False

        # Order expiration time in seconds
        self.expiration = 60 * 60 * 24 * 365 * 5

        # A private logger that adds worker identify data to the LogRecord
        self.log = logging.LoggerAdapter(
            logging.getLogger('dexbot.per_worker'),
            {
                'worker_name': name,
                'account': self.worker['account'],
                'market': self.worker['market'],
                'is_disabled': lambda: self.disabled
            }
        )

        self.orders_log = logging.LoggerAdapter(
            logging.getLogger('dexbot.orders_log'), {}
        )

    def _calculate_center_price(self, suppress_errors=False):
        """

            :param suppress_errors:
            :return:
        """
        # Todo: Add documentation
        ticker = self.market.ticker()
        highest_bid = ticker.get("highestBid")
        lowest_ask = ticker.get("lowestAsk")

        if highest_bid is None or highest_bid == 0.0:
            if not suppress_errors:
                self.log.critical(
                    "Cannot estimate center price, there is no highest bid."
                )
                self.disabled = True
            return None
        elif lowest_ask is None or lowest_ask == 0.0:
            if not suppress_errors:
                self.log.critical(
                    "Cannot estimate center price, there is no lowest ask."
                )
                self.disabled = True
            return None

        center_price = highest_bid['price'] * math.sqrt(lowest_ask['price'] / highest_bid['price'])
        return center_price

    def _callbackPlaceFillOrders(self, d):
        """ This method distinguishes notifications caused by Matched orders from those caused by placed orders
            Todo: can this be renamed to _instantFill()?
        """
        # Todo: Add documentation
        if isinstance(d, FilledOrder):
            self.onOrderMatched(d)
        elif isinstance(d, Order):
            self.onOrderPlaced(d)
        elif isinstance(d, UpdateCallOrder):
            self.onUpdateCallOrder(d)
        else:
            pass

    def _cancel_orders(self, orders):
        """

            :param orders:
            :return:
        """
        # Todo: Add documentation
        try:
            self.retry_action(
                self.bitshares.cancel,
                orders, account=self.account, fee_asset=self.fee_asset['id']
            )
        except bitsharesapi.exceptions.UnhandledRPCError as exception:
            if str(exception).startswith('Assert Exception: maybe_found != nullptr: Unable to find Object'):
                # The order(s) we tried to cancel doesn't exist
                self.bitshares.txbuffer.clear()
                return False
            else:
                self.log.exception("Unable to cancel order")
        except bitshares.exceptions.MissingKeyError:
            self.log.exception('Unable to cancel order(s), private key missing.')

        return True

    def account_total_value(self, return_asset):
        """ Returns the total value of the account in given asset

            :param string | return_asset: Balance is returned as this asset
            :return: float: Value of the account in one asset
        """
        total_value = 0

        # Total balance calculation
        for balance in self.balances:
            if balance['symbol'] != return_asset:
                # Convert to asset if different
                total_value += self.convert_asset(balance['amount'], balance['symbol'], return_asset)
            else:
                total_value += balance['amount']

        # Orders balance calculation
        for order in self.all_own_orders:
            updated_order = self.get_updated_order(order['id'])

            if not order:
                continue
            if updated_order['base']['symbol'] == return_asset:
                total_value += updated_order['base']['amount']
            else:
                total_value += self.convert_asset(
                    updated_order['base']['amount'],
                    updated_order['base']['symbol'],
                    return_asset
                )

        return total_value

    def balance(self, asset, fee_reservation=False):
        """ Return the balance of your worker's account for a specific asset

            :param bool | fee_reservation:
            :return: Balance of specific asset
        """
        # Todo: Add documentation
        return self._account.balance(asset)

    def calculate_center_price(self, center_price=None, asset_offset=False, spread=None,
                               order_ids=None, manual_offset=0, suppress_errors=False):
        # Todo: Fix comment
        """ Calculate center price which shifts based on available funds
        """
        if center_price is None:
            # No center price was given so we simply calculate the center price
            calculated_center_price = self._calculate_center_price(suppress_errors)
        else:
            # Center price was given so we only use the calculated center price
            # for quote to base asset conversion
            calculated_center_price = self._calculate_center_price(True)
            if not calculated_center_price:
                calculated_center_price = center_price

        if center_price:
            calculated_center_price = center_price

        if asset_offset:
            total_balance = self.get_allocated_assets(order_ids)
            total = (total_balance['quote'] * calculated_center_price) + total_balance['base']

            if not total:  # Prevent division by zero
                balance = 0
            else:
                # Returns a value between -1 and 1
                balance = (total_balance['base'] / total) * 2 - 1

            if balance < 0:
                # With less of base asset center price should be offset downward
                calculated_center_price = calculated_center_price / math.sqrt(1 + spread * (balance * -1))
            elif balance > 0:
                # With more of base asset center price will be offset upwards
                calculated_center_price = calculated_center_price * math.sqrt(1 + spread * balance)
            else:
                calculated_center_price = calculated_center_price

        # Calculate final_offset_price if manual center price offset is given
        if manual_offset:
            calculated_center_price = calculated_center_price + (calculated_center_price * manual_offset)

        return calculated_center_price

    def calculate_order_data(self, order, amount, price):
        quote_asset = Amount(amount, self.market['quote']['symbol'])
        order['quote'] = quote_asset
        order['price'] = price
        base_asset = Amount(amount * price, self.market['base']['symbol'])
        order['base'] = base_asset
        return order

    def calculate_worker_value(self, unit_of_measure, refresh=True):
        """ Returns the combined value of allocated and available QUOTE and BASE, measured in "unit_of_measure".

            :param unit_of_measure:
            :param refresh:
            :return:
        """
        # Todo: Insert logic here

    def cancel_all_orders(self):
        """ Cancel all orders of the worker's account
        """
        self.log.info('Canceling all orders')

        if self.all_own_orders:
            self.cancel(self.all_own_orders)

        self.log.info("Orders canceled")

    def cancel_orders(self, orders, batch_only=False):
        """ Cancel specific order(s)

            :param list | orders: List of orders to cancel
            :param bool | batch_only: Try cancel orders only in batch mode without one-by-one fallback
            :return:
        """
        # Todo: Add documentation
        if not isinstance(orders, (list, set, tuple)):
            orders = [orders]

        orders = [order['id'] for order in orders if 'id' in order]

        success = self._cancel_orders(orders)
        if not success and batch_only:
            return False
        if not success and len(orders) > 1 and not batch_only:
            # One of the order cancels failed, cancel the orders one by one
            for order in orders:
                self._cancel_orders(order)
        return True

    def count_asset(self, order_ids=None, return_asset=False, refresh=True):
        """ Returns the combined amount of the given order ids and the account balance
            The amounts are returned in quote and base assets of the market

            :param list | order_ids: list of order ids to be added to the balance
            :param bool | return_asset: true if returned values should be Amount instances
            :return: dict with keys quote and base
            Todo: When would we want the sum of a subset of orders? Why order_ids? Maybe just specify asset?
        """
        quote = 0
        base = 0
        quote_asset = self.market['quote']['id']
        base_asset = self.market['base']['id']

        # Total balance calculation
        for balance in self.balances:
            if balance.asset['id'] == quote_asset:
                quote += balance['amount']
            elif balance.asset['id'] == base_asset:
                base += balance['amount']

        if order_ids is None:
            # Get all orders from Blockchain
            order_ids = [order['id'] for order in self.current_market_own_orders]
        if order_ids:
            orders_balance = self.orders_balance(order_ids)
            quote += orders_balance['quote']
            base += orders_balance['base']

        if return_asset:
            quote = Amount(quote, quote_asset)
            base = Amount(base, base_asset)

        return {'quote': quote, 'base': base}

    def get_allocated_assets(self, order_ids, return_asset=False, refresh=True):
        # Todo:
        """ Returns the amount of QUOTE and BASE allocated in orders, and that do not show up in available balance

            :param order_ids:
            :param return_asset:
            :param refresh:
            :return:
        """
        # Todo: Add documentation
        if not order_ids:
            order_ids = []
        elif isinstance(order_ids, str):
            order_ids = [order_ids]

        quote = 0
        base = 0
        quote_asset = self.market['quote']['id']
        base_asset = self.market['base']['id']

        for order_id in order_ids:
            order = self.get_updated_order(order_id)
            if not order:
                continue
            asset_id = order['base']['asset']['id']
            if asset_id == quote_asset:
                quote += order['base']['amount']
            elif asset_id == base_asset:
                base += order['base']['amount']

        if return_asset:
            quote = Amount(quote, quote_asset)
            base = Amount(base, base_asset)

        return {'quote': quote, 'base': base}

    def get_lowest_market_sell(self):
        """ Returns the lowest sell order that is not own, regardless of order size.

            :return: order or None: Lowest market sell order.
        """
        orders = self.market.orderbook(1)

        try:
            order = orders['asks'][0]
            self.log.info('Lowest market ask @ {}'.format(order.get('price')))
        except IndexError:
            self.log.info('Market has no lowest ask.')
            return None

        return order

    def get_highest_market_buy(self):
        """ Returns the highest buy order that is not own, regardless of order size.

            :return: order or None: Highest market buy order.
        """
        orders = self.market.orderbook(1)

        try:
            order = orders['bids'][0]
            self.log.info('Highest market bid @ {}'.format(order.get('price')))
        except IndexError:
            self.log.info('Market has no highest bid.')
            return None

        return order

    def get_lowest_own_sell(self, refresh=False):
        """ Returns lowest own sell order.

            :param refresh:
            :return:
        """
        # Todo: Insert logic here

    def get_highest_own_buy(self, refresh=False):
        """ Returns highest own buy order.

            :param refresh:
            :return:
        """
        # Todo: Insert logic here

    def get_price_for_amount_buy(self, amount=None, refresh=False):
        """ Returns the cumulative price for which you could buy the specified amount of QUOTE.
            This method must take into account market fee.

            :param amount:
            :param refresh:
            :return:
        """
        # Todo: Insert logic here

    def get_price_for_amount_sell(self, amount=None, refresh=False):
        """ Returns the cumulative price for which you could sell the specified amount of QUOTE

            :param amount:
            :param refresh:
            :return:
        """
        # Todo: Insert logic here

    def get_external_price(self, source):
        """ Returns the center price of market including own orders.

            :param source:
            :return:
        """
        # Todo: Insert logic here

    def get_market_ask(self, depth=0, moving_average=0, weighted_moving_average=0, refresh=False):
        """ Returns the BASE/QUOTE price for which [depth] worth of QUOTE could be bought, enhanced with moving average
            or weighted moving average

            :param float | depth:
            :param float | moving_average:
            :param float | weighted_moving_average:
            :param bool | refresh:
            :return:
        """
        # Todo: Insert logic here

    def get_market_bid(self, depth=0, moving_average=0, weighted_moving_average=0, refresh=False):
        """ Returns the BASE/QUOTE price for which [depth] worth of QUOTE could be sold, enhanced with moving average or
            weighted moving average.

            Depth = 0 means highest regardless of size

            :param float | depth:
            :param float | moving_average:
            :param float | weighted_moving_average:
            :param bool | refresh:
            :return:
        """
        # Todo: Insert logic here

    def get_market_center_price(self, depth=0, refresh=False):
        """ Returns the center price of market including own orders.

            Depth: 0 = calculate from closest opposite orders.
            Depth: non-zero = calculate from specified depth

            :param float | depth:
            :param bool | refresh:
            :return:
        """
        # Todo: Insert logic here

    def get_market_spread(self, highest_market_buy_price=None, lowest_market_sell_price=None,
                          depth=0, refresh=False):
        """ Returns the market spread %, including own orders, from specified depth, enhanced with moving average or
            weighted moving average

            :param float | highest_market_buy_price:
            :param float | lowest_market_sell_price:
            :param float | depth:
            :param bool | refresh: Use most resent data from Bitshares
            :return: float or None: Market spread
        """
        # Todo: Add depth
        if refresh:
            try:
                # Try fetching orders from market
                highest_market_buy_price = self.get_highest_own_buy().get('price')
                lowest_market_sell_price = self.get_highest_own_buy().get('price')
            except AttributeError:
                # This error is given if there is no market buy or sell order
                return None
        else:
            # If orders are given, use them instead newest data from the blockchain
            highest_market_buy_price = highest_market_buy_price
            lowest_market_sell_price = lowest_market_sell_price

        # Calculate market spread
        market_spread = lowest_market_sell_price / highest_market_buy_price - 1
        return market_spread

    def get_own_spread(self, highest_own_buy_price=None, lowest_own_sell_price=None, depth=0, refresh=False):
        """ Returns the difference between own closest opposite orders.

            :param float | highest_own_buy_price:
            :param float | lowest_own_sell_price:
            :param float | depth: Use most resent data from Bitshares
            :param bool | refresh:
            :return: float or None: Own spread
        """
        # Todo: Add depth
        if refresh:
            try:
                # Try fetching own orders
                highest_own_buy_price = self.get_highest_market_buy().get('price')
                lowest_own_sell_price = self.get_lowest_own_sell().get('price')
            except AttributeError:
                return None
        else:
            # If orders are given, use them instead newest data from the blockchain
            highest_own_buy_price = highest_own_buy_price
            lowest_own_sell_price = lowest_own_sell_price

        # Calculate actual spread
        actual_spread = lowest_own_sell_price / highest_own_buy_price - 1
        return actual_spread

    def get_order_creation_fee(self, fee_asset):
        """ Returns the cost of creating an order in the asset specified

            :param fee_asset: QUOTE, BASE, BTS, or any other
            :return:
        """
        # Todo: Insert logic here

    def get_order_cancellation_fee(self, fee_asset):
        """ Returns the order cancellation fee in the specified asset.
            :param fee_asset:
            :return:
        """
        # Todo: Insert logic here

    def get_market_fee(self, asset):
        """ Returns the fee percentage for buying specified asset.
            :param asset:
            :return: Fee percentage in decimal form (0.025)
        """
        # Todo: Insert logic here

    def get_own_buy_orders(self, sort=None, orders=None):
        # Todo: I might combine this with the get_own_sell_orders and have 2 functions to call it with different returns
        """ Return own buy orders from list of orders. Can be used to pick buy orders from a list
            that is not up to date with the blockchain data. If list of orders is not passed, orders are fetched from
            blockchain.

            :param string | sort: DESC or ASC will sort the orders accordingly, default None.
            :param list | orders: List of orders. If None given get all orders from Blockchain.
            :return list | buy_orders: List of buy orders only.
        """
        buy_orders = []

        if not orders:
            orders = self.current_market_own_orders

        # Find buy orders
        for order in orders:
            if not self.is_sell_order(order):
                buy_orders.append(order)
        if sort:
            buy_orders = self.sort_orders(buy_orders, sort)

        return buy_orders

    def get_own_sell_orders(self, sort=None, orders=None):
        """ Return own sell orders from list of orders. Can be used to pick sell orders from a list
            that is not up to date with the blockchain data. If list of orders is not passed, orders are fetched from
            blockchain.

            :param string | sort: DESC or ASC will sort the orders accordingly, default None.
            :param list | orders: List of orders. If None given get all orders from Blockchain.
            :return list | sell_orders: List of sell orders only.
        """
        sell_orders = []

        if not orders:
            orders = self.current_market_own_orders

        # Find sell orders
        for order in orders:
            if self.is_sell_order(order):
                sell_orders.append(order)

        if sort:
            sell_orders = self.sort_orders(sell_orders, sort)

        return sell_orders

    def get_updated_order(self, order_id):
        # Todo: This needed?
        """ Tries to get the updated order from the API. Returns None if the order doesn't exist

            :param str|dict order_id: blockchain object id of the order
                can be an order dict with the id key in it
        """
        if isinstance(order_id, dict):
            order_id = order_id['id']

        # Get the limited order by id
        order = None
        for limit_order in self.account['limit_orders']:
            if order_id == limit_order['id']:
                order = limit_order
                break
        else:
            return order

        order = self.get_updated_limit_order(order)
        return Order(order, bitshares_instance=self.bitshares)

    def enhance_center_price(self, reference=None, manual_offset=False, balance_based_offset=False,
                             moving_average=0, weighted_average=0):
        """ Returns the passed reference price shifted up or down based on arguments.

            :param float | reference: Center price to enhance
            :param bool | manual_offset:
            :param bool | balance_based_offset:
            :param int or float | moving_average:
            :param int or float | weighted_average:
            :return:
        """
        # Todo: Insert logic here

    def execute_bundle(self):
        # Todo: Is this still needed?
        # Apparently old naming was "execute", and was used by walls strategy.
        """ Execute a bundle of operations
        """
        self.bitshares.blocking = "head"
        r = self.bitshares.txbuffer.broadcast()
        self.bitshares.blocking = False
        return r

    def is_buy_order(self, order):
        """ Checks if the order is a buy order. Returns False if not.

            :param order: Buy / Sell order
            :return:
        """
        if order['base']['symbol'] == self.market['base']['symbol']:
            return True
        return False

    def is_sell_order(self, order):
        """ Checks if the order is Sell order. Returns False if Buy order

            :param order: Buy / Sell order
            :return: bool: True = Sell order, False = Buy order
        """
        if order['base']['symbol'] != self.market['base']['symbol']:
            return True
        return False

    def is_current_market(self, base_asset_id, quote_asset_id):
        """ Returns True if given asset id's are of the current market

            :return: bool: True = Current market, False = Not current market
        """
        if quote_asset_id == self.market['quote']['id']:
            if base_asset_id == self.market['base']['id']:
                return True
            return False
        # Todo: Should we return true if market is opposite?
        if quote_asset_id == self.market['base']['id']:
            if base_asset_id == self.market['quote']['id']:
                return True
            return False
        return False

    def pause_worker(self):
        """ Pause the worker

            Note: By default pause cancels orders, but this can be overridden by strategy
        """
        # Cancel all orders from the market
        self.cancel_all()

        # Removes worker's orders from local database
        self.clear_orders()

    def purge_all_worker_data(self):
        """ Clear all the worker data from the database and cancel all orders
        """
        # Removes worker's orders from local database
        self.clear_orders()

        # Cancel all orders from the market
        self.cancel_all()

        # Finally clear all worker data from the database
        self.clear()

    def place_market_buy_order(self, amount, price, return_none=False, *args, **kwargs):
        """ Places a buy order in the market

            :param float | amount: Order amount in QUOTE
            :param float | price: Order price in BASE
            :param bool | return_none:
            :param args:
            :param kwargs:
            :return:
        """
        symbol = self.market['base']['symbol']
        precision = self.market['base']['precision']
        base_amount = truncate(price * amount, precision)

        # Don't try to place an order of size 0
        if not base_amount:
            self.log.critical('Trying to buy 0')
            self.disabled = True
            return None

        # Make sure we have enough balance for the order
        if self.balance(self.market['base']) < base_amount:
            self.log.critical("Insufficient buy balance, needed {} {}".format(base_amount, symbol))
            self.disabled = True
            return None

        self.log.info('Placing a buy order for {} {} @ {}'.format(base_amount, symbol, round(price, 8)))

        # Place the order
        buy_transaction = self.retry_action(
            self.market.buy,
            price,
            Amount(amount=amount, asset=self.market["quote"]),
            account=self.account.name,
            expiration=self.expiration,
            returnOrderId="head",
            fee_asset=self.fee_asset['id'],
            *args,
            **kwargs
        )

        self.log.debug('Placed buy order {}'.format(buy_transaction))
        buy_order = self.get_order(buy_transaction['orderid'], return_none=return_none)
        if buy_order and buy_order['deleted']:
            # The API doesn't return data on orders that don't exist
            # We need to calculate the data on our own
            buy_order = self.calculate_order_data(buy_order, amount, price)
            self.recheck_orders = True

        return buy_order

    def place_market_sell_order(self, amount, price, return_none=False, *args, **kwargs):
        """ Places a sell order in the market

            :param float | amount: Order amount in QUOTE
            :param float | price: Order price in BASE
            :param bool | return_none:
            :param args:
            :param kwargs:
            :return:
        """
        symbol = self.market['quote']['symbol']
        precision = self.market['quote']['precision']
        quote_amount = truncate(amount, precision)

        # Don't try to place an order of size 0
        if not quote_amount:
            self.log.critical('Trying to sell 0')
            self.disabled = True
            return None

        # Make sure we have enough balance for the order
        if self.balance(self.market['quote']) < quote_amount:
            self.log.critical("Insufficient sell balance, needed {} {}".format(amount, symbol))
            self.disabled = True
            return None

        self.log.info('Placing a sell order for {} {} @ {}'.format(quote_amount, symbol, round(price, 8)))

        # Place the order
        sell_transaction = self.retry_action(
            self.market.sell,
            price,
            Amount(amount=amount, asset=self.market["quote"]),
            account=self.account.name,
            expiration=self.expiration,
            returnOrderId="head",
            fee_asset=self.fee_asset['id'],
            *args,
            **kwargs
        )

        self.log.debug('Placed sell order {}'.format(sell_transaction))
        sell_order = self.get_order(sell_transaction['orderid'], return_none=return_none)
        if sell_order and sell_order['deleted']:
            # The API doesn't return data on orders that don't exist, we need to calculate the data on our own
            sell_order = self.calculate_order_data(sell_order, amount, price)
            sell_order.invert()
            self.recheck_orders = True

        return sell_order

    def restore_order(self, order):
        """ If an order is partially or completely filled, this will make a new order of original size and price.

            :param order:
            :return:
        """
        # Todo: Insert logic here

    def retry_action(self, action, *args, **kwargs):
        """ Perform an action, and if certain suspected-to-be-spurious grapheme bugs occur,
            instead of bubbling the exception, it is quietly logged (level WARN), and try again
            tries a fixed number of times (MAX_TRIES) before failing

            :param action:
            :return:
        """
        tries = 0
        while True:
            try:
                return action(*args, **kwargs)
            except bitsharesapi.exceptions.UnhandledRPCError as exception:
                if "Assert Exception: amount_to_sell.amount > 0" in str(exception):
                    if tries > MAX_TRIES:
                        raise
                    else:
                        tries += 1
                        self.log.warning("Ignoring: '{}'".format(str(exception)))
                        self.bitshares.txbuffer.clear()
                        self.account.refresh()
                        time.sleep(2)
                elif "now <= trx.expiration" in str(exception):  # Usually loss of sync to blockchain
                    if tries > MAX_TRIES:
                        raise
                    else:
                        tries += 1
                        self.log.warning("retrying on '{}'".format(str(exception)))
                        self.bitshares.txbuffer.clear()
                        time.sleep(6)  # Wait at least a BitShares block
                else:
                    raise

    def write_order_log(self, worker_name, order):
        """

            :param string | worker_name: Name of the worker
            :param object | order: Order that was traded
        """
        # Todo: Add documentation
        operation_type = 'TRADE'

        if order['base']['symbol'] == self.market['base']['symbol']:
            base_symbol = order['base']['symbol']
            base_amount = -order['base']['amount']
            quote_symbol = order['quote']['symbol']
            quote_amount = order['quote']['amount']
        else:
            base_symbol = order['quote']['symbol']
            base_amount = order['quote']['amount']
            quote_symbol = order['base']['symbol']
            quote_amount = -order['base']['amount']

        message = '{};{};{};{};{};{};{};{}'.format(
            worker_name,
            order['id'],
            operation_type,
            base_symbol,
            base_amount,
            quote_symbol,
            quote_amount,
            datetime.datetime.now().isoformat()
        )

        self.orders_log.info(message)

    @property
    def account(self):
        """ Return the full account as :class:`bitshares.account.Account` object!
            Can be refreshed by using ``x.refresh()``

            :return: object | Account
        """
        return self._account

    @property
    def balances(self):
        """ Returns all the balances of the account assigned for the worker.

            :return: list: Balances in list where each asset is in their own Amount object
        """
        return self._account.balances

    @property
    def all_own_orders(self, refresh=True):
        """ Return the worker's open orders in all markets

            :param bool | refresh: Use most resent data
            :return: list: List of Order objects
        """
        # Refresh account data
        if refresh:
            self.account.refresh()

        return [order for order in self.account.openorders]

    @property
    def current_market_own_orders(self, refresh=False):
        """ Return the account's open orders in the current market

            :return: list: List of Order objects
        """
        orders = []

        # Refresh account data
        if refresh:
            self.account.refresh()

        for order in self.account.openorders:
            if self.worker["market"] == order.market and self.account.openorders:
                orders.append(order)

        return orders

    @property
    def get_updated_orders(self):
        """ Returns all open orders as updated orders
            Todo: What exactly? When orders are needed who wants out of date info?
        """
        self.account.refresh()

        limited_orders = []
        for order in self.account['limit_orders']:
            base_asset_id = order['sell_price']['base']['asset_id']
            quote_asset_id = order['sell_price']['quote']['asset_id']
            # Check if the order is in the current market
            if not self.is_current_market(base_asset_id, quote_asset_id):
                continue

            limited_orders.append(self.get_updated_limit_order(order))

        return [Order(order, bitshares_instance=self.bitshares) for order in limited_orders]

    @property
    def market(self):
        """ Return the market object as :class:`bitshares.market.Market`
        """
        return self._market

    @staticmethod
    def convert_asset(from_value, from_asset, to_asset, refresh=False):
        """ Converts asset to another based on the latest market value

            :param float | from_value: Amount of the input asset
            :param string | from_asset: Symbol of the input asset
            :param string | to_asset: Symbol of the output asset
            :param bool | refresh:
            :return: float Asset converted to another asset as float value
        """
        market = Market('{}/{}'.format(from_asset, to_asset))
        ticker = market.ticker()
        latest_price = ticker.get('latest', {}).get('price', None)
        return from_value * latest_price

    @staticmethod
    def get_original_order(order_id, return_none=True):
        """ Returns the Order object for the order_id

            :param dict | order_id: blockchain object id of the order can be an order dict with the id key in it
            :param bool | return_none: return None instead of an empty Order object when the order doesn't exist
            :return:
        """
        if not order_id:
            return None

        if 'id' in order_id:
            order_id = order_id['id']

        order = Order(order_id)

        if return_none and order['deleted']:
            return None

        return order

    @staticmethod
    def get_updated_limit_order(limit_order):
        """ Returns a modified limit_order so that when passed to Order class,
            will return an Order object with updated amount values

            :param limit_order: an item of Account['limit_orders']
            :return: Order
            Todo: When would we not want an updated order?
        """
        order = copy.deepcopy(limit_order)
        price = order['sell_price']['base']['amount'] / order['sell_price']['quote']['amount']
        base_amount = order['for_sale']
        quote_amount = base_amount / price
        order['sell_price']['base']['amount'] = base_amount
        order['sell_price']['quote']['amount'] = quote_amount
        return order

    @staticmethod
    def purge_all_local_worker_data(worker_name):
        # Todo: Confirm this being correct
        """ Removes worker's data and orders from local sqlite database

            :param worker_name: Name of the worker to be removed
        """
        Storage.clear_worker_data(worker_name)

    @staticmethod
    def sort_orders(orders, sort='DESC'):
        """ Return list of orders sorted ascending or descending

            :param list | orders: list of orders to be sorted
            :param string | sort: ASC or DESC. Default DESC
            :return list: Sorted list of orders
        """
        if sort.upper() == 'ASC':
            reverse = False
        elif sort.upper() == 'DESC':
            reverse = True
        else:
            return None

        # Sort orders by price
        return sorted(orders, key=lambda order: order['price'], reverse=reverse)
