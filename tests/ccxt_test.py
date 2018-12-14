from dexbot.strategies.external_feeds.price_feed import PriceFeed


""" This is the unit test for testing price_feed module.
    Run this test first to cover everything in external feeds

    In DEXBot:
        unit of measure = BASE
        asset of interest = QUOTE
"""


def test_exchanges():
    symbol = 'BTC/USD'
    exchanges = ['gecko', 'bitfinex', 'kraken', 'gdax', 'binance', 'waves']

    for exchange in exchanges:
        price_feed = PriceFeed(exchange, symbol)
        price_feed.filter_symbols()
        center_price = price_feed.get_center_price(None)
        print("Center price: {}".format(center_price))

        if center_price is None:
            # Try USDT
            center_price = price_feed.get_center_price('USDT')
            print("Try again, USD/USDT center price: {}".format(center_price))


def test_consolidated_pair():
    symbol = 'STEEM/BTS'  # STEEM/USD * USD/BTS = STEEM/BTS
    price_feed = PriceFeed('gecko', symbol)
    center_price = price_feed.get_consolidated_price()
    print(center_price)


def test_alternative_usd():
    # Todo - Refactor price_feed to handle alt USD options.
    alternative_usd = ['USDT', 'USDC', 'TUSD', 'GUSD']
    exchanges = ['bittrex', 'poloniex', 'gemini', 'bitfinex', 'kraken', 'binance', 'okex']
    symbol = 'BTC/USD'  # Replace with alt usd

    for exchange in exchanges:
        for alternative in alternative_usd:
            price_feed = PriceFeed(exchange, symbol)
            center_price = price_feed.get_center_price(None)

            if center_price:
                print('{} using alt: {} {}'.format(symbol, alternative, center_price))
            else:
                center_price = price_feed.get_center_price(alternative)
                if center_price:
                    print('{} using alt: {} {}'.format(symbol, alternative, center_price))


if __name__ == '__main__':
    test_exchanges()
    test_consolidated_pair()
    test_alternative_usd()
