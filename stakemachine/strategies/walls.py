from math import fabs
from pprint import pprint
from collections import Counter
from bitshares.amount import Amount
from stakemachine.basestrategy import BaseStrategy
from stakemachine.errors import InsufficientFundsError
import logging
log = logging.getLogger(__name__)


class Walls(BaseStrategy):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Define Callbacks
        self.onMarketUpdate += self.test
        self.ontick += self.tick

        # Counter for blocks
        self.counter = Counter()

        # Tests for actions
        self.test_blocks = self.bot.get("test", {}).get("blocks", 0)

    def updateorders(self):
        """ Update the orders
        """
        log.info("Replacing orders")
        if self.orders:
            self.bitshares.cancel([o["id"] for o in self.orders], account=self.account)

        target = self.bot.get("target", {})
        price = self.getprice()

        # prices
        buy_price = price * (1 - target["offsets"]["buy"] / 100)
        sell_price = price * (1 + target["offsets"]["sell"] / 100)

        # Store price in storage for later use
        self["feed_price"] = float(price)

        # Buy Side
        if float(self.balance(self.market["base"])) < buy_price * target["amount"]["buy"]:
            InsufficientFundsError(Amount(target["amount"]["buy"], self.market["quote"]))
        else:
            self.market.buy(
                buy_price,
                Amount(target["amount"]["buy"], self.market["quote"]),
                account=self.account
            )

        # Sell Side
        if float(self.balance(self.market["quote"])) < target["amount"]["sell"]:
            InsufficientFundsError(Amount(target["amount"]["sell"], self.market["quote"]))
        else:
            self.market.sell(
                sell_price,
                Amount(target["amount"]["sell"], self.market["quote"]),
                account=self.account
            )

        pprint(self.execute())

    def getprice(self):
        target = self.bot.get("target", {})
        if target.get("reference") == "feed":
            assert self.market == self.market.core_quote_market(), "Wrong market for 'feed' reference!"
            ticker = self.market.ticker()
            price = ticker.get("quoteSettlement_price")
            assert abs(price["price"]) != float("inf"), "Check price feed of asset!"
        return price

    def tick(self, d):
        """ ticks come in on every block
        """
        if self.test_blocks:
            self.counter["blocks"] += 1
            if not self.counter["blocks"] % self.test_blocks:
                self.test()

    def test(self, *args, **kwargs):
        """ Tests if the orders need updating
        """
        orders = self.orders

        # Test if still 2 orders in the market (the walls)
        if len(orders) < 2:
            log.info("No 2 orders available. Updating orders!")
            self.updateorders()

        # Test if price feed has moved more than the threshold
        if (
            self["feed_price"] and
            fabs(1 - float(self.getprice()) / self["feed_price"]) > self.bot["threshold"] / 100.0
        ):
            log.info("Price feed moved by more than the threshold. Updating orders!")
            self.updateorders()
