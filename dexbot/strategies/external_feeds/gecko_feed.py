import click
import requests

from dexbot.strategies.external_feeds.styles import yellow
from dexbot.strategies.external_feeds.process_pair import split_pair, filter_prefix_symbol, filter_bit_symbol
"""
    To use Gecko API, note that gecko does not provide pairs by default.
    For base/quote one must be listed as ticker and the other as fullname,
    i.e. BTCUSD is vs_currency = usd , ids = bitcoin
    https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&ids=bitcoin
"""
GECKO_COINS_URL = 'https://api.coingecko.com/api/v3/coins/'
isDebug = False


def debug(*args):
    if isDebug:
        print(' '.join([str(arg) for arg in args]))


def print_usage():
    print("Usage: python3 gecko_feed.py", yellow('[symbol]'),
          "Symbol is required, for example:", yellow('BTC/USD'), sep='')


def get_json(url):
    r = requests.get(url)
    json_obj = r.json()
    return json_obj


def check_gecko_symbol_exists(coin_list, symbol):
    try:
        symbol_name = [obj for obj in coin_list if obj['symbol'] == symbol][0]['id']
        return symbol_name
    except IndexError:
        return None


def get_gecko_market_price(base, quote):
    try:
        coin_list = get_json(GECKO_COINS_URL+'list')
        quote_name = check_gecko_symbol_exists(coin_list, quote.lower())
        lookup_pair = "?vs_currency="+base.lower()+"&ids="+quote_name
        market_url = GECKO_COINS_URL+'markets'+lookup_pair
        debug(market_url)
        ticker = get_json(market_url)
        current_price = None
        for entry in ticker:
            current_price = entry['current_price']
            high_24h = entry['high_24h']
            low_24h = entry['low_24h']
            total_volume = entry['total_volume']
        return current_price
    except TypeError:
        return None


# Unit tests
# Todo: Move tests to own files
@click.group()
def main():
    pass


@main.command()
@click.argument('symbol')
def test_feed(symbol):
    """
        [symbol]  Symbol example: btc/usd or btc:usd
    """
    try:
        pair = split_pair(symbol)  # pair=[quote, base]
        filtered_pair = [filter_bit_symbol(j) for j in [filter_prefix_symbol(i) for i in pair]]
        debug(filtered_pair)
        new_quote = filtered_pair[0]
        new_base = filtered_pair[1]
        current_price = get_gecko_market_price(new_base, new_quote)

        if current_price is None:   # Try inverted version
            debug(" Trying pair inversion...")
            current_price = get_gecko_market_price(new_quote, new_base)
            print(new_base + '/' + new_quote,  str(current_price), sep=':')
            if current_price is not None:   # Re-invert price
                actual_price = 1/current_price
                print(new_quote + '/' + new_base, str(actual_price), sep=':')
        else:
            print(symbol, current_price, sep=':')
    except Exception as e:
        print(type(e).__name__, e.args, str(e))
        print_usage()


if __name__ == '__main__':
    main()
