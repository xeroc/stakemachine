from dexbot.strategies.external_feeds.process_pair import split_pair, get_consolidated_pair, filter_prefix_symbol, \
    filter_bit_symbol

"""
This is the unit test for filters in process_pair module.
"""


# Unit Tests
def test_consolidated_pair():
    symbol = 'STEEM:BTS'  # pair = 'STEEM:BTS' or STEEM/BTS'
    pair = split_pair(symbol)
    pair1, pair2 = get_consolidated_pair(pair[1], pair[0])
    print(symbol, '=', pair1, pair2, sep=' ')


def test_split_symbol():
    try:
        group = ['BTC:USD', 'STEEM/USD']
        pair = [split_pair(symbol) for symbol in group]
        print('original:', group, 'result:', pair, sep=' ')
    except Exception:
        pass


def test_filters():
    test_symbols = ['USDT', 'bridge.USD', 'Rudex.USD', 'open.USD',
                    'GDEX.USD', 'Spark.USD', 'bridge.BTC', 'BTC', 'LTC',
                    'bitUSD', 'bitEUR', 'bitHKD']
    print("Test Symbols", test_symbols, sep=":")
    r = [filter_prefix_symbol(i) for i in test_symbols]
    print("Filter prefix symbol", r, sep=":")
    r2 = [filter_bit_symbol(i) for i in r]
    print("Apply to result, Filter bit symbol", r2, sep=":")


if __name__ == '__main__':
    print("testing consolidate pair")
    test_consolidated_pair()
    print("\ntesting split symbol")
    test_split_symbol()
    print("\ntesting filters")
    test_filters()
