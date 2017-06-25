from pprint import pprint
from collections import Counter
from bitshares.amount import Amount
from stakemachine.basestrategy import BaseStrategy
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
        if self.orders:
            self.bitshares.cancel([o["id"] for o in self.orders], account=self.account)

        target = self.bot.get("target", {})

        if target.get("reference") == "feed":
            assert self.market == self.market.core_quote_market(), "Wrong market for 'feed' reference!"
            ticker = self.market.ticker()
            price = ticker.get("quoteSettlement_price")
            assert abs(price["price"]) != float("inf"), "Check price feed of asset!"

        self.market.buy(
            price * (1 - target["spread"]/200),
            Amount(target["amount"]["buy"], self.market["quote"]),
            account=self.account
        )
        self.market.sell(
            price * (1 + target["spread"]/200),
            Amount(target["amount"]["sell"], self.market["quote"]),
            account=self.account
        )

        pprint(self.execute())

    def tick(self, d):
        if self.test_blocks:
            self.counter["blocks"] += 1
            if not self.counter["blocks"] % self.test_blocks:
                self.test()

    def test(self):
        """ Tests if the orders need updating
        """
        orders = self.orders

        if len(orders) < 2:
            self.updateorders()
