from dexbot.strategies.external_feeds.price_feed import PriceFeed

"""
Note from Marko Paasila, In DEXBot:
unit of measure = BASE
asset of interest = QUOTE
"""


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

