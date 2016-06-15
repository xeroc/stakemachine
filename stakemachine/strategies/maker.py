from .basestrategy import BaseStrategy, MissingSettingsException
# import math
# from numpy import linspace


class MakerSellBuyWalls(BaseStrategy):
    """ Play Buy/Sell Walls into a market

        **Settings**:

        * **target_price**: target_price to place Ramps around (floating number or "feed")
        * **target_price_offset_percentage**: +-percentage offset from target_price
        * **spread_percentage**: Another "offset". Allows a spread. The lowest orders will be placed here
        * **volume_percentage**: The amount of funds (%) you want to use
        * **symmetric_sides**: (boolean) Place symmetric walls on both sides?
        * **only_buy**: Serve only on of both sides
        * **only_sell**: Serve only on of both sides
        * **expiration**: Expiration time of the order in seconds

        .. code-block:: yaml

             MakerWall:
                  module: "stakemachine.strategies.maker"
                  bot: "MakerSellBuyWalls"
                  markets :
                   - "TEMPA:LIVE"
                  target_price: 10.0
                  target_price_offset_percentage: 0
                  spread_percentage: 15
                  volume_percentage: 10
                  symmetric_sides: True
                  only_buy: False
                  only_sell: False

        .. note:: This module does not watch your orders, all it does is
                  place new orders!
    """
    delayState = "waiting"
    delayCounter = 0
    refreshMarkets = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def init(self):
        """ set default settings
        """
        if "target_price_offset_percentage" not in self.settings:
            self.settings["target_price_offset_percentage"] = 0.0

        if "target_price" not in self.settings:
            raise MissingSettingsException("target_price")

        if "spread_percentage" not in self.settings:
            raise MissingSettingsException("spread_percentage")

        if "volume_percentage" not in self.settings:
            raise MissingSettingsException("volume_percentage")

        if "symmetric_sides" not in self.settings:
            self.settings["symmetric_sides"] = True

        if "expiration" not in self.settings or not self.settings["expiration"]:
            self.settings["expiration"] = 60 * 60 * 24 * 7

        if "delay" not in self.settings:
            self.settings["delay"] = 3

    def orderFilled(self, oid):
        self.ensureOrders()

    def tick(self, *args, **kwargs):
        self.ensureOrders()

        if self.delayState == "updating":
            print("Refreshing markets %s" % str(self.refreshMarkets))
            self.cancel_mine(markets=self.refreshMarkets)
            self.place(markets=self.refreshMarkets)
            # reset
            self.delayState = "waiting"
            self.delayCounter = 0
            self.refreshMarkets = []

        if self.delayState == "counting":
            self.delayCounter += 1
            if self.delayCounter > self.settings["delay"]:
                self.delayState = "updating"

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
        if self.delayState == "waiting":
            myOrders = self.getMyOrders()
            for market in self.settings["markets"]:
                if len(myOrders[market]) != 2:
                    self.refreshMarkets.append(market)
            self.refreshMarkets = list(set(self.refreshMarkets))
            if self.refreshMarkets:
                self.delayState = "counting"

    def place(self, markets=None) :
        if not markets:
            markets = self.settings["markets"]
        """ Place all orders according to the settings.
        """
        print("Placing Orders:")
        target_price = self.settings["target_price"]
        only_sell = True if "only_sell" in self.settings and self.settings["only_sell"] else False
        only_buy = True if "only_buy" in self.settings and self.settings["only_buy"] else False

        #: Amount of Funds available for trading (per asset)
        balances = self.returnBalances()
        asset_ids = []
        amounts = {}
        for market in markets:
            quote, base = market.split(self.config.market_separator)
            asset_ids.append(base)
            asset_ids.append(quote)
        assets_unique = list(set(asset_ids))
        for a in assets_unique:
            if a in balances :
                amounts[a] = balances[a] * self.settings["volume_percentage"] / 100 / asset_ids.count(a)

        ticker = self.dex.returnTicker()
        for m in markets:

            if isinstance(target_price, float) or isinstance(target_price, int):
                base_price = float(target_price) * (1 + self.settings["target_price_offset_percentage"] / 100)
            elif isinstance(target_price, str):
                if (target_price is "settlement_price" or
                        target_price is "feed" or
                        target_price is "price_feed"):
                    if "settlement_price" in ticker[m] :
                        base_price = ticker[m]["settlement_price"] * (1 + self.settings["target_price_offset_percentage"] / 100)
                    else :
                        raise Exception("Pair %s does not have a settlement price!" % m)
                elif target_price == "last":
                    base_price = ticker[m]["last"] * (1 + self.settings["target_price_offset_percentage"] / 100)
                else:
                    raise Exception("Invalid option for 'target_price'")

            buy_price  = base_price * (1.0 - self.settings["spread_percentage"] / 200)
            sell_price = base_price * (1.0 + self.settings["spread_percentage"] / 200)

            quote, base = m.split(self.config.market_separator)
            if quote in amounts and not only_buy:
                if "symmetric_sides" in self.settings and self.settings["symmetric_sides"] and not only_sell:
                    thisAmount = min([amounts[quote], amounts[base] / buy_price]) if base in amounts else amounts[quote]
                    self.sell(m, sell_price, thisAmount, self.settings["expiration"])
                else :
                    self.sell(m, sell_price, amounts[quote], self.settings["expiration"])
            if base in amounts and not only_sell:
                if "symmetric_sides" in self.settings and self.settings["symmetric_sides"] and not only_buy:
                    thisAmount = min([amounts[quote], amounts[base] / buy_price]) if quote in amounts else amounts[base] / buy_price
                    self.buy(m, buy_price, thisAmount, self.settings["expiration"])
                else :
                    self.buy(m, buy_price, amounts[base] / buy_price, self.settings["expiration"])


#class MakerRamp(BaseStrategy):
#
#    """ Play Buy/Sell Walls into a market
#
#        **Settings**:
#
#        * **target_price**: target_price to place Ramps around (floating number or "feed")
#        * **target_price_offset_percentage**: +-percentage offset from target_price
#        * **spread_percentage**: Another "offset". Allows a spread. The lowest orders will be placed here
#        * **volume_percentage**: The amount of funds (%) you want to use
#        * **only_buy**: Serve only on of both sides
#        * **only_sell**: Serve only on of both sides
#        * **ramp_mode**: "linear" ramp (equal amounts) or "exponential" (linearily increasing amounts)
#        * **ramp_price_percentage**: Ramp goes up with volume up to a price increase of x%
#        * **ramp_step_percentage**: from spread/2 to ramp_price, place an order every x%
#        * **expiration**: Expiration time of the order in seconds
#
#        .. code-block:: yaml
#
#            MakerRexp:
#                module: "stakemachine.strategies.maker"
#                bot: "MakerRamp"
#                markets:
#                    - "USD:BTS"
#                target_price: "feed"
#                target_price_offset_percentage: 5
#                spread_percentage: 0.2
#                volume_percentage: 30
#                ramp_price_percentage: 2
#                ramp_step_percentage: 0.3
#                ramp_mode: "linear"
#                only_buy: False
#                only_sell: False
#                expiration: 21400
#
#        .. note:: This module does not watch your orders, all it does is
#                  place new orders!
#
#    """
#
#    def __init__(self, *args, **kwargs):
#        super().__init__(*args, **kwargs)
#        self.delayCounter = 0
#        self.delayStarted = False
#        self.refreshNow = False
#        self.refreshMarkets = []
#
#    def init(self) :
#        """ set default settings
#        """
#        if "target_price_offset_percentage" not in self.settings:
#            self.settings["target_price_offset_percentage"] = 0.0
#
#        if "target_price" not in self.settings:
#            raise MissingSettingsException("target_price")
#
#        if "spread_percentage" not in self.settings:
#            raise MissingSettingsException("spread_percentage")
#
#        if "volume_percentage" not in self.settings:
#            raise MissingSettingsException("volume_percentage")
#
#        if "ramp_price_percentage" not in self.settings:
#            raise MissingSettingsException("ramp_price_percentage")
#
#        if "ramp_step_percentage" not in self.settings:
#            raise MissingSettingsException("ramp_step_percentage")
#
#        if "ramp_mode" not in self.settings:
#            self.settings["ramp_mode"] = "linear"
#
#        if "expiration" not in self.settings:
#            self.settings["expiration"] = 60 * 60 * 24 * 7
#
#        if "delay" not in self.settings:
#            self.settings["delay"] = 3
#
#        self.ensureOrders()
#
#    def orderFilled(self, oid):
#        """ Do nothing, when an order is Filled
#        """
#        self.ensureOrders()
#
#    def tick(self, *args, **kwargs):
#        """ Do nothing
#        """
#        if self.delayStarted:
#            self.delayCounter += 1
#            if self.delayCounter > self.settings["delay"]:
#                self.refreshNow = True
#                self.delayCounter = 0
#
#        if self.refreshNow:
#            print("Refreshing markets %s" % str(self.refreshMarkets))
#            self.cancel_mine(markets=self.refreshMarkets)
#            self.place(markets=self.refreshMarkets)
#            self.delayStarted = False
#            self.refreshNow = False
#
#    def orderPlaced(seld, *args, **kwargs):
#        """ Do nothing
#        """
#        pass
#
#    def ensureOrders(self):
#        """ Make sure that there are two orders open for this bot. If
#            not, place them!
#        """
#        if not self.delayStarted:
#            myOrders = self.getMyOrders()
#            for market in self.settings["markets"]:
#                if len(myOrders[market]) != 2:
#                    self.refreshMarkets.append(market)
#            if self.refreshMarkets:
#                self.delayStarted = True
#
#    def place(self, markets=None) :
#        if not markets:
#            markets = self.settings["markets"]
#        """ Place all orders according to the settings.
#        """
#        print("Placing Orders:")
#        #: Amount of Funds available for trading (per asset)
#        if "ramp_mode" not in self.settings:
#            mode = "linear"
#        else :
#            mode = self.settings["ramp_mode"]
#        target_price = self.settings["target_price"]
#        only_sell = True if "only_sell" in self.settings and self.settings["only_sell"] else False
#        only_buy = True if "only_buy" in self.settings and self.settings["only_buy"] else False
#
#        balances = self.returnBalances()
#        asset_ids = []
#        amounts = {}
#        for market in markets:
#            quote, base = market.split(self.config.market_separator)
#            asset_ids.append(base)
#            asset_ids.append(quote)
#        assets_unique = list(set(asset_ids))
#        for a in assets_unique:
#            if a in balances :
#                amounts[a] = balances[a] * self.settings["volume_percentage"] / 100 / asset_ids.count(a)
#
#        ticker = self.dex.returnTicker()
#        for m in markets:
#
#            quote, base = m.split(self.config.market_separator)
#            if isinstance(target_price, float) or isinstance(target_price, int):
#                base_price = float(target_price)
#            elif isinstance(target_price, str):
#                if(target_price is "settlement_price" or
#                        target_price is "feed" or
#                        target_price is "price_feed"):
#                    if "settlement_price" in ticker[m] :
#                        base_price = ticker[m]["settlement_price"]
#                    else :
#                        raise Exception("Pair %s does not have a settlement price!" % m)
#                elif target_price == "last":
#                    base_price = ticker[m]["last"] * (1 + self.settings["target_price_offset_percentage"] / 100)
#                else:
#                    raise Exception("Invalid option for 'target_price'")
#            else:
#                raise Exception("Invalid target_price!")
#
#            base_price = base_price * (1 + self.settings["target_price_offset_percentage"] / 100)
#
#            if quote in amounts and not only_buy:
#                price_start  = base_price * (1 + self.settings["spread_percentage"] / 200.0)
#                price_end    = base_price * (1 + self.settings["ramp_price_percentage"] / 100.0)
#                if not only_sell :
#                    amount       = min([amounts[quote], amounts[base] / (price_start)]) if base in amounts else amounts[quote]
#                else:
#                    amount = amounts[quote]
#                number_orders = math.floor((self.settings["ramp_price_percentage"] / 100.0 - self.settings["spread_percentage"] / 200.0) / (self.settings["ramp_step_percentage"] / 100.0))
#                if mode == "linear" :
#                    for price in linspace(price_start, price_end, number_orders) :
#                        self.sell(m, price, amount / number_orders, self.settings["expiration"])
#                elif mode == "exponential" :
#                    k = linspace(1 / number_orders, 1, number_orders)
#                    k = [v / sum(k) for v in k]
#                    order_amounts = [v * amount for v in k]
#                    for i, price in enumerate(linspace(price_start, price_end, number_orders)):
#                        self.sell(m, price, order_amounts[i], self.settings["expiration"])
#                else :
#                    raise Exception("ramp_mode '%s' not known" % mode)
#
#            if base in amounts and not only_sell:
#                price_start  = base_price * (1 - self.settings["spread_percentage"] / 200.0)
#                price_end    = base_price * (1 - self.settings["ramp_price_percentage"] / 100.0)
#                if not only_buy:
#                    amount       = min([amounts[quote], amounts[base] / (price_start)]) if quote in amounts else amounts[base] / (price_start)
#                else:
#                    amount = amounts[base] / price_start
#                number_orders = math.floor((self.settings["ramp_price_percentage"] / 100.0 - self.settings["spread_percentage"] / 200.0) / (self.settings["ramp_step_percentage"] / 100.0))
#                if mode == "linear" :
#                    for price in linspace(price_start, price_end, number_orders) :
#                        self.buy(m, price, amount / number_orders, self.settings["expiration"])
#                elif mode == "exponential" :
#                    k = linspace(1 / number_orders, 1, number_orders)
#                    k = [v / sum(k) for v in k]
#                    order_amounts = [v * amount for v in k]
#                    for i, price in enumerate(linspace(price_start, price_end, number_orders)):
#                        self.buy(m, price, order_amounts[i], self.settings["expiration"])
#                else :
#                    raise Exception("ramp_mode '%s' not known" % mode)
