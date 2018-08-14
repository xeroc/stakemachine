import math
from datetime import datetime
from datetime import timedelta

from dexbot.basestrategy import BaseStrategy, ConfigElement
from dexbot.qt_queue.idle_queue import idle_add

from bitshares.price import FilledOrder

class Strategy(BaseStrategy):
    """ Relative Orders strategy
    """

    @classmethod
    def configure(cls, return_base_config=True):
        return BaseStrategy.configure(return_base_config) + [
            ConfigElement('amount', 'float', 1, 'Amount',
                          'Fixed order size, expressed in quote asset, unless "relative order size" selected',
                          (0, None, 8, '')),
            ConfigElement('relative_order_size', 'bool', False, 'Relative order size',
                          'Amount is expressed as a percentage of the account balance of quote/base asset', None),
            ConfigElement('spread', 'float', 5, 'Spread',
                          'The percentage difference between buy and sell', (0, 100, 2, '%')),
            ConfigElement('center_price', 'float', 0, 'Center price',
                          'Fixed center price expressed in base asset: base/quote', (0, None, 8, '')),
            ConfigElement('center_price_dynamic', 'bool', True, 'Update center price from closest market orders',
                          'Always calculate the middle from the closest market orders', None),
            ConfigElement('center_price_offset', 'bool', False, 'Center price offset based on asset balances',
                          'Automatically adjust orders up or down based on the imbalance of your assets', None),
            ConfigElement('manual_offset', 'float', 0, 'Manual center price offset',
                          "Manually adjust orders up or down. "
                          "Works independently of other offsets and doesn't override them", (-50, 100, 2, '%')),
            ConfigElement('reset_on_partial_fill', 'bool', True, 'Reset orders on partial fill',
                          'Reset orders when buy or sell order is partially filled', None),
            ConfigElement('partial_fill_threshold', 'float', 30, 'Fill threshold',
                          'Fill threshold to reset orders', (0, 100, 2, '%')),
            ConfigElement('reset_on_market_trade', 'bool', False, 'Reset orders on market trade',
                          'Reset orders when detected a market trade', None),
            ConfigElement('reset_on_price_change', 'bool', False, 'Reset orders on center price change',
                          'Reset orders when center price is changed more than threshold', None),
            ConfigElement('price_change_threshold', 'float', 2, 'Price change threshold',
                          'Define center price threshold to react on', (0, 100, 2, '%')),
            ConfigElement('custom_expiration', 'bool', False, 'Custom expiration',
                          'Override order expiration time to trigger a reset', None),
            ConfigElement('expiration_time', 'int', 157680000, 'Order expiration time',
                          'Define custom order expiration time to force orders reset more often, seconds',
                          (30, 157680000, ''))
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.log.info("Initializing Relative Orders")

        # Tick counter
        self.counter = 0

        # Define Callbacks
        self.ontick += self.tick
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

        self.is_relative_order_size = self.worker.get('relative_order_size', False)
        self.is_asset_offset = self.worker.get('center_price_offset', False)
        self.manual_offset = self.worker.get('manual_offset', 0) / 100
        self.order_size = float(self.worker.get('amount', 1))
        self.spread = self.worker.get('spread') / 100
        self.is_reset_on_partial_fill = self.worker.get('reset_on_partial_fill', True)
        self.partial_fill_threshold = self.worker.get('partial_fill_threshold', 30) / 100
        self.is_reset_on_market_trade = self.worker.get('reset_on_market_trade', False)
        self.is_reset_on_price_change = self.worker.get('reset_on_price_change', False)
        self.price_change_threshold = self.worker.get('price_change_threshold', 2) / 100
        self.is_custom_expiration = self.worker.get('custom_expiration', False)

        if self.is_custom_expiration:
            self.expiration = self.worker.get('expiration_time', self.expiration)

        self.last_check = datetime.now()
        self.min_check_interval = 8

        self.buy_price = None
        self.sell_price = None

        self.initial_balance = self['initial_balance'] or 0
        self.worker_name = kwargs.get('name')
        self.view = kwargs.get('view')

        # Check for conflicting settings
        if self.is_reset_on_price_change and not self.is_center_price_dynamic:
            self.log.error('reset_on_price_change requires Dynamic Center Price')
            self.disabled = True
        self.update_orders()

    def error(self, *args, **kwargs):
        self.cancel_all()
        self.disabled = True

    def tick(self, d):
        """ Ticks come in on every block. We need to periodically check orders because cancelled orders
            do not triggers a market_update event
        """
        if (self.is_reset_on_price_change and not
            self.counter % 8):
            self.log.debug('checking orders by tick threshold')
            self.check_orders('tick')
        self.counter += 1

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
            self.center_price = self.calculate_center_price(
                None,
                self.is_asset_offset,
                self.spread,
                self['order_ids'],
                self.manual_offset
            )
        else:
            self.center_price = self.calculate_center_price(
                self.center_price,
                self.is_asset_offset,
                self.spread,
                self['order_ids'],
                self.manual_offset
            )

        self.buy_price = self.center_price / math.sqrt(1 + self.spread)
        self.sell_price = self.center_price * math.sqrt(1 + self.spread)

    def update_orders(self):
        #self.log.debug('Change detected, updating orders')

        # Recalculate buy and sell order prices
        self.calculate_order_prices()

        # Cancel the orders before redoing them
        self.cancel_all()
        self.clear_orders()

        order_ids = []

        amount_base = self.amount_base
        amount_quote = self.amount_quote

        # Buy Side
        buy_order = self.market_buy(amount_base, self.buy_price, True)
        if buy_order:
            self.save_order(buy_order)
            order_ids.append(buy_order['id'])

        # Sell Side
        sell_order = self.market_sell(amount_quote, self.sell_price, True)
        if sell_order:
            self.save_order(sell_order)
            order_ids.append(sell_order['id'])

        self['order_ids'] = order_ids

        self.log.info("Done placing orders")

        # Some orders weren't successfully created, redo them
        if len(order_ids) < 2 and not self.disabled:
            self.update_orders()

    def check_orders(self, event, *args, **kwargs):
        """ Tests if the orders need updating
        """
        delta = datetime.now() - self.last_check

        # Only allow to check orders whether minimal time passed
        if delta < timedelta(seconds=self.min_check_interval):
            self.log.debug('Ignoring market_update event as min_check_interval is not passed')
            return

        orders = self.fetch_orders()

        # Detect complete fill, order expiration, manual cancel, or just init
        need_update = False
        if not orders:
            need_update = True
        else:
            # Loop trough the orders and look for changes
            for order_id, order in orders.items():
                current_order = self.get_order(order_id)

                if not current_order:
                    need_update = True
                    self.log.debug('Could not found order on the market, it was filled, expired or cancelled')
                    # FIXME: writing a log entry is disabled because we cannot distinguish an expired order
                    #        from filled
                    #self.write_order_log(self.worker_name, order)
                elif self.is_reset_on_partial_fill:
                    # Detect partially filled orders;
                    # on fresh order 'for_sale' is always equal to ['base']['amount']
                    if current_order['for_sale']['amount'] != current_order['base']['amount']:
                        diff_abs = current_order['base']['amount'] - current_order['for_sale']['amount']
                        diff_rel = diff_abs / current_order['base']['amount']
                        if diff_rel >= self.partial_fill_threshold:
                            need_update = True
                            self.log.info('Partially filled order detected, filled {:.2%}'.format(diff_rel))
                            # FIXME: need to write trade operation; possible race condition may occur: while
                            #        we're updating order it may be filled futher so trade log entry will not
                            #        be correct

        if (self.is_reset_on_market_trade and
            isinstance(event, FilledOrder)):
            self.log.debug('Market trade detected, updating orders')
            need_update = True

        if self.is_reset_on_price_change:
            center_price = self.calculate_center_price(
                None,
                self.is_asset_offset,
                self.spread,
                self['order_ids'],
                self.manual_offset
            )
            diff = (self.center_price - center_price) / self.center_price
            diff = abs(diff)
            if diff >= self.price_change_threshold:
                self.log.debug('Center price changed, updating orders. Diff: {:.2%}'.format(diff))
                need_update = True

        if need_update:
            self.update_orders()
        else:
            pass
            #self.log.debug("Orders correct on market")

        if self.view:
            self.update_gui_profit()
            self.update_gui_slider()

        self.last_check = datetime.now()

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

        order_ids = None
        orders = self.fetch_orders()

        if orders:
            order_ids = orders.keys()

        total_balance = self.total_balance(order_ids)
        total = (total_balance['quote'] * latest_price) + total_balance['base']

        if not total:  # Prevent division by zero
            percentage = 50
        else:
            percentage = (total_balance['base'] / total) * 100
        idle_add(self.view.set_worker_slider, self.worker_name, percentage)
        self['slider'] = percentage
