from dexbot.strategies.external_feeds.process_pair import filter_bit_symbol, filter_prefix_symbol, split_pair
from dexbot.strategies.external_feeds.waves_feed import get_waves_price

""" This is the unit test for getting external feed data from waves DEX.
"""

if __name__ == '__main__':

    symbol = 'BTC/USD'  # quote/base for external exchanges
    print(symbol, "=")
    raw_pair = split_pair(symbol)
    pair = [filter_bit_symbol(j) for j in [filter_prefix_symbol(i) for i in raw_pair]]

    # Test symbol and pair options for getting price
    pair_price = get_waves_price(pair_=pair)
    if pair_price:
        print("pair price ", pair_price, sep=":")

    current_price = get_waves_price(symbol_=symbol)
    if current_price:
        print("symbol price ", current_price, sep=":")
