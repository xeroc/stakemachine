import math

from dexbot.basestrategy import BaseStrategy, ConfigElement
from dexbot.queue.idle_queue import idle_add


class Strategy(BaseStrategy):
    """ Relative Orders strategy
    """

    @classmethod
    def configure(cls):
        return BaseStrategy.configure() + [
            ConfigElement('center_price_dynamic',
                          'bool', False, 'Dynamic centre price', None),
            ConfigElement('center_price', 'float', 0.0,
                          'Initial center price', (0, 0, None)),
            ConfigElement('amount_relative', 'bool', False,
                          'Amount is expressed as a percentage of the account balance of quote/base asset', None),
            ConfigElement('amount', 'float', 1.0,
                          'The amount of buy/sell orders', (0.0, None)),
            ConfigElement('spread', 'float', 5.0,
                          'The percentage difference between buy and sell (Spread)', (0.0, 100.0))
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.log.info("Initializing Relative Orders")

        # Define Callbacks
        self.onMarketUpdate += self.check_orders
        self.onAccount += self.check_orders

        self.error_ontick = self.error
        self.error_onMarketUpdate = self.error
        self.error_onAccount = self.error

        self.is_center_price_dynamic = self.worker["center_price_dynamic"]
        if self.is_center_price_dynamic:
            self.center_price = None
        else:
            self.center_price = self.worker["center_price"]

        self.is_relative_order_size = self.worker['amount_relative']
        self.is_center_price_offset = self.worker.get('center_price_offset', False)
        self.order_size = float(self.worker['amount'])
        self.spread = self.worker.get('spread') / 100

        self.buy_price = None
        self.sell_price = None

        self.initial_balance = self['initial_balance'] or 0
        self.worker_name = kwargs.get('name')
        self.view = kwargs.get('view')
        self.check_orders()

    def error(self, *args, **kwargs):
        self.cancel_all()
        self.disabled = True

    @property
    def amount_quote(self):
        """ Get quote amount, calculate if order size is relative
        """
        if self.is_relative_order_size:
            quote_balance = float(self.balance(self.market["quote"]))
            return quote_balance * (self.order_size / 100)
        else:
            return self.order_size

    @property
    def amount_base(self):
        """ Get base amount, calculate if order size is relative
        """
        if self.is_relative_order_size:
            base_balance = float(self.balance(self.market["base"]))
            # amount = % of balance / buy_price = amount combined with calculated price to give % of balance
            return base_balance * (self.order_size / 100) / self.buy_price
        else:
            return self.order_size

    def calculate_order_prices(self):
        if self.is_center_price_dynamic:
            if self.is_center_price_offset:
                self.center_price = self.calculate_offset_center_price(
                    self.spread, order_ids=self['order_ids'])
            else:
                self.center_price = self.calculate_center_price()
        else:
            if self.is_center_price_offset:
                self.center_price = self.calculate_offset_center_price(
                    self.spread, self.center_price, self['order_ids'])

        self.buy_price = self.center_price / math.sqrt(1 + self.spread)
        self.sell_price = self.center_price * math.sqrt(1 + self.spread)

    def update_orders(self):
        self.log.info('Change detected, updating orders')

        # Recalculate buy and sell order prices
        self.calculate_order_prices()

        # Cancel the orders before redoing them
        self.cancel_all()

        # Mark the orders empty
        self['buy_order'] = {}
        self['sell_order'] = {}

        order_ids = []

        amount_base = self.amount_base
        amount_quote = self.amount_quote

        # Buy Side
        buy_order = self.market_buy(amount_base, self.buy_price, True)
        if buy_order:
            self['buy_order'] = buy_order
            order_ids.append(buy_order['id'])

        # Sell Side
        sell_order = self.market_sell(amount_quote, self.sell_price, True)
        if sell_order:
            self['sell_order'] = sell_order
            order_ids.append(sell_order['id'])

        self['order_ids'] = order_ids

        self.log.info("Done placing orders")

        # Some orders weren't successfully created, redo them
        if len(order_ids) < 2 and not self.disabled:
            self.update_orders()

    def check_orders(self, *args, **kwargs):
        """ Tests if the orders need updating
        """
        stored_sell_order = self['sell_order']
        stored_buy_order = self['buy_order']
        current_sell_order = self.get_order(stored_sell_order)
        current_buy_order = self.get_order(stored_buy_order)

        if not current_sell_order or not current_buy_order:
            # Either buy or sell order is missing, update both orders
            self.update_orders()
        else:
            self.log.info("Orders correct on market")

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
        latest_price = ticker.get('latest', {}).get('price', None)
        if not latest_price:
            return

        total_balance = self.total_balance(self['order_ids'])
        total = (total_balance['quote'] * latest_price) + total_balance['base']

        if not total:  # Prevent division by zero
            percentage = 50
        else:
            percentage = (total_balance['base'] / total) * 100
        idle_add(self.view.set_worker_slider, self.worker_name, percentage)
        self['slider'] = percentage
