import re

isDebug = True


def debug(*args):
    if isDebug:
        print(' '.join([str(arg) for arg in args]))


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


def join_pair(pair):
    symbol = pair[0]+'/'+pair[1]
    return symbol


def get_consolidated_pair(base, quote):
    # Split into two USD pairs, STEEM/BTS=(BTS/USD * USD/STEEM)
    # todo
    pair1 = [base, 'USD']  # BTS/USD  pair=[quote, base]
    pair2 = ['USD', quote]
    return pair1, pair2


