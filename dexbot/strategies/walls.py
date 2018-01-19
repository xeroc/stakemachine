from math import fabs
from pprint import pprint
from collections import Counter
from bitshares.amount import Amount
from dexbot.basestrategy import BaseStrategy
from dexbot.errors import InsufficientFundsError


class Walls(BaseStrategy):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Define Callbacks
        self.onMarketUpdate += self.test
        self.ontick += self.tick
        self.onAccount += self.test

        self.error_ontick = self.error
        self.error_onMarketUpdate = self.error
        self.error_onAccount = self.error

        # Counter for blocks
        self.counter = Counter()

        # Tests for actions
        self.test_blocks = self.bot.get("test", {}).get("blocks", 0)

    def error(self, *args, **kwargs):
        self.disabled = True
        self.cancelall()
        self.log.info(self.execute())

    def updateorders(self):
        """ Update the orders
        """
        self.log.info("Replacing orders")

        # Canceling orders
        self.cancelall()

        # Target
        target = self.bot.get("target", {})
        price = self.getprice()

        # prices
        buy_price = price * (1 - target["offsets"]["buy"] / 100)
        sell_price = price * (1 + target["offsets"]["sell"] / 100)

        # Store price in storage for later use
        self["feed_price"] = float(price)

        # Buy Side
        if float(self.balance(self.market["base"])) < buy_price * target["amount"]["buy"]:
            InsufficientFundsError(Amount(target["amount"]["buy"] * float(buy_price), self.market["base"]))
            self["insufficient_buy"] = True
        else:
            self["insufficient_buy"] = False
            self.market.buy(
                buy_price,
                Amount(target["amount"]["buy"], self.market["quote"]),
                account=self.account
            )

        # Sell Side
        if float(self.balance(self.market["quote"])) < target["amount"]["sell"]:
            InsufficientFundsError(Amount(target["amount"]["sell"], self.market["quote"]))
            self["insufficient_sell"] = True
        else:
            self["insufficient_sell"] = False
            self.market.sell(
                sell_price,
                Amount(target["amount"]["sell"], self.market["quote"]),
                account=self.account
            )

        self.log.info(self.execute())

    def getprice(self):
        """ Here we obtain the price for the quote and make sure it has
            a feed price
        """
        target = self.bot.get("target", {})
        if target.get("reference") == "feed":
            assert self.market == self.market.core_quote_market(), "Wrong market for 'feed' reference!"
            ticker = self.market.ticker()
            price = ticker.get("quoteSettlement_price")
            assert abs(price["price"]) != float("inf"), "Check price feed of asset! (%s)" % str(price)
        return price

    def tick(self, d):
        """ ticks come in on every block
        """
        if self.test_blocks:
            if not (self.counter["blocks"] or 0) % self.test_blocks:
                self.test()
            self.counter["blocks"] += 1

    def test(self, *args, **kwargs):
        """ Tests if the orders need updating
        """
        orders = self.orders

        # Test if still 2 orders in the market (the walls)
        if len(orders) < 2 and len(orders) > 0:
            if (
                not self["insufficient_buy"] and
                not self["insufficient_sell"]
            ):
                self.log.info("No 2 orders available. Updating orders!")
                self.updateorders()
        elif len(orders) == 0:
            self.updateorders()

        # Test if price feed has moved more than the threshold
        if (
            self["feed_price"] and
            fabs(1 - float(self.getprice()) / self["feed_price"]) > self.bot["threshold"] / 100.0
        ):
            self.log.info("Price feed moved by more than the threshold. Updating orders!")
            self.updateorders()
