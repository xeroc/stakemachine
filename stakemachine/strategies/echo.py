from stakemachine.basestrategy import BaseStrategy
import logging
log = logging.getLogger(__name__)


def print1(i):
    print("1: %s" % i)

def print2(i):
    print("2: %s" % i)

def print3(i):
    print("3: %s" % i)

def print4(i):
    print("4: %s" % i)

class Echo(BaseStrategy):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        """ set default settings
        """
        self.onOrderMatched += print1
        self.onOrderPlaced += print2
        #self.onMarketUpdate += print3
        self.ontick += print4
