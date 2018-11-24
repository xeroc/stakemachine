from dexbot.strategies.external_feeds.price_feed import PriceFeed
from dexbot.strategies.external_feeds.process_pair import get_consolidated_pair


"""
This is the unit test for testing price_feed module. 
Run this test first to cover everything in external feeds

Note from Marko, In DEXBot: unit of measure = BASE, asset of interest = QUOTE
"""


def test_exchanges():
    center_price = None
    symbol = 'BTC/USDT'
    exchanges = ['gecko', 'bitfinex', 'kraken', 'gdax', 'binance', 'waves']
    
    for exchange in exchanges:
        symbol = 'BTC/USD'
        pf = PriceFeed(exchange, symbol)
        pf.filter_symbols()
        center_price = pf.get_center_price(None)
        print("center price: ", center_price)        
        if center_price is None: # try USDT            
            center_price = pf.get_center_price('USDT')
            print("try again, s/USD/USDT, center price: ", center_price)

            
def test_consolidated_pair():
    center_price = None
    try:
        symbol2 = 'STEEM/BTS' # STEEM/USD * USD/BTS = STEEM/BTS
        pf = PriceFeed('gecko', symbol2)            
        pair1, pair2 = get_consolidated_pair('STEEM', 'BTS')
        print(pair1, pair2)
        pf.pair = pair1
        p1_price = pf.get_center_price(None)
        print("pair1 price", p1_price, sep=':')            
        pf.pair = pair2
        p2_price = pf.get_center_price(None)
        print("pair2 price", p2_price, sep='=')

        if p1_price and p2_price:
            center_price = p1_price * p2_price
            print(symbol2, "price is ", center_price)        
    except Exception as e:
        print(type(e).__name__, e.args, 'Error')
    

def test_alternative_usd():
    alternative_usd = ['USDT', 'USDC', 'TUSD', 'GUSD']
    # todo - refactor price_feed to try alt USD options, but only if they exist
    
    

if __name__ == '__main__':
    
    test_exchanges()
    test_consolidated_pair()

