from collections import Counter

from bitshares.amount import Amount
from bitshares.price import Price

from dexbot.basestrategy import BaseStrategy
from dexbot.queue.idle_queue import idle_add


class Strategy(BaseStrategy):
    """
    Simple strategy
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

        # Tests for actions
        self.price = self.bot.get("target", {}).get("center_price", 0)

        self.bot_name = kwargs.get('name')
        self.view = kwargs.get('view')

    def error(self, *args, **kwargs):
        self.disabled = True
        self.cancel_all()
        self.clear()
        self.log.info(self.execute())

    def init_strategy(self):
        # Target
        target = self.bot.get("target", {})

        # prices
        buy_price = self.price * (1 - (target["spread"] / 2) / 100)
        sell_price = self.price * (1 + (target["spread"] / 2) / 100)

        amount = target['amount'] / 2

        # Buy Side
        if float(self.balance(self.market["base"])) < buy_price * amount:
            self.log.critical(
                'Insufficient buy balance, needed {} {}'.format(buy_price * amount, self.market['base']['symbol'])
            )
            self.disabled = True
        else:
            buy_transaction = self.market.buy(
                buy_price,
                Amount(amount=amount, asset=self.market["quote"]),
                account=self.account,
                returnOrderId="head"
            )
            buy_order = self.get_order(buy_transaction['orderid'])
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
                sell_price,
                Amount(amount=amount, asset=self.market["quote"]),
                account=self.account,
                returnOrderId="head"
            )
            sell_order = self.get_order(sell_transaction['orderid'])
            if sell_order:
                self['sell_order'] = sell_order

        self['initial_balance'] = self.orders_balance()

    def update_orders(self, new_sell_order, new_buy_order):
        """
        Update the orders
        """
        print('Updating orders!')
        target = self.bot.get("target", {})

        # Stored orders
        sell_order = self['sell_order']
        buy_order = self['buy_order']

        # prices
        buy_price = self.price * (1 - (target["spread"] / 2) / 100)
        sell_price = self.price * (1 + (target["spread"] / 2) / 100)

        sold_amount = 0
        if new_sell_order and new_sell_order['base']['amount'] < sell_order['base']['amount']:
            # Some of the sell order was sold
            sold_amount = sell_order['quote']['amount'] - new_sell_order['quote']['amount']
        elif not new_sell_order and sell_order:
            # All of the sell order was sold
            sold_amount = sell_order['quote']['amount']

        bought_amount = 0
        if new_buy_order and new_buy_order['quote']['amount'] < buy_order['quote']['amount']:
            # Some of the buy order was bought
            bought_amount = buy_order['quote']['amount'] - new_buy_order['quote']['amount']
        elif not new_buy_order and buy_order:
            # All of the buy order was bought
            bought_amount = buy_order['quote']['amount']

        if sold_amount:
            # We sold something, place updated buy order
            try:
                buy_order_amount = buy_order['quote']['amount']
            except KeyError:
                buy_order_amount = 0
            new_buy_amount = buy_order_amount - bought_amount + sold_amount
            if float(self.balance(self.market["base"])) < new_buy_amount:
                self.log.critical(
                    'Insufficient buy balance, needed {} {}'.format(buy_price * new_buy_amount,
                                                                    self.market['base']['symbol'])
                )
                self.disabled = True
            else:
                if buy_order:
                    # Cancel the old order
                    self.cancel(buy_order)

                buy_transaction = self.market.buy(
                    buy_price,
                    Amount(amount=new_buy_amount, asset=self.market["quote"]),
                    account=self.account,
                    returnOrderId="head"
                )
                buy_order = self.get_order(buy_transaction['orderid'])
                if buy_order:
                    self['buy_order'] = buy_order
        else:
            # Update the buy order
            self['buy_order'] = new_buy_order or {}

        if bought_amount:
            # We bought something, place updated sell order
            try:
                sell_order_amount = sell_order['base']['amount']
            except KeyError:
                sell_order_amount = 0
            new_sell_amount = sell_order_amount + bought_amount - sold_amount
            if float(self.balance(self.market["quote"])) < new_sell_amount:
                self.log.critical(
                    "Insufficient sell balance, needed {} {}".format(new_sell_amount, self.market["quote"]['symbol'])
                )
                self.disabled = True
            else:
                if sell_order:
                    # Cancel the old order
                    self.cancel(sell_order)

                sell_transaction = self.market.sell(
                    sell_price,
                    Amount(amount=new_sell_amount, asset=self.market["quote"]),
                    account=self.account,
                    returnOrderId="head"
                )
                sell_order = self.get_order(sell_transaction['orderid'])
                if sell_order:
                    self['sell_order'] = sell_order
        else:
            # Update the sell order
            self['sell_order'] = new_sell_order or {}

    def orders_balance(self):
        balance = 0
        for order in [self['buy_order'], self['sell_order']]:
            if order:
                if order['base']['symbol'] != self.market['base']['symbol']:
                    # Invert the market for easier calculation
                    if not isinstance(order, Price):
                        order = self.get_order(order['id'])
                    order.invert()
                balance += self.get_converted_asset_amount(order['quote'])

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

    # GUI updaters
    def update_gui_profit(self):
        profit = round((self.orders_balance() - self['initial_balance']) / self['initial_balance'], 3)
        idle_add(self.view.set_bot_profit, self.bot_name, profit)
        self['profit'] = profit

    def update_gui_slider(self):
        # WIP
        percentage = ''
        idle_add(self.view.update_slider, percentage)
