import logging
from events import Events
from bitshares.price import FilledOrder, Order
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
        *args,
        **kwargs
    ):
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
        self.onMarketUpdate += self.callbackPlaceFillOrders

    def callbackPlaceFillOrders(self, d):
        if isinstance(d, FilledOrder):
            self.onOrderMatched(d)
        elif isinstance(d, Order):
            self.onOrderPlaced(d)
        else:
            pass

    def update(self):
        """ Tick every block
        """
        log.debug("Market update. Please define `%s.update()`" % self.name)

    # Extra calls
    def buy(self, market, price, amount, expiration=60 * 60 * 24, **kwargs):
        pass

    def sell(self, market, price, amount, expiration=60 * 60 * 24, **kwargs):
        pass

    def cancel(self, orderid):
        """ Cancel the order with id ``orderid``
        """
        log.info("Canceling %s" % orderid)
        try:
            cancel = self.dex.cancel(orderid)
        except Exception as e:
            log.critical("An error occured while trying to sell: %s" % str(e))
        return cancel

    def get_balances(self):
        pass

    @property
    def balance(self):
        pass
