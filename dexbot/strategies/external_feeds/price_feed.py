from dexbot.strategies.external_feeds.ccxt_feed import get_ccxt_price
from dexbot.strategies.external_feeds.waves_feed import get_waves_price
from dexbot.strategies.external_feeds.gecko_feed import get_gecko_price

from dexbot.strategies.external_feeds.process_pair import split_pair, filter_prefix_symbol, filter_bit_symbol, debug


class PriceFeed:

    def __init__(self, exchange, symbol):
        self.exchange = exchange
        self.symbol = symbol
        self.alt_exchanges = ['gecko', 'waves'] # assume all other exchanges are ccxt
        self.pair = split_pair(self.symbol)

        
    def prefilter(self):
        raw_pair = self.pair
        self.pair = [filter_bit_symbol(j) for j in [filter_prefix_symbol(i) for i in raw_pair]]
        
        
    def get_center_price(self):
        price = None
        if self.exchange not in self.alt_exchanges:
            print("use ccxt exchange ", self.exchange, ' symbol ', self.symbol, sep=":")   
            price = get_ccxt_price(self.symbol, self.exchange)
        elif self.exchange == 'gecko':
            print("gecko exchange - ", self.exchange, ' symbol ', self.symbol, sep=":")
            price = get_gecko_price(self.symbol)
        elif self.exchange == 'waves':
            print("use waves -", self.exchange, ' symbol ', self.symbol, sep=":")
            price = get_waves_price(symbol_=self.symbol)
        return price


if __name__ == '__main__':
    exchanges = ['gecko', 'bitfinex', 'kraken', 'waves']
    symbol = 'BTC/USD'  # quote/base for external exchanges
    
    for exchange in exchanges:
        pf = PriceFeed(exchange, symbol)
        pf.prefilter()
        print(pf.pair)
        center_price = pf.get_center_price()
        print("center price: ", center_price)
        
