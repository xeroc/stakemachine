import logging
from events import Events
from bitshares.market import Market
from bitshares.account import Account
from bitshares.price import FilledOrder, Order
from bitshares.instance import shared_bitshares_instance
from .storage import Storage
from .statemachine import StateMachine
log = logging.getLogger(__name__)


class BaseStrategy(Storage, StateMachine, Events):

    __events__ = [
        'onOrderMatched',
        'onOrderPlaced',
        'onMarketUpdate',
        'ontick',
    ]

    def __init__(
        self,
        config,
        name,
        onOrderMatched=None,
        onOrderPlaced=None,
        onMarketUpdate=None,
        ontick=None,
        bitshares_instance=None,
        *args,
        **kwargs
    ):
        """ Base Strategy and methods available in all Sub Classes that
            inherit this BaseStrategy.

            BaseStrategy inherits:

            * :class:`stakemachine.storage.Storage`
            * :class:`stakemachine.statemachine.StateMachine`
            * ``Events``

            Available attributes:

             * ``basestrategy.bitshares``: instance of ´`bitshares.BitShares()``
             * ``basestrategy.add_state``: Add a specific state
             * ``basestrategy.set_state``: Set finite state machine
             * ``basestrategy.get_state``: Change state of state machine
             * ``basestrategy.account``: The Account object of this bot
             * ``basestrategy.market``: The market used by this bot
             * ``basestrategy.orders``: List of open orders of the bot's account in the bot's market
             * ``basestrategy.balance``: List of assets and amounts available in the bot's account

            Also, Base Strategy inherits :class:`stakemachine.storage.Storage`
            which allows to permanently store data in a sqlite database
            using:

            ``basestrategy["key"] = "value"``

            ... note:: This applies a ``json.loads(json.dumps(value))``!
        """
        # BitShares instance
        self.bitshares = bitshares_instance or shared_bitshares_instance()

        # Storage
        Storage.__init__(self, name)

        # Statemachine
        StateMachine.__init__(self, name)

        # Events
        Events.__init__(self)

        if onOrderMatched:
            self.onOrderMatched += onOrderMatched
        if onOrderPlaced:
            self.onOrderPlaced += onOrderPlaced
        if onMarketUpdate:
            self.onMarketUpdate += onMarketUpdate
        if ontick:
            self.ontick += ontick

        # Redirect this event to also call order placed and order matched
        self.onMarketUpdate += self._callbackPlaceFillOrders

        self.config = config
        self.bot = config["bots"][name]
        self._account = Account(
            self.bot["account"],
            full=True,
            bitshares_instance=self.bitshares
        )
        self._market = Market(
            config["bots"][name]["market"],
            bitshares_instance=self.bitshares
        )

        # Settings for bitshares instance
        self.bitshares.bundle = bool(self.bot["bundle"])

    @property
    def orders(self):
        """ Return the bot's open accounts in the current market
        """
        self.account.refresh()
        return [o for o in self.account.openorders if self.bot["market"] == o.market and self.account.openorders]

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
        """ Return the balance of your bot's account for a specific asset
        """
        return self._account.balance(asset)

    @property
    def balances(self):
        """ Return the balances of your bot's account
        """
        return self._account.balances

    def _callbackPlaceFillOrders(self, d):
        """ This method distringuishes notifications caused by Matched orders
            from those caused by placed orders
        """
        if isinstance(d, FilledOrder):
            self.onOrderMatched(d)
        elif isinstance(d, Order):
            self.onOrderPlaced(d)
        else:
            pass

    def execute(self):
        """ Execute a bundle of operations
        """
        self.bitshares.blocking = "head"
        r = self.bitshares.txbuffer.broadcast()
        self.bitshares.blocking = False
        return r
