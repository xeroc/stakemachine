import re

from dexbot.strategies.external_feeds.ccxt_feed import get_ccxt_price
from dexbot.strategies.external_feeds.gecko_feed import get_gecko_price
from dexbot.strategies.external_feeds.waves_feed import get_waves_price
from dexbot.strategies.external_feeds.process_pair import split_pair, join_pair, filter_prefix_symbol, \
    filter_bit_symbol, get_consolidated_pair, debug


class PriceFeed:
    """
    price feed class, which handles all data requests for external center price
    """

    def __init__(self, exchange, symbol):
        self._alt_exchanges = ['gecko', 'waves']  # assume all other exchanges are ccxt
        self._exchange = exchange
        self._symbol = symbol
        self._pair = split_pair(symbol)

    @property
    def symbol(self):
        return self._symbol

    @symbol.setter
    def symbol(self, symbol):
        self._symbol = symbol
        self._pair = split_pair(self._symbol)

    @property
    def pair(self):
        return self._pair

    @pair.setter
    def pair(self, pair):
        self._pair = pair
        self._symbol = join_pair(pair)

    @property
    def exchange(self):
        return self._exchange

    @exchange.setter
    def exchange(self, exchange):
        self._exchange = exchange

    def filter_symbols(self):
        raw_pair = self._pair
        self._pair = [filter_bit_symbol(j) for j in [filter_prefix_symbol(i) for i in raw_pair]]
        debug(self._pair)

    def get_consolidated_price(self):
        """
        assumes XXX/YYY must be broken into XXX/USD * USD/YYY
        """
        center_price = None
        original_pair = self.pair
        try:
            pair1, pair2 = get_consolidated_pair(self.pair[0], self.pair[1])
            self.pair = pair1
            pair1_price = self.get_center_price(None)
            self.pair = pair2
            pair2_price = self.get_center_price(None)
            if pair1_price and pair2_price:
                center_price = pair1_price * pair2_price
                print(original_pair, "price is ", center_price)
                self.pair = original_pair  # put original pair back
        except Exception as e:
            print(type(e).__name__, e.args, 'Error')
        return center_price

    def set_alt_usd_pair(self, type):
        """
        get center price by search and replace for USD with USDT only
        todo: extend in PriceFeed or base.py for other alts, e.g. USDC, TUSD,etc
        """
        alt_usd_pair = self._pair
        i = 0
        while i < 2:
            if re.match(r'^USD$', self._pair[i], re.I):
                alt_usd_pair[i] = re.sub(r'USD', type, self._pair[i])
            i = i + 1
        self._pair = alt_usd_pair
        self._symbol = join_pair(self._pair)

    def _get_center_price(self):
        symbol = self._symbol
        price = None
        if self._exchange not in self._alt_exchanges:
            price = get_ccxt_price(symbol, self._exchange)
            debug('Use ccxt exchange {} symbol {} price: {}'.format(self.exchange, symbol, price))
        elif self._exchange == 'gecko':
            price = get_gecko_price(symbol_=symbol)
            debug('Use ccxt exchange {} symbol {} price: {}'.format(self.exchange, symbol, price))
        elif self._exchange == 'waves':
            price = get_waves_price(symbol_=symbol)
            debug('Use waves exchange {} symbol {} price: {}'.format(self.exchange, symbol, price))
        return price

    def get_center_price(self, type):
        if type is not None:
            self.set_alt_usd_pair(type)
        return self._get_center_price()
