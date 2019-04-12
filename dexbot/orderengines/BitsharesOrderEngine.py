from bitshares.instance import shared_bitshares_instance


class BitsharesOrderEngine:

    def __init__(self,
                 bitshares_instance=None):
        
        # BitShares instance
        self.bitshares = bitshares_instance or shared_bitshares_instance()

        # Dex instance used to get different fees for the market
        self.dex = Dex(self.bitshares)
        

        
    def get_market_buy_orders(self, depth=10):
        """ Fetches most recent data and returns list of buy orders.

            :param int | depth: Amount of buy orders returned, Default=10
            :return: List of market sell orders
        """
        orders = self.get_market_orders(depth=depth)
        buy_orders = self.filter_buy_orders(orders)
        return buy_orders

    
    def get_market_sell_orders(self, depth=10):
        """ Fetches most recent data and returns list of sell orders.

            :param int | depth: Amount of sell orders returned, Default=10
            :return: List of market sell orders
        """
        orders = self.get_market_orders(depth=depth)
        sell_orders = self.filter_sell_orders(orders)
        return sell_orders

    def get_highest_market_buy_order(self, orders=None):
        """ Returns the highest buy order that is not own, regardless of order size.

            :param list | orders: Optional list of orders, if none given fetch newest from market
            :return: Highest market buy order or None
        """
        if not orders:
            orders = self.get_market_buy_orders(1)

        try:
            order = orders[0]
        except IndexError:
            self.log.info('Market has no buy orders.')
            return None

        return order

    def get_highest_own_buy_order(self, orders=None):
        """ Returns highest own buy order.

            :param list | orders:
            :return: Highest own buy order by price at the market or None
        """
        if not orders:
            orders = self.get_own_buy_orders()

        try:
            return orders[0]
        except IndexError:
            return None

    def get_lowest_market_sell_order(self, orders=None):
        """ Returns the lowest sell order that is not own, regardless of order size.

            :param list | orders: Optional list of orders, if none given fetch newest from market
            :return: Lowest market sell order or None
        """
        if not orders:
            orders = self.get_market_sell_orders(1)

        try:
            order = orders[0]
        except IndexError:
            self.log.info('Market has no sell orders.')
            return None

        return order

    def get_lowest_own_sell_order(self, orders=None):
        """ Returns lowest own sell order.

            :param list | orders:
            :return: Lowest own sell order by price at the market
        """
        if not orders:
            orders = self.get_own_sell_orders()

        try:
            return orders[0]
        except IndexError:
            return None

            def cancel_all_orders(self):
        """ Cancel all orders of the worker's account
        """
        self.log.info('Canceling all orders')

        if self.all_own_orders:
            self.cancel_orders(self.all_own_orders)

        self.log.info("Orders canceled")

    def cancel_orders(self, orders, batch_only=False):
        """ Cancel specific order(s)

            :param list | orders: List of orders to cancel
            :param bool | batch_only: Try cancel orders only in batch mode without one-by-one fallback
            :return:
        """
        if not isinstance(orders, (list, set, tuple)):
            orders = [orders]

        orders = [order['id'] for order in orders if 'id' in order]

        success = self._cancel_orders(orders)
        if not success and batch_only:
            return False
        if not success and len(orders) > 1 and not batch_only:
            # One of the order cancels failed, cancel the orders one by one
            for order in orders:
                success = self._cancel_orders(order)
                if not success:
                    return False
        return success

