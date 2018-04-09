import logging
from events import Events
from bitshares.amount import Amount
from bitshares.market import Market
from bitshares.account import Account
from bitshares.price import FilledOrder, Order, UpdateCallOrder
from bitshares.instance import shared_bitshares_instance
from .storage import Storage
from .statemachine import StateMachine


class BaseStrategy(Storage, StateMachine, Events):
    """ Base Strategy and methods available in all Sub Classes that
        inherit this BaseStrategy.

        BaseStrategy inherits:

        * :class:`dexbot.storage.Storage`
        * :class:`dexbot.statemachine.StateMachine`
        * ``Events``

        Available attributes:

         * ``basestrategy.bitshares``: instance of ´`bitshares.BitShares()``
         * ``basestrategy.add_state``: Add a specific state
         * ``basestrategy.set_state``: Set finite state machine
         * ``basestrategy.get_state``: Change state of state machine
         * ``basestrategy.account``: The Account object of this worker
         * ``basestrategy.market``: The market used by this worker
         * ``basestrategy.orders``: List of open orders of the worker's account in the worker's market
         * ``basestrategy.balance``: List of assets and amounts available in the worker's account
         * ``basestrategy.log``: a per-worker logger (actually LoggerAdapter) adds worker-specific context:
            worker name & account (Because some UIs might want to display per-worker logs)

        Also, Base Strategy inherits :class:`dexbot.storage.Storage`
        which allows to permanently store data in a sqlite database
        using:

        ``basestrategy["key"] = "value"``

        .. note:: This applies a ``json.loads(json.dumps(value))``!

    Workers must never attempt to interact with the user, they must assume they are running unattended
    They can log events. If a problem occurs they can't fix they should set self.disabled = True and throw an exception
    The framework catches all exceptions thrown from event handlers and logs appropriately.
    """

    __events__ = [
        'ontick',
        'onMarketUpdate',
        'onAccount',
        'error_ontick',
        'error_onMarketUpdate',
        'error_onAccount',
        'onOrderMatched',
        'onOrderPlaced',
        'onUpdateCallOrder',
    ]

    def __init__(
        self,
        config,
        name,
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

        self.config = config
        self.worker = config["workers"][name]
        self._account = Account(
            self.worker["account"],
            full=True,
            bitshares_instance=self.bitshares
        )
        self._market = Market(
            config["workers"][name]["market"],
            bitshares_instance=self.bitshares
        )

        # Settings for bitshares instance
        self.bitshares.bundle = bool(self.worker.get("bundle", False))

        # Disabled flag - this flag can be flipped to True by a worker and
        # will be reset to False after reset only
        self.disabled = False

        # A private logger that adds worker identify data to the LogRecord
        self.log = logging.LoggerAdapter(
            logging.getLogger('dexbot.per_worker'),
            {'worker_name': name,
             'account': self.worker['account'],
             'market': self.worker['market'],
             'is_disabled': lambda: self.disabled}
        )

    @property
    def calculate_center_price(self):
        ticker = self.market.ticker()
        highest_bid = ticker.get("highestBid")
        lowest_ask = ticker.get("lowestAsk")
        if highest_bid is None or highest_bid == 0.0:
            self.log.critical(
                "Cannot estimate center price, there is no highest bid."
            )
            self.disabled = True
        elif lowest_ask is None or lowest_ask == 0.0:
            self.log.critical(
                "Cannot estimate center price, there is no lowest ask."
            )
            self.disabled = True
        else:
            center_price = (highest_bid['price'] + lowest_ask['price']) / 2
            return center_price

    @property
    def orders(self):
        """ Return the worker's open accounts in the current market
        """
        self.account.refresh()
        return [o for o in self.account.openorders if self.worker["market"] == o.market and self.account.openorders]

    def get_order(self, order_id):
        for order in self.orders:
            if order['id'] == order_id:
                return order
        return False

    def get_updated_order(self, order):
        """ Tries to get the updated order from the API
            returns None if the order doesn't exist
        """
        if not order:
            return None
        if isinstance(order, str):
            order = {'id': order}
        for updated_order in self.updated_open_orders:
            if updated_order['id'] == order['id']:
                return updated_order
        return None

    @property
    def updated_open_orders(self):
        """
        Returns updated open Orders.
        account.openorders doesn't return updated values for the order so we calculate the values manually
        """
        self.account.refresh()
        self.account.ensure_full()

        limit_orders = self.account['limit_orders'][:]
        for o in limit_orders:
            base_amount = o['for_sale']
            price = o['sell_price']['base']['amount'] / o['sell_price']['quote']['amount']
            quote_amount = base_amount / price
            o['sell_price']['base']['amount'] = base_amount
            o['sell_price']['quote']['amount'] = quote_amount

        orders = [
            Order(o, bitshares_instance=self.bitshares)
            for o in limit_orders
        ]

        return [o for o in orders if self.worker["market"] == o.market]

    @property
    def market(self):
        """ Return the market object as :class:`bitshares.market.Market`
        """
        return self._market

    @property
    def account(self):
        """ Return the full account as :class:`bitshares.account.Account` object!

            Can be refreshed by using ``x.refresh()``
        """
        return self._account

    def balance(self, asset):
        """ Return the balance of your worker's account for a specific asset
        """
        return self._account.balance(asset)

    @property
    def test_mode(self):
        return self.config['node'] == "wss://node.testnet.bitshares.eu"

    @property
    def balances(self):
        """ Return the balances of your worker's account
        """
        return self._account.balances

    def _callbackPlaceFillOrders(self, d):
        """ This method distinguishes notifications caused by Matched orders
            from those caused by placed orders
        """
        if isinstance(d, FilledOrder):
            self.onOrderMatched(d)
        elif isinstance(d, Order):
            self.onOrderPlaced(d)
        elif isinstance(d, UpdateCallOrder):
            self.onUpdateCallOrder(d)
        else:
            pass

    def execute(self):
        """ Execute a bundle of operations
        """
        self.bitshares.blocking = "head"
        r = self.bitshares.txbuffer.broadcast()
        self.bitshares.blocking = False
        return r

    def cancel(self, orders):
        """ Cancel specific orders
        """
        if not isinstance(orders, list):
            orders = [orders]
        return self.bitshares.cancel(
            [o["id"] for o in orders if "id" in o],
            account=self.account
        )

    def cancel_all(self):
        """ Cancel all orders of the worker's account
        """
        if self.orders:
            self.log.info('Canceling all orders')
            return self.bitshares.cancel(
                [o["id"] for o in self.orders],
                account=self.account
            )

    def purge(self):
        """ Clear all the worker data from the database and cancel all orders
        """
        self.cancel_all()
        self.clear()

    @staticmethod
    def get_order_amount(order, asset_type):
        try:
            order_amount = order[asset_type]['amount']
        except (KeyError, TypeError):
            order_amount = 0
        return order_amount

    def total_balance(self, order_ids=None, return_asset=False):
        """ Returns the combined balance of the given order ids and the account balance
            The amounts are returned in quote and base assets of the market

            :param order_ids: list of order ids to be added to the balance
            :param return_asset: true if returned values should be Amount instances
            :return: dict with keys quote and base
        """
        quote = 0
        base = 0
        quote_asset = self.market['quote']['id']
        base_asset = self.market['base']['id']

        for balance in self.balances:
            if balance.asset['id'] == quote_asset:
                quote += balance['amount']
            elif balance.asset['id'] == base_asset:
                base += balance['amount']

        orders_balance = self.orders_balance(order_ids)
        quote += orders_balance['quote']
        base += orders_balance['base']

        if return_asset:
            quote = Amount(quote, quote_asset)
            base = Amount(base, base_asset)

        return {'quote': quote, 'base': base}

    def orders_balance(self, order_ids, return_asset=False):
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
