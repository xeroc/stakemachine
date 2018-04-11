from dexbot.basestrategy import BaseStrategy
from dexbot.queue.idle_queue import idle_add

from bitshares.amount import Amount


class Strategy(BaseStrategy):
    """ Relative Orders strategy
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Define Callbacks
        self.onMarketUpdate += self.check_orders
        self.onAccount += self.check_orders

        self.error_ontick = self.error
        self.error_onMarketUpdate = self.error
        self.error_onAccount = self.error

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

        self.check_orders()

    def calculate_order_prices(self):
        if self.is_center_price_dynamic:
            self.center_price = self.calculate_center_price

        self.buy_price = self.center_price * (1 - (self.target["spread"] / 2) / 100)
        self.sell_price = self.center_price * (1 + (self.target["spread"] / 2) / 100)

    def error(self, *args, **kwargs):
        self.cancel_all()
        self.disabled = True
        self.log.info(self.execute())

    def update_orders(self):
        self.log.info('Change detected, updating orders')
        amount = self.target['amount']

        # Recalculate buy and sell order prices
        self.calculate_order_prices()

        # Cancel the orders before redoing them
        self.cancel_all()

        order_ids = []

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
            self.log.info('Placed a buy order for {} {} @ {}'.format(amount,
                                                                     self.market["quote"]['symbol'],
                                                                     self.buy_price))
            if buy_order:
                self['buy_order'] = buy_order
                order_ids.append(buy_transaction['orderid'])

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
            self.log.info('Placed a sell order for {} {} @ {}'.format(amount,
                                                                      self.market["quote"]['symbol'],
                                                                      self.sell_price))
            if sell_order:
                self['sell_order'] = sell_order
                order_ids.append(sell_transaction['orderid'])

        self['order_ids'] = order_ids

    def check_orders(self, *args, **kwargs):
        """ Tests if the orders need updating
        """
        stored_sell_order = self['sell_order']
        stored_buy_order = self['buy_order']
        current_sell_order = self.get_updated_order(stored_sell_order)
        current_buy_order = self.get_updated_order(stored_buy_order)

        # Update checks
        sell_order_updated = not current_sell_order or \
            current_sell_order['quote']['amount'] != stored_sell_order['quote']['amount']
        buy_order_updated = not current_buy_order or \
            current_buy_order['base']['amount'] != stored_buy_order['base']['amount']

        if sell_order_updated or buy_order_updated:
            # Either buy or sell order was changed, update both orders
            self.update_orders()

        if self.view:
            self.update_gui_profit()
            self.update_gui_slider()

    # GUI updaters
    def update_gui_profit(self):
        # Fixme: profit calculation doesn't work this way, figure out a better way to do this.
        if self.initial_balance:
            profit = round((self.orders_balance(None) - self.initial_balance) / self.initial_balance, 3)
        else:
            profit = 0
        idle_add(self.view.set_worker_profit, self.worker_name, float(profit))
        self['profit'] = profit

    def update_gui_slider(self):
        ticker = self.market.ticker()
        latest_price = ticker.get('latest').get('price')
        total_balance = self.total_balance(self['order_ids'])
        total = (total_balance['quote'] * latest_price) + total_balance['base']

        if not total:  # Prevent division by zero
            percentage = 50
        else:
            percentage = (total_balance['base'] / total) * 100
        idle_add(self.view.set_worker_slider, self.worker_name, percentage)
        self['slider'] = percentage
