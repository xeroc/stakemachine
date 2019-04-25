from dexbot.pricefeeds.bitshares_feed import BitsharesPriceFeed
from bitshares.bitshares import BitShares
from bitshares.market import Market
import logging, os
import pytest

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(funcName)s %(lineno)d  : %(message)s'
)

class Test_PriceFeed:
    def setup_class(self):
        self.node_url = "wss://api.fr.bitsharesdex.com/ws"
        self.TEST_CONFIG = {
            'node': self.node_url
        }
        self.bts = BitShares(node=self.TEST_CONFIG['node'])
        self.market = Market("USD:BTS")
        logging.info(self.market.ticker())

        self.pf = BitsharesPriceFeed(market=self.market, bitshares_instance=self.bts)
        logging.info("Setup Bitshares Price Feed Test: {}".format(self.bts))


    def teardown_class(self):
        pass

    def setup_method(self):
        pass

    def teardown_method(self):
        pass

    def test_configure(self):
        logging.info("Creating Bitshares Price Feed")

    def test_get_ticker(self):
        ticker = self.pf.market
        logging.info("Market ticker: {}".format(ticker))

    def test_get_limit_orders(self):
        mkt_orders = self.pf.get_limit_orders(depth=1)
        logging.info("Limit Orders: {} ".format(mkt_orders))

    def test_get_orderbook_orders(self):
        orderbook = self.pf.get_orderbook_orders(depth=1)
        logging.info("Orderbook orders: {} ".format(orderbook))

    def test_get_market_center_price(self):
        center_price = self.pf.get_market_center_price(base_amount=0, quote_amount=0, suppress_errors=False)
        logging.info("Center price: {}".format(center_price))

    def test_get_market_buy_price(self):
        mkt_buy_price = self.pf.get_market_buy_price(quote_amount=0, base_amount=0)
        logging.info("Get market buy price: {}".format(mkt_buy_price))

    def test_get_market_sell_price(self):
        mkt_sell_price = self.pf.get_market_sell_price(quote_amount=0, base_amount=0)
        logging.info("Get market sell price: {}".format(mkt_sell_price))

    def test_get_market_spread(self):
        mkt_spread = self.pf.get_market_spread(quote_amount=0, base_amount=0)
        logging.info("Market spread: {}".format(mkt_spread))

    def test_get_market_buy_orders(self):
        buy_orders = self.pf.get_market_buy_orders(depth=10)
        logging.info("List of buy orders: {}".format(buy_orders))
        return buy_orders

    def test_sort_orders_by_price(self):
        buy_orders = self.test_get_market_buy_orders()
        asc_buy_orders = self.pf.sort_orders_by_price(buy_orders, sort='ASC')
        logging.info("List of Buy orders in ASC price: {} ".format(asc_buy_orders))
        return asc_buy_orders

    def test_get_highest_market_buy_order(self):
        asc_buy_orders = self.test_sort_orders_by_price()
        highest = self.pf.get_highest_market_buy_order(asc_buy_orders)
        logging.info("Highest market buy order: {}".format(highest))

    def test_get_market_sell_orders(self):
        sell_orders = self.pf.get_market_sell_orders(depth=10)
        logging.info("Market Sell Orders: {}".format(sell_orders))
        return sell_orders

    def test_get_lowest_market_sell_order(self):
        sell_orders = self.test_get_market_sell_orders()
        lowest = self.pf.get_lowest_market_sell_order(sell_orders)
        logging.info("Lowest market sell order: {} ".format(lowest))



if __name__ == '__main__':
    cur_dir = os.path.dirname(__file__)
    test_file = os.path.join(cur_dir, 'bitshares_feed_test.py')
    pytest.main(['--capture=no', test_file])



