from .basestrategy import BaseStrategy, MissingSettingsException
from datetime import datetime
import logging
import time

class AdvancedBaseStrategy(BaseStrategy):
    """
        AdvancedBaseStrategy:
            module: "stakemachine.strategies.advanced_basestrategy"
            bot: "AdvancedBaseStrategy"
            markets:
                - "USD : BTS"
            amount_validators:
                minimum_amount:
                    USD: 0.2
            target_price:
                last: 0.5
                feed: 2
                gap: 1
                filled_orders: 0.7
            filled_order_age: 10000

    """
    delayState = "waiting"
    delayCounter = 0
    refreshMarkets = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def init(self):
        """ set default settings
        """

        if "target_price" not in self.settings:
            raise MissingSettingsException("target_price")

        if "delay" not in self.settings:
            self.settings["delay"] = 0

        if "time_weight_factor" not in self.settings:
            self.settings["time_weight_factor"] = 1

        time.sleep(1)  # looks like part of the config is missing without waiting a second.

    def update_data(self):
        if self.delayState == "waiting":
            self.ticker = self.dex.returnTicker()
            self.open_orders = self.dex.returnOpenOrders()
            self.balances = self.returnBalances()
            self.filled_orders = self.get_filled_orders_data()
            self.delayState = "updated"

    def tick(self, *args, **kwargs):
        self.update_data()
        self.ensureOrders()

        if self.delayState == "counting":
            self.delayCounter += 1
            if self.delayCounter > self.settings["delay"]:
                self.delayState = "replace"

        if self.delayState == "replace":
            logging.info("Refreshing markets %s" % str(self.refreshMarkets))
            self.cancel_orders(self.refreshMarkets)
            self.place(markets=self.refreshMarkets)
            # reset
            self.delayState = "waiting"
            self.delayCounter = 0
            self.refreshMarkets = []

    def ensureOrders(self):
        if self.delayState == "updated":
            for m in self.settings["markets"]:
                self.verify_place_orders(m)
            self.refreshMarkets = list(set(self.refreshMarkets))
            if self.refreshMarkets:
                self.delayState = "counting"
            else:
                self.delayState = "waiting"

    def place(self, markets=None, only_sell=False, only_buy=False) :
        if not markets:
            markets = self.settings["markets"]

        for m in markets:
            pass

    def cancel_orders(self, markets):
        """ Cancel all orders for all markets or a specific market
        """
        for market in markets:
            logging.info("%s | Cancelling orders for %s market(s)" % (datetime.now(), market))
            for order in self.open_orders[market]:
                try:
                    logging.info("Cancelling %s" % order["orderNumber"])
                    self.dex.cancel(order["orderNumber"])
                except Exception as e:
                    logging.warning("An error has occurred when trying to cancel order %s!" % order)
                    logging.warning(e)

    def orderFilled(self, oid):
        pass

    def orderPlaced(self, *args, **kwargs):
        pass

    def get_filled_orders_data(self):
        filled_orders_markets = {}
        for market in self.settings["markets"]:
            quote_symbol, base_symbol = market.split(self.config.market_separator)
            base_id = self.dex.ws.get_asset(base_symbol)['id']
            quote_id = self.dex.ws.get_asset(quote_symbol)['id']
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

    def price_target(self):
        return float(self.settings['target_price']) * (1 + self.settings["target_price_offset_percentage"] / 100)

    def price_bid_ask(self, market):
        return (self.ticker[market]['highestBid'] + self.ticker[market]['lowestAsk']) / 2

    def price_last(self, market):
        return self.ticker[market]['last']

    def get_price(self, market, target_price=None):
        if not target_price:
            target_price = self.settings['target_price']
        if isinstance(target_price, float) or isinstance(target_price, int):
            return self.price_target()
        elif (isinstance(target_price, str) and
            target_price == "settlement_price" or
            target_price == "feed" or
            target_price == "price_feed"):
            return self.price_feed(market)
        elif (isinstance(target_price, str) and
            target_price == "filled_orders"):
            return self.price_filled_orders(market)
        elif (isinstance(target_price, str) and
            target_price == "bid_ask" or
            target_price == "gap"):
            return self.price_bid_ask(market)
        elif (isinstance(target_price, str) and
            target_price == "last"):
            return self.price_last(market)

        if isinstance(target_price, dict):
            price_weight_sum = sum([self.get_price(market, target_price=target) * weight for target, weight in target_price.items() if self.get_price(market, target_price=target) != None])
            weight_sum = sum([weight for target, weight in target_price.items() if self.get_price(market, target_price=target) != None])
            try:
                return price_weight_sum / weight_sum
            except ZeroDivisionError:
                return None

    def get_order_prices(self, base_price):
        pass

    def validate_order(self, type, quote, price, amount):
        for validator in self.settings["validators"]:
            if validator == "minimum_amount":
                valid = self.minimum_amount(amount, quote)
            if not valid:
                return False
        return True

    def minimum_amount(self, amount, quote):
        return amount >= self.settings["validators"]["minimum_amount"][quote]

    def get_amounts(self):
        if self.settings["amount_calculation"] == "volume_percentage":
            return self.amounts_volume_percentage()

    def amounts_volume_percentage(self):
        amounts = {}
        asset_ids = []
        for single_market in self.settings["markets"]:
            quote, base = single_market.split(self.config.market_separator)
            asset_ids.append(base)
            asset_ids.append(quote)
            assets_unique = list(set(asset_ids))
        for a in assets_unique:
            if a in self.balances:
                amounts[a] = self.balances[a] * self.settings["volume_percentage"] / 100 / asset_ids.count(a)
        return amounts

    def verify_place_orders(self, m):
        pass
