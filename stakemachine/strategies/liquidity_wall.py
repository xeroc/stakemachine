from .basestrategy import BaseStrategy, MissingSettingsException
from datetime import datetime
import math

class LiquidityWallReloaded(BaseStrategy):

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

        if "volume_percentage" not in self.settings:
            raise MissingSettingsException("volume_percentage")

        if "symmetric_sides" not in self.settings:
            self.settings["symmetric_sides"] = True

        if "expiration" not in self.settings or not self.settings["expiration"]:
            self.settings["expiration"] = 60 * 60 * 24

        if "delay" not in self.settings:
            self.settings["delay"] = 3

    def update_data(self):
        self.ticker = self.dex.returnTicker()
        self.open_orders = self.getMyOrders()
        self.balances = self.dex.returnBalances()
        self.filled_orders = self.get_filled_orders_data()

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

    def ensureOrders(self):
        if self.delayState == "waiting":
            self.update_data()
            for market in self.settings["markets"]:
                base_price = self.get_price(market)
                if base_price:
                    buy_price, sell_price = self.get_place_order_price(base_price)
                    if buy_price and sell_price:
                        if len(self.open_orders[market]) == 0:
                            self.refreshMarkets.append(market)
                        if len(self.open_orders[market]) == 1:
                            if self.open_orders[market][0]['type'] == "sell":
                                self.place(market, only_buy=True)
                            elif self.open_orders[market][0]['type'] == "buy":
                                self.place(market, only_sell=True)
                        for o in self.open_orders[market]:
                            order_feed_spread = math.fabs((o["rate"] - self.ticker[market]["settlement_price"]) / self.ticker[market]["settlement_price"] * 100)
                            print("%s | Order: %s is %.3f%% away from feed" % (datetime.now(), o['orderNumber'], order_feed_spread))
                            if order_feed_spread <= self.settings["allowed_spread_percentage"] / 2 or order_feed_spread >= (self.settings["allowed_spread_percentage"] + self.settings["spread_percentage"]) / 2:
                                self.refreshMarkets.append(market)
                else:
                    print("NO PRICE AVAILABLE WARNING")
            self.refreshMarkets = list(set(self.refreshMarkets))
            if self.refreshMarkets:
                self.delayState = "counting"

    def place(self, markets=None, only_sell=False, only_buy=False) :
        if not markets:
            markets = self.settings["markets"]

        for m in markets:
            balances = self.dex.returnBalances()
            asset_ids = []
            amounts = {}
            for single_market in self.settings["markets"]:
                quote, base = single_market.split(self.config.market_separator)
                asset_ids.append(base)
                asset_ids.append(quote)
            assets_unique = list(set(asset_ids))
            for a in assets_unique:
                if a in balances:
                    amounts[a] = balances[a] * self.settings["volume_percentage"] / 100 / asset_ids.count(a)
            base_price = self.get_price(m)
            if base_price:
                buy_price, sell_price = self.get_place_order_price(base_price)
                quote, base = m.split(self.config.market_separator)
                if quote in amounts and not only_buy:
                    if "symmetric_sides" in self.settings and self.settings["symmetric_sides"] and not only_sell:
                        amount = min([amounts[quote], amounts[base] / buy_price]) if base in amounts else amounts[quote]
                        if self.validate_amount(amount, quote):
                            self.sell(m, sell_price, amount, self.settings["expiration"])
                    else :
                        amount = amounts[quote]
                        if self.validate_amount(amount, quote):
                            self.sell(m, sell_price, amount, self.settings["expiration"])
                if base in amounts and not only_sell:
                    if "symmetric_sides" in self.settings and self.settings["symmetric_sides"] and not only_buy:
                        amount = min([amounts[quote], amounts[base] / buy_price]) if quote in amounts else amounts[base] / buy_price
                        if self.validate_amount(amount, quote):
                            self.buy(m, buy_price, amount, self.settings["expiration"])
                    else:
                        amount = amounts[base] / buy_price
                        if self.validate_amount(amount, quote):
                            self.buy(m, buy_price, amount, self.settings["expiration"])
            else:
                print("NO PRICE AVAILABLE WARNING")

    def orderFilled(self, oid):
        self.ensureOrders()

    def orderPlaced(self, *args, **kwargs):
        pass

    def get_filled_orders_data(self):
        filled_orders_markets = {}
        for market in self.settings["markets"]:
            quote_symbol, base_symbol = market.split(self.config.market_separator)
            base_id = self.dex.rpc.get_asset(base_symbol)['id']
            quote_id = self.dex.rpc.get_asset(quote_symbol)['id']
            m = {"base": base_id, "quote": quote_id}
            filled_orders = self.dex.ws.get_fill_order_history(quote_id, base_id, 1000, api="history")
            price_list = []
            for order in filled_orders:
                timestamp = datetime.strptime(order['time'], "%Y-%m-%dT%H:%M:%S")
                seconds_ago = (datetime.now() - timestamp).total_seconds()
                op = order['op']
                if seconds_ago <= self.settings["filled_order_age"]:
                    price_data = {
                        "price": self.dex._get_price_filled(order, m),
                        "seconds_ago": (datetime.now() - timestamp).total_seconds(),
                        "volume": op['pays']['amount'] if op['pays']['asset_id'] == quote_id else op['receives']['amount']
                    }
                    price_list.append(price_data)
            filled_orders_markets[market] = price_list
        return filled_orders_markets

    def price_filled_orders(self, market):
        price_list = self.filled_orders[market]
        price_weight_total = sum([order['volume'] * (1 / (self.settings["time_weight_factor"] * order['seconds_ago'])) * order['price'] for order in price_list])
        weight_total = sum([order['volume'] * (1 / (self.settings["time_weight_factor"] * order['seconds_ago'])) for order in price_list])
        volume_total = sum([order['volume'] for order in price_list])
        try:
            price = (price_weight_total / weight_total)
        except ZeroDivisionError:
            return None
        else:
            return price if volume_total >= self.settings["minimum_volume"] else None

    def price_feed(self, market):
        if "settlement_price" in self.ticker[market]:
            return(self.ticker[market]["settlement_price"] * (1 + self.settings["target_price_offset_percentage"] / 100))
        else:
            raise Exception("Pair %s does not have a settlement price!" % market)

    def price_target(self, market):
        return float(self.settings['target_price']) * (1 + self.settings["target_price_offset_percentage"] / 100)

    def price_bid_ask(self, market):
        return (self.ticker[market]['highestBid'] + self.ticker[market]['lowestAsk']) / 2

    def price_last(self, market):
        return self.ticker[market]['last']

    def get_price(self, market):
        target_price = self.settings['target_price']
        if isinstance(target_price, float) or isinstance(target_price, int):
            return self.price_target
        elif (isinstance(target_price, str) and
            target_price is "settlement_price" or
            target_price is "feed" or
            target_price is "price_feed"):
            return self.price_feed(market)
        elif (isinstance(target_price, str) and
            target_price is "filled_orders"):
            return self.price_filled_orders(market)
        elif (isinstance(target_price, str) and
            target_price is "bid_ask" or
            target_price is "gap"):
            return self.price_bid_ask(market)
        elif (isinstance(target_price, str) and
            target_price is "last"):
            return self.price_last(market)

        if isinstance(target_price, dict):
            price_weight_sum = sum([self.get_price(market, target_price=target) * weight for target, weight in target_price.items() if self.get_price(market, target_price=target) > 0])
            weight_sum = sum([weight for target, weight in target_price.items() if self.get_price(market, target_price=target) > 0])
            try:
                return price_weight_sum / weight_sum
            except ZeroDivisionError:
                return None

    def get_place_order_price(self, base_price):
        if self.settings['place_order_strategy'] is "spread_percentage":
            return self.price_spread_percentage(base_price)
        elif self.settings['place_order_strategy'] is "set_amount":
            return self.price_set_amount(base_price)

    def price_orders_spread_percentage(self, base_price):
        buy_price  = base_price * (1.0 - self.settings["spread_percentage"] / 200)
        sell_price = base_price * (1.0 + self.settings["spread_percentage"] / 200)
        return (buy_price, sell_price)

    def price_set_amount(self, base_price):
        buy_price = base_price + self.settings["set_amount"]
        sell_price = base_price - self.settings["set_amount"]
        return (buy_price, sell_price)

    def validate_amount(self, amount, quote):
        for validator in self.settings["amount_validators"]:
            if validator is "minimum_amounts":
                valid = self.minimum_amount(amount, quote)
            elif validator is "maximum_amount":
                valid = self.maximum_amount(amount, quote)
            if not valid:
                return False
        return True

    def minimum_amount(self, amount, quote):
        return amount >= self.settings["amount_validators"]["minimum_amounts"][quote]

    def maximum_amount(self, amount, quote):
        return amount <= self.settings["amount_validators"]["maximum_amounts"][quote]
