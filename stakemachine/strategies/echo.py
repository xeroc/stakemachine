from stakemachine.basestrategy import BaseStrategy
import logging
log = logging.getLogger(__name__)


def print1(i):
    print("order matched: %s" % i)


def print2(i):
    print("order placed:  %s" % i)


def print3(i):
    print("marketupdate:  %s" % i)


def print4(i):
    print("new block:     %s" % i)


def print5(i):
    print("account:       %s" % i)


class Echo(BaseStrategy):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        """ set default settings
        """
        self.onOrderMatched += print1
        self.onOrderPlaced += print2
        self.onMarketUpdate += print3
        self.ontick += print4
        self.onAccount += print5
