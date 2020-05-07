import logging
import math
import time
from datetime import datetime

from dexbot.config import Config
from dexbot.orderengines.bitshares_engine import BitsharesOrderEngine
from dexbot.pricefeeds.bitshares_feed import BitsharesPriceFeed
from dexbot.qt_queue.idle_queue import idle_add
from dexbot.storage import Storage
from dexbot.strategies.config_parts.base_config import BaseConfig

# Number of maximum retries used to retry action before failing
MAX_TRIES = 3


class StrategyBase(BitsharesOrderEngine, BitsharesPriceFeed):
    """
    A strategy based on this class is intended to work in one market. This class contains most common methods needed by
    the strategy.

    NOTE: StrategyBase currently requires BitsharesOrderEngine inheritance
    as all configuration from Worker is located here.

    Post Core-refactor, in the future it should not be this way.

    TODO: The StrategyBase should be able to select any {N} OrderEngine(s) and {M} PriceFeed(s)
    and not be tied to the BitsharesOrderEngine only. (where N and M are integers)
    This would allow for cross dex or cex strategy flexibility

    In process: make StrategyBase an ABC.

    Unit tests should take above into consideration


    All prices are passed and returned as BASE/QUOTE.
    (In the BREAD:USD market that would be USD/BREAD, 2.5 USD / 1 BREAD).
    - Buy orders reserve BASE
    - Sell orders reserve QUOTE

    Strategy inherits:
        * :class:`dexbot.storage.Storage` : Stores data to sqlite database
        * ``Events``

    Available attributes:
        * ``worker.bitshares``: instance of ´`bitshares.BitShares()``
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

    @classmethod
    def configure(cls, return_base_config=True):
        return BaseConfig.configure(return_base_config)

    @classmethod
    def configure_details(cls, include_default_tabs=True):
        return BaseConfig.configure_details(include_default_tabs)

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

    def __init__(
        self,
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
        **kwargs
    ):

        BitsharesOrderEngine.__init__(self, name, config=config, *args, **kwargs)

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

        self.assets_intersections_data = None
        if config:
            self.config = config
            self.assets_intersections_data = Config.assets_intersections(config)
        else:
            self.config = config = Config.get_worker_config_file(name)

        # What percent of balance the worker should use
        self.operational_percent_quote = self.worker.get('operational_percent_quote', 0) / 100
        self.operational_percent_base = self.worker.get('operational_percent_base', 0) / 100

        # Initial value for check_last_run decorator in dexbot/decorators.py
        self.last_check = datetime(1970, 1, 1)

        # A private logger that adds worker identify data to the LogRecord
        self.log = logging.LoggerAdapter(
            logging.getLogger('dexbot.per_worker'),
            {
                'worker_name': name,
                'account': self.worker['account'],
                'market': self.worker['market'],
                'is_disabled': lambda: self.disabled,
            },
        )

        self.orders_log = logging.LoggerAdapter(logging.getLogger('dexbot.orders_log'), {})

    def pause(self):
        """
        Pause the worker.

        Note: By default pause cancels orders, but this can be overridden by strategy
        """
        # Cancel all orders from the market
        self.cancel_all_orders()

        # Removes worker's orders from local database
        self.clear_orders()

    def clear_all_worker_data(self):
        """Clear all the worker data from the database and cancel all orders."""
        # Removes worker's orders from local database
        self.clear_orders()

        # Cancel all orders from the market
        self.cancel_all_orders()

        # Finally clear all worker data from the database
        self.clear()

    def get_worker_share_for_asset(self, asset):
        """
        Returns operational percent of asset available to the worker.

        :param str asset: Which asset should be checked
        :return: a value between 0-1 representing a percent
        :rtype: float
        """
        intersections_data = self.assets_intersections_data[self.account.name][asset]

        if asset == self.market['base']['symbol']:
            if self.operational_percent_base:
                return self.operational_percent_base
            else:
                return (1 - intersections_data['sum_pct']) / intersections_data['num_zero_workers']
        elif asset == self.market['quote']['symbol']:
            if self.operational_percent_quote:
                return self.operational_percent_quote
            else:
                return (1 - intersections_data['sum_pct']) / intersections_data['num_zero_workers']
        else:
            self.log.error('Got asset which is not used by this worker')

    def store_profit_estimation_data(self):
        """Save total quote, total base, center_price, and datetime in to the database."""
        assets = self.count_asset()
        account = self.config['workers'][self.worker_name].get('account')
        base_amount = assets['base']
        base_symbol = self.market['base'].get('symbol')
        quote_amount = assets['quote']
        quote_symbol = self.market['quote'].get('symbol')
        center_price = self.get_market_center_price(suppress_errors=True)
        if not center_price:
            # Don't write anything until center price will be available
            return None
        timestamp = time.time()

        self.store_balance_entry(
            account, self.worker_name, base_amount, base_symbol, quote_amount, quote_symbol, center_price, timestamp
        )

    def get_profit_estimation_data(self, seconds):
        """
        Get balance history closest to the given time.

        :returns The data as dict from the first timestamp going backwards from seconds argument
        """
        return self.get_balance_history(
            self.config['workers'][self.worker_name].get('account'), self.worker_name, seconds
        )

    def calc_profit(self):
        """Calculate relative profit for the current worker."""
        profit = 0
        time_range = 60 * 60 * 24 * 7  # 7 days
        current_time = time.time()
        timestamp = current_time - time_range

        # Fetch the balance from history
        old_data = self.get_balance_history(
            self.config['workers'][self.worker_name].get('account'),
            self.worker_name,
            timestamp,
            self.base_asset,
            self.quote_asset,
        )
        if old_data:
            earlier_base = old_data.base_total
            earlier_quote = old_data.quote_total
            old_center_price = old_data.center_price
            center_price = self.get_market_center_price(suppress_errors=True)

            if not old_center_price or not center_price:
                return profit

            # Calculate max theoretical balances based on starting price
            old_max_quantity_base = earlier_base + earlier_quote * old_center_price
            old_max_quantity_quote = earlier_quote + earlier_base / old_center_price

            if not old_max_quantity_base or not old_max_quantity_quote:
                return profit

            # Current balances
            balance = self.count_asset()
            base_balance = balance['base']
            quote_balance = balance['quote']

            # Calculate max theoretical current balances
            max_quantity_base = base_balance + quote_balance * center_price
            max_quantity_quote = quote_balance + base_balance / center_price

            base_roi = max_quantity_base / old_max_quantity_base
            quote_roi = max_quantity_quote / old_max_quantity_quote
            profit = round(math.sqrt(base_roi * quote_roi) - 1, 4)

        return profit

    @property
    def balances(self):
        """
        Returns all the balances of the account assigned for the worker.

        :return: Balances in list where each asset is in their own Amount object
        """
        return self._account.balances

    @staticmethod
    def purge_all_local_worker_data(worker_name):
        """
        Removes worker's data and orders from local sqlite database.

        :param worker_name: Name of the worker to be removed
        """
        Storage.clear_worker_data(worker_name)

    # GUI updaters
    def update_gui_slider(self):
        ticker = self.market.ticker()
        latest_price = ticker.get('latest', {}).get('price', None)
        if not latest_price:
            return

        total_balance = self.count_asset()
        total = (total_balance['quote'] * latest_price) + total_balance['base']

        if not total:  # Prevent division by zero
            percentage = 50
        else:
            percentage = (total_balance['base'] / total) * 100
        idle_add(self.view.set_worker_slider, self.worker_name, percentage)
        self['slider'] = percentage

    def update_gui_profit(self):
        profit = self.calc_profit()

        # Add to idle queue
        idle_add(self.view.set_worker_profit, self.worker_name, float(profit))
        self['profit'] = profit
