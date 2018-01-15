import logging
from events import Events
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
         * ``basestrategy.account``: The Account object of this bot
         * ``basestrategy.market``: The market used by this bot
         * ``basestrategy.orders``: List of open orders of the bot's account in the bot's market
         * ``basestrategy.balance``: List of assets and amounts available in the bot's account
         * ``basestrategy.log``: a per-bot logger (actually LoggerAdapter) adds bot-specific context: botname & account
           (Because some UIs might want to display per-bot logs)

        Also, Base Strategy inherits :class:`dexbot.storage.Storage`
        which allows to permanently store data in a sqlite database
        using:

        ``basestrategy["key"] = "value"``

        .. note:: This applies a ``json.loads(json.dumps(value))``!

    Bots must never attempt to interact with the user, they must assume they are running unattended
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
        self.bitshares.bundle = bool(self.bot.get("bundle", False))

        # disabled flag - this flag can be flipped to True by a bot and
        # will be reset to False after reset only
        self.disabled = False

        # a private logger that adds bot identify data to the LogRecord
        self.log = logging.LoggerAdapter(logging.getLogger('dexbot.per_bot'),{'botname':name,
                                                                                 'account':self.bot['account'],
                                                                                 'market':self.bot['market'],
                                                                                 'is_disabled':(lambda: self.disabled)})
    
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

    def cancelall(self):
        """ Cancel all orders of this bot
        """
        if self.orders:
            return self.bitshares.cancel(
                [o["id"] for o in self.orders],
                account=self.account
            )
