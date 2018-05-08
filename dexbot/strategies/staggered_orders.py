from dexbot.basestrategy import BaseStrategy
from dexbot.queue.idle_queue import idle_add

from bitshares.amount import Amount


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
        self.spread = self.worker['spread']
        self.increment = self.worker['increment']
        self.upper_bound = self.worker['upper_bound']
        self.lower_bound = self.worker['lower_bound']

        self.check_orders()

    def error(self, *args, **kwargs):
        self.cancel_all()
        self.disabled = True
        self.log.info(self.execute())

    def init_strategy(self):
        center_price = self.calculate_center_price()
        buy_prices = []
        buy_price = center_price * (1 + self.spread / 2)
        buy_prices.append(buy_price)

        while buy_price > self.lower_bound:
            buy_price = buy_price / (1 + self.increment)
            buy_prices.append(buy_price)

        sell_prices = []
        sell_price = center_price * (1 - self.spread / 2)
        sell_prices.append(sell_price)

        while sell_price < self.upper_bound:
            sell_price = sell_price * (1 + self.increment)
            sell_prices.append(sell_price)

        self['orders'] = []

    def update_order(self, order, order_type):
        self.log.info('Change detected, updating orders')
        # Make sure
        self.cancel(order)

        if order_type == 'buy':
            amount = order['quote']['amount']
            price = order['price'] * self.spread
            new_order = self.market_sell(amount, price)
        else:
            amount = order['base']['amount']
            price = order['price'] / self.spread
            new_order = self.market_buy(amount, price)

        self['orders'] = new_order

    def check_orders(self, *args, **kwargs):
        """ Tests if the orders need updating
        """
        for order in self['sell_orders']:
            current_order = self.get_updated_order(order)
            if current_order['quote']['amount'] != order['quote']['amount']:
                self.update_order(order, 'sell')

        for order in self['buy_orders']:
            current_order = self.get_updated_order(order)
            if current_order['quote']['amount'] != order['quote']['amount']:
                self.update_order(order, 'buy')

        if self.view:
            self.update_gui_profit()
            self.update_gui_slider()

    # GUI updaters
    def update_gui_profit(self):
        pass

    def update_gui_slider(self):
        pass
