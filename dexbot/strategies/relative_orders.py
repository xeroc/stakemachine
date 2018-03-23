from collections import Counter

from bitshares.amount import Amount
from bitshares.price import Price
from bitshares.price import Order

from dexbot.basestrategy import BaseStrategy
from dexbot.queue.idle_queue import idle_add


class Strategy(BaseStrategy):
    """
    Relative Orders strategy
    This strategy places a buy and a sell wall that change height over time
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Define Callbacks
        self.onMarketUpdate += self.test
        self.ontick += self.tick

        self.error_ontick = self.error
        self.error_onMarketUpdate = self.error
        self.error_onAccount = self.error

        # Counter for blocks
        self.counter = Counter()

        self.target = self.worker.get("target", {})
        self.is_center_price_dynamic = self.target["center_price_dynamic"]
        if self.is_center_price_dynamic:
            self.center_price = None
        else:
            self.center_price = self.target["center_price"]

        self.buy_price = None
        self.sell_price = None
        self.calculate_order_prices()

        self.initial_balance = self['initial_balance'] or 0
        self.worker_name = kwargs.get('name')
        self.view = kwargs.get('view')

    def calculate_order_prices(self):
        if self.is_center_price_dynamic:
            self.center_price = self.calculate_center_price

        self.buy_price = self.center_price * (1 - (self.target["spread"] / 2) / 100)
        self.sell_price = self.center_price * (1 + (self.target["spread"] / 2) / 100)

    def error(self, *args, **kwargs):
        self.disabled = True
        self.log.info(self.execute())

    def init_strategy(self):
        amount = self.target['amount'] / 2

        # Recalculate buy and sell order prices
        self.calculate_order_prices()

        # Buy Side
        if float(self.balance(self.market["base"])) < self.buy_price * amount:
            self.log.critical(
                'Insufficient buy balance, needed {} {}'.format(self.buy_price * amount, self.market['base']['symbol'])
            )
            self.disabled = True
        else:
            buy_transaction = self.market.buy(
                self.buy_price,
                Amount(amount=amount, asset=self.market["quote"]),
                account=self.account,
                returnOrderId="head"
            )
            buy_order = self.get_order(buy_transaction['orderid'])
            self.log.info('Placed a buy order for {} {} @ {}'.format(amount, self.market["quote"], self.buy_price))
            if buy_order:
                self['buy_order'] = buy_order

        # Sell Side
        if float(self.balance(self.market["quote"])) < amount:
            self.log.critical(
                "Insufficient sell balance, needed {} {}".format(amount, self.market['quote']['symbol'])
            )
            self.disabled = True
        else:
            sell_transaction = self.market.sell(
                self.sell_price,
                Amount(amount=amount, asset=self.market["quote"]),
                account=self.account,
                returnOrderId="head"
            )
            sell_order = self.get_order(sell_transaction['orderid'])
            self.log.info('Placed a sell order for {} {} @ {}'.format(amount, self.market["quote"], self.buy_price))
            if sell_order:
                self['sell_order'] = sell_order

        order_balance = self.orders_balance()
        self['initial_balance'] = order_balance  # Save to database
        self.initial_balance = order_balance

    def update_orders(self, new_sell_order, new_buy_order):
        """
        Update the orders
        """
        # Stored orders
        sell_order = self['sell_order']
        buy_order = self['buy_order']

        # Recalculate buy and sell order prices
        self.calculate_order_prices()

        sold_amount = 0
        if new_sell_order and new_sell_order['base']['amount'] < sell_order['base']['amount']:
            # Some of the sell order was sold
            sold_amount = sell_order['base']['amount'] - new_sell_order['base']['amount']
        elif not new_sell_order and sell_order:
            # All of the sell order was sold
            sold_amount = sell_order['base']['amount']

        bought_amount = 0
        if new_buy_order and new_buy_order['quote']['amount'] < buy_order['quote']['amount']:
            # Some of the buy order was bought
            bought_amount = buy_order['quote']['amount'] - new_buy_order['quote']['amount']
        elif not new_buy_order and buy_order:
            # All of the buy order was bought
            bought_amount = buy_order['quote']['amount']

        if sold_amount:
            # We sold something, place updated buy order
            buy_order_amount = self.get_order_amount(buy_order, 'quote')
            new_buy_amount = buy_order_amount - bought_amount + sold_amount
            if float(self.balance(self.market["base"])) < self.buy_price * new_buy_amount:
                self.log.critical(
                    'Insufficient buy balance, needed {} {}'.format(self.buy_price * new_buy_amount,
                                                                    self.market['base']['symbol'])
                )
                self.disabled = True
            else:
                if buy_order and not Order(buy_order['id'])['deleted']:
                    # Cancel the old order
                    self.cancel(buy_order)

                buy_transaction = self.market.buy(
                    self.buy_price,
                    Amount(amount=new_buy_amount, asset=self.market["quote"]),
                    account=self.account,
                    returnOrderId="head"
                )
                buy_order = self.get_order(buy_transaction['orderid'])
                self.log.info(
                    'Placed a buy order for {} {} @ {}'.format(new_buy_amount, self.market["quote"], self.buy_price)
                )
                if buy_order:
                    self['buy_order'] = buy_order
        else:
            # Update the buy order
            self['buy_order'] = new_buy_order or {}

        if bought_amount:
            # We bought something, place updated sell order
            sell_order_amount = self.get_order_amount(sell_order, 'quote')
            new_sell_amount = sell_order_amount + bought_amount - sold_amount
            if float(self.balance(self.market["quote"])) < new_sell_amount:
                self.log.critical(
                    "Insufficient sell balance, needed {} {}".format(new_sell_amount, self.market["quote"]['symbol'])
                )
                self.disabled = True
            else:
                if sell_order and not Order(sell_order['id'])['deleted']:
                    # Cancel the old order
                    self.cancel(sell_order)

                sell_transaction = self.market.sell(
                    self.sell_price,
                    Amount(amount=new_sell_amount, asset=self.market["quote"]),
                    account=self.account,
                    returnOrderId="head"
                )
                sell_order = self.get_order(sell_transaction['orderid'])
                self.log.info(
                    'Placed a sell order for {} {} @ {}'.format(new_sell_amount, self.market["quote"], self.buy_price)
                )
                if sell_order:
                    self['sell_order'] = sell_order
        else:
            # Update the sell order
            self['sell_order'] = new_sell_order or {}

    def orders_balance(self):
        balance = 0
        orders = [o for o in [self['buy_order'], self['sell_order']] if o]  # Strip empty orders
        for order in orders:
            if order['base']['symbol'] != self.market['base']['symbol']:
                # Invert the market for easier calculation
                if not isinstance(order, Price):
                    order = self.get_order(order['id'])
                if order:
                    order.invert()
            if order:
                balance += order['base']['amount']

        return balance

    def tick(self, d):
        """
        Test orders every 10th block
        """
        if not (self.counter["blocks"] or 0) % 10:
            self.test()
        self.counter["blocks"] += 1

    def test(self, *args, **kwargs):
        """
        Tests if the orders need updating
        """
        if 'sell_order' not in self or 'buy_order' not in self:
            self.init_strategy()
        else:
            current_sell_order = self.get_updated_order(self['sell_order'])
            current_buy_order = self.get_updated_order(self['buy_order'])

            # Update checks
            sell_order_updated = not current_sell_order or \
                current_sell_order['base']['amount'] != self['sell_order']['base']['amount']
            buy_order_updated = not current_buy_order or \
                current_buy_order['quote']['amount'] != self['buy_order']['quote']['amount']

            if (self['sell_order'] and sell_order_updated) or (self['buy_order'] and buy_order_updated):
                # Either buy or sell order was changed, update both orders
                self.update_orders(current_sell_order, current_buy_order)

            if self.view:
                self.update_gui_profit()
                self.update_gui_slider()

    # GUI updaters
    def update_gui_profit(self):
        # Fixme: profit calculation doesn't work this way, figure out a better way to do this.
        if self.initial_balance:
            profit = round((self.orders_balance() - self.initial_balance) / self.initial_balance, 3)
        else:
            profit = 0
        idle_add(self.view.set_worker_profit, self.worker_name, float(profit))
        self['profit'] = profit

    def update_gui_slider(self):
        buy_order = self['buy_order']
        if buy_order:
            buy_amount = buy_order['quote']['amount']
        else:
            buy_amount = 0
        sell_order = self['sell_order']
        if sell_order:
            sell_amount = sell_order['base']['amount']
        else:
            sell_amount = 0

        total = buy_amount + sell_amount
        if not total:  # Prevent division by zero
            percentage = 0
        else:
            percentage = (buy_amount / total) * 100
        idle_add(self.view.set_worker_slider, self.worker_name, percentage)
        self['slider'] = percentage
