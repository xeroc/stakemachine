from .basestrategy import BaseStrategy, MissingSettingsException
import logging
log = logging.getLogger(__name__)
# import math
# from numpy import linspace


class MakerSellBuyWalls(BaseStrategy):
    """ Play Buy/Sell Walls into a market

        **Settings**:

        * **target_price**: target_price to place Ramps around (floating number or "feed")
        * **spread_percentage**: Another "offset". Allows a spread. The lowest orders will be placed here
        * **only_buy**: Serve only on of both sides
        * **only_sell**: Serve only on of both sides
        * **expiration**: Expiration time of the order in seconds
        * **amount**: Definition of the amounts to be used

        .. code-block:: yaml

             MakerWall:
                  module: "stakemachine.strategies.maker"
                  bot: "MakerSellBuyWalls"
                  markets :
                   - "TEMPA:LIVE"
                  target_price: 10.0
                  spread_percentage: 15
                  only_buy: False
                  only_sell: False
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

        .. note:: This module does not watch your orders, all it does is
                  place new orders!
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def init(self):
        """ set default settings
        """
        if "target_price" not in self.settings:
            raise MissingSettingsException("target_price")

        if "spread_percentage" not in self.settings:
            raise MissingSettingsException("spread_percentage")

        self.settings["expiration"] = self.settings.get("expiration", 60 * 60 * 24 * 7)
        self.settings["delay"] = self.settings.get("delay", 5)
        self.settings["offset"] = self.settings.get("offset", 0)
        self.refreshMarkets = []

    def orderFilled(self, oid):
        self.ensureOrders()

    def orderCanceled(self, oid):
        pass

    def tick(self, *args, **kwargs):
        self.ensureOrders()

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
        """ Do nothing
        """
        pass

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
            myOrders = self.getMyOrders()
            for market in self.settings["markets"]:
                # Update if one of the orders has been fully filled
                numOrders = 2
                if self.settings.get("only_buy", False):
                    numOrders -= 1
                if self.settings.get("only_sell", False):
                    numOrders -= 1
                if self._get(market, "insufficient_sell"):
                    numOrders -= 1
                if self._get(market, "insufficient_buy"):
                    numOrders -= 1
                if numOrders and len(myOrders[market]) != numOrders:
                    log.info("Expected %d orders, found %d." % (numOrders, len(myOrders[market])) +
                             " Goging to refresh market %s" % market)
                    self.refreshMarkets.append(market)

            # unique list
            self.refreshMarkets = list(set(self.refreshMarkets))
            if len(self.refreshMarkets):
                self.changeFSM("counting")

    def place(self, markets=None) :
        """ Place all orders according to the settings.
        """
        if not markets:
            markets = self.settings["markets"]
        target_price = self.settings["target_price"]

        only_sell = self.settings.get("only_sell", False)
        only_buy = self.settings.get("only_buy", False)

        ticker = self.dex.returnTicker()
        for m in markets:
            balances = self.dex.returnBalances()
            quote, base = m.split(self.config.market_separator)

            # Get price relation (base price)
            if isinstance(target_price, float) or isinstance(target_price, int):
                base_price = float(target_price)
            elif isinstance(target_price, str):
                if (target_price is "settlement_price" or
                        target_price is "feed" or
                        target_price is "price_feed"):
                    if "settlement_price" in ticker[m] :
                        base_price = ticker[m]["settlement_price"]
                    else :
                        log.critical("Pair %s does not have a settlement price!" % m)
                        continue
                elif target_price == "last":
                    base_price = ticker[m]["last"]
                else:
                    log.critical("Invalid option for 'target_price'")
                    continue

            # offset
            base_price = base_price * (1.0 + self.settings["offset"] / 100)
            # spread
            buy_price  = base_price * (1.0 - self.settings["spread_percentage"] / 200)
            sell_price = base_price * (1.0 + self.settings["spread_percentage"] / 200)

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

            if not only_buy and sell_amount < balances.get(quote, 0):
                self.sell(m, sell_price, sell_amount, returnID=True)
                self._set(m, "insufficient_sell", False)
            else:
                log.info("[%s] You don't have %f %s!" % (m, sell_amount, quote))
                self._set(m, "insufficient_sell", True)

            if not only_sell and buy_amount * buy_price < balances.get(base, 0):
                self.buy(m, buy_price, buy_amount, returnID=True)
                self._set(m, "insufficient_buy", False)
            else:
                log.info("[%s] You don't have %f %s!" % (m, buy_amount * buy_price, base))
                self._set(m, "insufficient_buy", True)
