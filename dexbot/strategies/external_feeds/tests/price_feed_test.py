from dexbot.strategies.external_feeds.price_feed import PriceFeed
from dexbot.strategies.external_feeds.process_pair import get_consolidated_pair

"""
This is the unit test for testing price_feed module. 
Run this test first to cover everything in external feeds

In DEXBot: unit of measure = BASE, asset of interest = QUOTE
"""


def test_exchanges():
    center_price = None
    symbol = 'BTC/USD'
    exchanges = ['gecko', 'bitfinex', 'kraken', 'gdax', 'binance', 'waves']

    for exchange in exchanges:
        pf = PriceFeed(exchange, symbol)
        pf.filter_symbols()
        center_price = pf.get_center_price(None)
        print("center price: ", center_price)
        if center_price is None:  # try USDT
            center_price = pf.get_center_price('USDT')
            print("try again, s/USD/USDT, center price: ", center_price)


def test_consolidated_pair():
    symbol2 = 'STEEM/BTS'  # STEEM/USD * USD/BTS = STEEM/BTS
    pf = PriceFeed('gecko', symbol2)
    center_price = pf.get_consolidated_price()
    print(center_price)


def test_alternative_usd():
    # todo - refactor price_feed to handle alt USD options.
    alternative_usd = ['USDT', 'USDC', 'TUSD', 'GUSD']
    exchanges = ['bittrex', 'poloniex', 'gemini', 'bitfinex', 'kraken', 'binance', 'okex']
    symbol = 'BTC/USD'  # replace with alt usd

    for exchange in exchanges:
        for alt in alternative_usd:
            pf = PriceFeed(exchange, symbol)
            center_price = pf.get_center_price(None)
            if center_price:
                print(symbol, ' using alt:', alt, center_price, "\n", sep=' ')
            else:
                center_price = pf.get_center_price(alt)
                if center_price:
                    print(symbol, ' using alt:', alt, center_price, "\n", sep=' ')


if __name__ == '__main__':
    test_exchanges()
    test_consolidated_pair()
    test_alternative_usd()
