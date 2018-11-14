from dexbot.strategies.external_feeds.ccxt_feed import get_ccxt_price
from dexbot.strategies.external_feeds.waves_feed import get_waves_price
from dexbot.strategies.external_feeds.process_pair import split_pair
#from gecko_feed import get_gecko_price


class PriceFeed:

    def __init__(self, exchange, symbol):
        self.exchange = exchange
        self.symbol = symbol
        self.alt_exchanges = ['gecko', 'waves'] # assume all other exchanges are ccxt

        
    def get_center_price(self):
        pair = split_pair(symbol)
        price = None
        if self.exchange not in self.alt_exchanges:
            print("use ccxt exchange ", self.exchange, ' symbol ', self.symbol, sep=":")   
            price = get_ccxt_price(self.symbol, self.exchange)
        elif self.exchange == 'gecko':
            print("gecko - WIP todo")
        elif self.exchange == 'waves':
            print("use waves -", self.exchange, ' symbol ', self.symbol, sep=":")
            price = get_waves_price(pair[1], pair[0])

        return price


    
if __name__ == '__main__':
    exchanges = ['bitfinex', 'kraken', 'gecko', 'waves']
    symbol = 'BTC/USD'  # quote/base for external exchanges
    
    for exchange in exchanges:
        pf = PriceFeed(exchange, symbol)
        center_price = pf.get_center_price()
        print("center price: ", center_price)
        
