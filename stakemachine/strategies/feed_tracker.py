from .basestrategy import BaseStrategy, MissingSettingsException
import logging
import math
log = logging.getLogger(__name__)


class FeedTracker(BaseStrategy):
    """ This strategy trusts the feed/settlemnt price published by the
        witness nodes (et. al.) on bitassets and trades around that
        feed.

        **Configuration parameters**

        * **assets**: The list of assets you want to track (required for notifications on feed price changes)
        * **markets**: The markets you are interested in (usually related to 'assets' by appending ":BTS")
        * **spread**: The spread (percentage) at which to place orders
        * **offset**: An offset (percentage) for the sell/buy price
        * **threshold**: Update the orders if the price feed is less than x% away from any of my orders!
        * **delay**: Way x blocks before updating the order
        * **amount**: Definition of the amounts to be used

        .. code-block:: yaml

             FeedTrack:
              module: "stakemachine.strategies.feed_tracker"
              bot: "FeedTracker"
              assets:
               - "USD"
              markets:
               - "USD:BTS"
              spread: 5
              offset: +1.0
              threshold: 2
              delay: 5
              amount:
                [...]

        **Amount Configuration**

        Absolute Amounts:

        ..code-block:: yaml

              amount:
               type: "absolute"
               amounts:
                USD: 2
                BTS: 200
                EUR: 500

        Percentage (of remaining balance) amounts (per order!!)

        ..code-block:: yaml

              amount:
               type: "percentage"
               percentages:
                USD: 50
                BTS: 50

        Balanced Amounts such that the orders on both sides are equal "value"

        ..code-block:: yaml

              amount:
               type: "balanced"
               balance: "BTS"
               amounts:
                USD: .5
                EUR: .5
                SILVER: 0.01

    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.refreshMarkets = []

    def init(self):
        ticker = self.dex.returnTicker()

        self.settings["delay"] = self.settings.get("delay", 3)
        self.settings["offset"] = self.settings.get("offset", 0)
        self.settings["spread"] = self.settings.get("spread", 5)
        self.settings["threshold"] = self.settings.get("threshold", self.settings["spread"] / 4)

        if self.settings["threshold"] * 2 + self.settings["offset"] >= self.settings["spread"]:
            raise ValueError("threshold * 2 + offset has to be smaller than 'spread'!")

        for m in self.settings.get("markets"):
            if ("settlement_price" not in ticker[m]):
                raise ValueError("The market %s " % m +
                                 "has no settlement/feed price!")

    def orderFilled(self, oid):
        self.ensureOrders()

    def tick(self, *args, **kwargs):
        if self.getFSM() == "counting":
            self.incrementFSMCounter()
            if self.getFSMCounter() > self.settings["delay"]:
                self.changeFSM("updating")

        if self.getFSM() == "updating":
            log.info("Refreshing markets %s" % str(self.refreshMarkets))
            self.cancel_mine(markets=self.refreshMarkets)
            self.place(markets=self.refreshMarkets)
            # reset
            self.changeFSM("waiting")
            self.refreshMarkets = []

    def asset_tick(self, *args, **kwargs):
        self.ensureOrders()

    def orderCanceled(self, oid):
        self.asset_tick()

    def orderPlaced(seld, *args, **kwargs):
        """ Do nothing
        """
        pass

    def orderCancled(seld, *args, **kwargs):
        """ Do nothing
        """
        pass

    def ensureOrders(self):
        """ Make sure that there are two orders open for this bot. If
            not, place them!
        """
        if self.getFSM() == "waiting":
            ticker = self.dex.returnTicker()
            openOrders = self.dex.returnOpenOrders()
            myOrders = self.getMyOrders()
            for market in self.settings["markets"]:
                quote, base = market.split(self.config.market_separator)

                # Update if one of the orders has been fully filled
                numOrders = 2
                if self._get(market, "insufficient_sell"):
                    numOrders -= 1
                if self._get(market, "insufficient_buy"):
                    numOrders -= 1
                if numOrders and len(myOrders[market]) != numOrders:
                    log.info("Expected %d orders, found %d." % (numOrders, len(myOrders[market])) +
                             " Goging to refresh market %s" % market)
                    self.refreshMarkets.append(market)

                # Update if the price change is bigger than the threshold
                for oId in myOrders[market]:
                    if oId not in openOrders[market]:
                        self.orderCancled(oId)
                        continue

                    base_price = ticker[market]["settlement_price"]
                    base_price = base_price * (1.0 + self.settings["offset"] / 100)

                    o = openOrders[market][oId]
                    distance = math.fabs(o["rate"] - base_price) / base_price * 100.0

                    if distance < self.settings["threshold"] / 100.0:
                        log.info(
                            "Price feed %f %s/%s is closer than %f%% to my order %f %s/%s" % (
                                ticker[market]["settlement_price"],
                                base, quote,
                                self.settings["threshold"],
                                o["rate"],
                                base, quote))
                        self.refreshMarkets.append(market)
                    else:
                        print("All good")
                        continue

            # unique list
            self.refreshMarkets = list(set(self.refreshMarkets))
            if len(self.refreshMarkets):
                self.changeFSM("counting")

    def place(self, markets=None) :
        """ Place all orders according to the settings.
        """
        if not markets:
            markets = self.settings["markets"]
        tickers = self.dex.returnTicker()
        for m in markets:
            balances = self.dex.returnBalances()
            ticker = tickers.get(m)
            quote, base = m.split(self.config.market_separator)

            base_price = ticker["settlement_price"]
            # offset
            base_price = base_price * (1.0 + self.settings["offset"] / 100)
            # spread
            buy_price  = base_price * (1.0 - self.settings["spread"] / 200)
            sell_price = base_price * (1.0 + self.settings["spread"] / 200)

            # Amount Settings
            amounts = {}
            amountSettings = self.settings.get("amount")
            if quote not in amountSettings.get("amounts"):
                log.warn("You have mentioned %s in 'assets' " % quote +
                         "but have not defined an amount")
                continue
            if amountSettings.get("type") == "absolute":
                amounts = amountSettings.get("amounts")
            elif amountSettings.get("type") == "percentage":
                for a in amountSettings.get("percentages"):
                    amounts[a] = (
                        balances.get(a, 0) *
                        amountSettings["percentages"].get(a, 0) /
                        100
                    )
            elif amountSettings.get("type") == "balanced":
                # Do the balancing later!
                amounts = amountSettings.get("amounts")
            else:
                log.error("No Amount specified")
                continue

            sell_amount = amounts.get(quote, 0)
            buy_amount = amounts.get(base, 0) / buy_price

            if amountSettings.get("type") == "balanced":
                if base == amountSettings.get("balance"):
                    sell_amount = amounts.get(quote, 0)
                    buy_amount = amounts.get(quote, 0)
                if quote == amountSettings.get("balance"):
                    sell_amount = amounts.get(base, 0) / sell_price
                    buy_amount = amounts.get(base, 0) / buy_price

            placed_sell = False
            placed_buy = False
            if sell_amount and sell_amount < balances.get(quote, 0):
                placed_sell = self.sell(m, sell_price, sell_amount)

            if buy_amount and buy_amount * buy_price < balances.get(base, 0):
                placed_buy = self.buy(m, buy_price, buy_amount)

            self._set(m, "insufficient_sell", not placed_sell)
            self._set(m, "insufficient_buy", not placed_buy)

            if not placed_sell:
                log.info("[%s] Not selling %f %s (insufficient balance or not amount provided)!" % (m, sell_amount, quote))

            if not placed_buy:
                log.info("[%s] Not buying %f %s (insufficient balance or not amount provided)!" % (m, buy_amount * buy_price, base))
