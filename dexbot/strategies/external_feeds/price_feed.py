from dexbot.strategies.external_feeds.ccxt_feed import get_ccxt_price
from dexbot.strategies.external_feeds.waves_feed import get_waves_price
from dexbot.strategies.external_feeds.gecko_feed import get_gecko_price
from dexbot.strategies.external_feeds.process_pair import split_pair, join_pair, filter_prefix_symbol, filter_bit_symbol, debug
import re

"""
Note from Marko Paasila, In DEXBot:
unit of measure = BASE
asset of interest = QUOTE
"""

class PriceFeed:
    """
    price feed class to handle price feed
    """
    def __init__(self, exchange, symbol):
        self._alt_exchanges = ['gecko', 'waves'] # assume all other exchanges are ccxt
        self._exchange= exchange
        self._symbol=symbol
        self._pair= split_pair(symbol)
 
               
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

        
    def set_alt_usd_pair(self):
        """
        get center price by search and replace for USD with USDT only
        extend this method in the future for other usdt like options, e.g. USDC, TUSD,etc
        """
        alt_usd_pair = self._pair
        i = 0
        while i < 2:
            if re.match(r'^USD$', self._pair[i], re.I):
                alt_usd_pair[i] = re.sub(r'USD','USDT', self._pair[i])
            i = i+1
        self._pair = alt_usd_pair
        self._symbol = join_pair(self._pair)
        

    def get_center_price(self, type):
        if type == "USDT":
            self.set_alt_usd_pair()
        return  self._get_center_price()

        
    def _get_center_price(self):
        symbol = self._symbol
        price = None
        if self._exchange not in self._alt_exchanges:
            print("use ccxt exchange ", self._exchange, ' symbol ', symbol, sep=":")
            price = get_ccxt_price(symbol, self._exchange)
        elif self._exchange == 'gecko':
            print("gecko exchange - ", self._exchange, ' symbol ', symbol, sep=":")
            price = get_gecko_price(symbol_=symbol)
        elif self._exchange == 'waves':
            print("use waves -", self._exchange, ' symbol ', symbol, sep=":")
            price = get_waves_price(symbol_=symbol)
        return price



if __name__ == '__main__':
    center_price = None
    exchanges = ['gecko', 'bitfinex', 'kraken', 'gdax', 'binance', 'waves']
    symbol = 'BTC/USDT'
    
    for exchange in exchanges:
        symbol = 'BTC/USD'
        pf = PriceFeed(exchange, symbol)
        pf.filter_symbols()
        center_price = pf.get_center_price(None)
        print("center price: ", center_price)        
        if center_price is None: # try USDT
            center_price = pf.get_center_price("USDT")
            print("s/usd/usdt, center price: ", center_price)

