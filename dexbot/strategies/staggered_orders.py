import math

from dexbot.basestrategy import BaseStrategy
from dexbot.queue.idle_queue import idle_add


class Strategy(BaseStrategy):
    """ Staggered Orders strategy
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Define Callbacks
        self.onMarketUpdate += self.check_orders
        self.onAccount += self.check_orders

        self.error_ontick = self.error
        self.error_onMarketUpdate = self.error
        self.error_onAccount = self.error

        self.worker_name = kwargs.get('name')
        self.view = kwargs.get('view')
        self.amount = self.worker['amount']
        self.spread = self.worker['spread'] / 100
        self.increment = self.worker['increment'] / 100
        self.upper_bound = self.worker['upper_bound']
        self.lower_bound = self.worker['lower_bound']

        self.check_orders()

    def error(self, *args, **kwargs):
        self.cancel_all()
        self.disabled = True
        self.log.info(self.execute())

    def init_strategy(self):
        # Make sure no orders remain
        self.cancel_all()
        self.clear_orders()

        center_price = self.calculate_center_price()

        # Calculate buy prices
        buy_prices = []
        buy_price = center_price / math.sqrt(1 + self.spread)
        while buy_price > self.lower_bound:
            buy_prices.append(buy_price)
            buy_price = buy_price * (1 - self.increment)

        # Calculate sell prices
        sell_prices = []
        sell_price = center_price * math.sqrt(1 + self.spread)
        while sell_price < self.upper_bound:
            sell_prices.append(sell_price)
            sell_price = sell_price * (1 + self.increment)

        # Calculate buy amounts
        highest_buy_price = buy_prices.pop(0)
        buy_orders = [{'amount': self.amount, 'price': highest_buy_price}]
        for buy_price in buy_prices:
            last_amount = buy_orders[-1]['amount']
            amount = last_amount / math.sqrt(1 + self.increment)
            buy_orders.append({'amount': amount, 'price': buy_price})

        # Calculate sell amounts
        lowest_sell_price = highest_buy_price * math.sqrt(1 + self.spread + self.increment)
        sell_orders = [{'amount': self.amount, 'price': lowest_sell_price}]
        for sell_price in sell_prices:
            last_amount = sell_orders[-1]['amount']
            amount = last_amount / math.sqrt(1 + self.increment)
            sell_orders.append({'amount': amount, 'price': sell_price})

        # Make sure there is enough balance for the buy orders
        needed_buy_asset = 0
        for buy_order in buy_orders:
            needed_buy_asset += buy_order['amount'] * buy_order['price']
        if self.balance(self.market["base"]) < needed_buy_asset:
            self.log.critical(
                "Insufficient buy balance, needed {} {}".format(needed_buy_asset, self.market['base']['symbol'])
            )
            self.disabled = True
            return

        # Make sure there is enough balance for the sell orders
        needed_sell_asset = 0
        for sell_order in sell_orders:
            needed_sell_asset += sell_order['amount']
        if self.balance(self.market["quote"]) < needed_sell_asset:
            self.log.critical(
                "Insufficient sell balance, needed {} {}".format(needed_sell_asset, self.market['quote']['symbol'])
            )
            self.disabled = True
            return

        # Place the buy orders
        for buy_order in buy_orders:
            order = self.market_buy(buy_order['amount'], buy_order['price'])
            self.save_order(order)

        # Place the sell orders
        for sell_order in sell_orders:
            order = self.market_sell(sell_order['amount'], sell_order['price'])
            self.save_order(order)

        self['setup_done'] = True

    def replace_order(self, order):
        self.log.info('Change detected, updating orders')
        self.remove_order(order)

        if order['base']['symbol'] == self.market['base']['symbol']:  # Buy order
            amount = order['quote']['amount']
            price = order['price'] * self.spread
            new_order = self.market_sell(amount, price)
        else:  # Sell order
            amount = order['base']['amount']
            price = order['price'] / self.spread
            new_order = self.market_buy(amount, price)

        self.save_order(new_order)

    def check_orders(self, *args, **kwargs):
        """ Tests if the orders need updating
        """
        if not self['setup_done']:
            self.init_strategy()

        orders = self.fetch_orders()
        for order in orders:
            current_order = self.get_order(order)
            if not current_order:
                self.replace_order(order)

        if self.view:
            self.update_gui_profit()
            self.update_gui_slider()

    # GUI updaters
    def update_gui_profit(self):
        pass

    def update_gui_slider(self):
        pass
