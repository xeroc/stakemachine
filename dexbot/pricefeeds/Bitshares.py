
import bitshares.exceptions
import bitsharesapi
import bitsharesapi.exceptions
from bitshares.market import Market

class PriceFeed:

    def __init__(self, market, account):
        self.market = market
        self.account = account