from dexbot.strategies.external_feeds.ccxt_feed import get_ccxt_price
from dexbot.strategies.external_feeds.waves_feed import get_waves_price
from dexbot.strategies.external_feeds.gecko_feed import get_gecko_price

from dexbot.strategies.external_feeds.process_pair import split_pair, filter_prefix_symbol, filter_bit_symbol, debug

"""
Note from Marko Paasila: 

We have been calling the unit-of-measure BASE and the asset-of-interest QUOTE. 
Since there seem to be confusing definitions around, we just had to settle one way, and be consistent. 
We chose the way @xeroc had in python-bitshares, where the market is BTSUSD or BTS:USD or BTS/USD, 
and price is USD/BTS. This is opposite to how bitshares-ui shows it (or I'm not sure of that, 
but at least unit-of-measure is QUOTE and not BASE there). 

So in DEXBot:

unit of measure = BASE
asset of interest = QUOTE

"""

class PriceFeed:

    def __init__(self, exchange, symbol):
        self.exchange = exchange
        self.symbol = symbol
        self.alt_exchanges = ['gecko', 'waves'] # assume all other exchanges are ccxt
        self.pair = split_pair(self.symbol)

        
    def filter_symbols(self):
        raw_pair = self.pair
        self.pair = [filter_bit_symbol(j) for j in [filter_prefix_symbol(i) for i in raw_pair]]
        debug(self.pair)        

#    def get_usd_alternative(self):
#    def get_consolidated_alternative(self):


    def get_center_price(self):
        price = None
        if self.exchange not in self.alt_exchanges:
            print("use ccxt exchange ", self.exchange, ' symbol ', self.symbol, sep=":")   
            price = get_ccxt_price(self.symbol, self.exchange)
        elif self.exchange == 'gecko':
            print("gecko exchange - ", self.exchange, ' symbol ', self.symbol, sep=":")
            price = get_gecko_price(symbol_=self.symbol)
        elif self.exchange == 'waves':
            print("use waves -", self.exchange, ' symbol ', self.symbol, sep=":")
            price = get_waves_price(symbol_=self.symbol)
            
        return price


if __name__ == '__main__':

    exchanges = ['gecko', 'bitfinex', 'kraken', 'waves', 'gdax', 'binance']
    symbol = 'BTC/USD'  # quote/base for external exchanges
    
    for exchange in exchanges:
        pf = PriceFeed(exchange, symbol)
        pf.filter_symbols()
        print(pf.pair)
        center_price = pf.get_center_price()
        print("center price: ", center_price)
        
