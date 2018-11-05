import re


def print_args(*args):
    print(' '.join([str(arg) for arg in args]))


def filter_prefix_symbol(symbol):
    # Example open.USD or bridge.USD, remove leading bit up to .
    base = ''
    if re.match(r'^[a-zA-Z](.*)\.(.*)', symbol):
        base = re.sub('(.*)\.', '', symbol)
    else:
        base = symbol
    return base


def filter_bit_symbol(symbol):
    # if matches bitUSD or bitusd any bit prefix, strip
    base = ''
    if re.match(r'bit[a-zA-Z]{3}', symbol):
        base = re.sub("bit", "", symbol)
    else:
        base = symbol
    return base


def split_pair(symbol):
    pair = re.split(':|/', symbol)
    return pair


def get_consolidated_pair(base, quote):
    # Split into two USD pairs, STEEM/BTS=(BTS/USD * USD/STEEM)
    pair1 = [base, 'USD']  # BTS/USD  pair=[quote, base]
    pair2 = ['USD', quote]
    return pair1, pair2


# Unit Tests
# Todo: Move tests to own files
def test_consolidated_pair():
    symbol = 'STEEM:BTS'  # pair = 'STEEM:BTS' or STEEM/BTS'
    pair = split_pair(symbol)
    pair1, pair2 = get_consolidated_pair(pair[1], pair[0])
    print(symbol, '=', pair1, pair2, sep=' ')


def test_split_symbol():
    try:
        group = ['BTC:USD', 'STEEM/USD']
        pair = [split_pair(symbol) for symbol in group]
        print('original:', group, 'result:',  pair, sep=' ')
    except Exception as e:
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
