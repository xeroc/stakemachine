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

            Available attributes:

             * ``basestrategy.bitshares``: instance of ´`bitshares.BitShares()``
             * ``basestrategy.add_state``: Add a specific state
             * ``basestrategy.set_state``: Set finite state machine
             * ``basestrategy.get_state``: Change state of state machine
             * ``basestrategy.account``: The Account object of this bot 
             * ``basestrategy.market``: The market used by this bot
             * ``basestrategy.orders``: List of open orders of the bot's account in the bot's market
             * ``basestrategy.balanc``: List of assets and amounts available in the bot's account

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
        self.account = Account(
            self.bot["account"],
            bitshares_instance=self.bitshares
        )

    @property
    def market(self):
        return Market(
            self.bot["market"],
            bitshares_instance=self.bitshares
        )

    @property
    def orders(self):
        return [o for o in self.account.openorders if self.bot["market"] == o.market]

    @property
    def balance(self):
        return self.account.balances

    @property
    def balances(self):
        return self.balance

    def _callbackPlaceFillOrders(self, d):
        if isinstance(d, FilledOrder):
            self.onOrderMatched(d)
        elif isinstance(d, Order):
            self.onOrderPlaced(d)
        else:
            pass
