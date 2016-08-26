from .basestrategy import MissingSettingsException
from .advanced_basestrategy import AdvancedBaseStrategy
from datetime import datetime
import math
import logging
import time


logging.basicConfig(level=logging.INFO)


class LiquiditySellBuyWalls(AdvancedBaseStrategy):
    """ Puts up buy/sell walls at a specific spread in the market, replacing orders as the price changes.

        **Settings**:

        * **minimum_amounts**: the minimum amount an order has to be
        * **target_price**: target_price to place walls around (floating number or "feed")
        * **spread_percentage**: Another "offset". Allows a spread. The lowest orders will be placed here
        * **allowed_spread_percentage**: The allowed spread an order may have before it gets replaced
        * **volume_percentage**: The amount of funds (%) you want to use
        * **expiration**: Expiration time of the order in seconds
        * **ratio**: The desired collateral ratio (same as maintain_collateral_ratio.py)


        * **skip_blocks**: Runs the bot logic only every x blocks

        .. code-block:: yaml

            LiquidityWall:
                module: "stakemachine.strategies.liquidity_wall"
                bot: "LiquiditySellBuyWalls"
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
                place_order_strategy: "spread_percentage"
                spread_percentage: 5
                amount_calculation: "volume_percentage"
                volume_percentage: 70
                allowed_spread_percentage: 2.5
                symmetric_sides: False
                expiration: 21600
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

        if "volume_percentage" not in self.settings:
            raise MissingSettingsException("volume_percentage")

        if "symmetric_sides" not in self.settings:
            self.settings["symmetric_sides"] = False

        if "expiration" not in self.settings or not self.settings["expiration"]:
            self.settings["expiration"] = 60 * 60 * 24

        if "delay" not in self.settings:
            self.settings["delay"] = 0

        time.sleep(1) # looks like part of the config is missing without waiting a second.


    def place(self, markets=None, only_sell=False, only_buy=False) :
        if not markets:
            markets = self.settings["markets"]

        for m in markets:
            if self.settings["place_order_strategy"] == "walls":
                self.place_walls(m, only_buy, only_sell)

    def get_order_prices(self, base_price):
        if self.settings['place_order_price_strategy'] == "spread_percentage_walls":
            return self.order_prices_spread_percentage(base_price)
        elif self.settings['place_order_price_strategy'] == "set_amount_walls":
            return self.order_prices_set_amount(base_price)

    def order_prices_spread_percentage(self, base_price):
        buy_price  = base_price * (1.0 - self.settings["spread_percentage"] / 200)
        sell_price = base_price * (1.0 + self.settings["spread_percentage"] / 200)
        return (buy_price, sell_price)

    def order_prices_set_amount(self, base_price):
        buy_price = base_price + self.settings["set_amount"]
        sell_price = base_price - self.settings["set_amount"]
        return (buy_price, sell_price)

    def place_walls(self, m, only_buy, only_sell):
        amounts = self.get_amounts()
        base_price = self.get_price(m)
        if base_price:
            buy_price, sell_price = self.get_order_prices(base_price)
            quote, base = m.split(self.config.market_separator)
            if quote in amounts and not only_buy:
                if "symmetric_sides" in self.settings and self.settings["symmetric_sides"] and not only_sell:
                    amount = min([amounts[quote], amounts[base] / buy_price]) if base in amounts else amounts[quote]
                    if self.validate_order("sell", quote, sell_price, amount):
                        self.sell(m, sell_price, amount, self.settings["expiration"])
                else :
                    amount = amounts[quote]
                    if self.validate_order("sell", quote, sell_price, amount):
                        self.sell(m, sell_price, amount, self.settings["expiration"])
            if base in amounts and not only_sell:
                if "symmetric_sides" in self.settings and self.settings["symmetric_sides"] and not only_buy:
                    amount = min([amounts[quote], amounts[base] / buy_price]) if quote in amounts else amounts[base] / buy_price
                    if self.validate_order("buy", quote, buy_price, amount):
                        self.buy(m, buy_price, amount, self.settings["expiration"])
                else:
                    amount = amounts[base] / buy_price
                    if self.validate_order("buy", quote, buy_price, amount):
                        self.buy(m, buy_price, amount, self.settings["expiration"])
        else:
            logging.warning("No price available for %s" % m)


    def verify_place_orders(self, m):
        if self.settings["place_order_strategy"] == "walls":
            self.verify_place_orders_walls(m)

    def verify_place_orders_walls(self, m):
        base_price = self.get_price(m)
        if base_price:
            buy_price, sell_price = self.get_order_prices(base_price)
            if buy_price and sell_price:
                if len(self.open_orders[m]) == 0:
                    self.refreshMarkets.append(m)
                if len(self.open_orders[m]) == 1:
                    if self.open_orders[m][0]['type'] == "sell":
                        self.place(markets=[m], only_buy=True)
                    elif self.open_orders[m][0]['type'] == "buy":
                        self.place(markets=[m], only_sell=True)
                for o in self.open_orders[m]:
                    order_feed_spread = math.fabs((o["rate"] - self.ticker[m]["settlement_price"]) / self.ticker[m]["settlement_price"] * 100)
                    logging.info("%s | Order: %s is %.3f%% away from feed" % (datetime.now(), o['orderNumber'], order_feed_spread))
                    if order_feed_spread <= self.settings["allowed_spread_percentage"] / 2 or order_feed_spread >= (self.settings["allowed_spread_percentage"] + self.settings["spread_percentage"]) / 2:
                        self.refreshMarkets.append(m)
        else:
            logging.warning("No price available for %s" % m)