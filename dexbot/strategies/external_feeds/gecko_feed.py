import requests
import asyncio
from dexbot.strategies.external_feeds.process_pair import split_pair, debug

"""
    To use Gecko API, note that gecko does not provide pairs by default.
    For base/quote one must be listed as ticker and the other as fullname,
    i.e. BTCUSD is vs_currency = usd , ids = bitcoin
    https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&ids=bitcoin
"""
GECKO_COINS_URL = 'https://api.coingecko.com/api/v3/coins/'


async def get_json(url):
    r = requests.get(url)
    json_obj = r.json()
    return json_obj


def _get_market_price(base, quote):
    try:
        coin_list = asyncio.get_event_loop().run_until_complete(get_json(GECKO_COINS_URL + 'list'))
        quote_name = check_gecko_symbol_exists(coin_list, quote.lower())
        lookup_pair = "?vs_currency=" + base.lower() + "&ids=" + quote_name
        market_url = GECKO_COINS_URL + 'markets' + lookup_pair
        debug(market_url)
        ticker = asyncio.get_event_loop().run_until_complete(get_json(market_url))
        current_price = None
        for entry in ticker:
            current_price = entry['current_price']
            high_24h = entry['high_24h']
            low_24h = entry['low_24h']
            total_volume = entry['total_volume']
        return current_price
    except TypeError:
        return None


def check_gecko_symbol_exists(coin_list, symbol):
    try:
        symbol_name = [obj for obj in coin_list if obj['symbol'] == symbol][0]['id']
        return symbol_name
    except IndexError:
        return None


def get_gecko_price_by_pair(pair):
    current_price = None
    try:
        quote = pair[0]
        base = pair[1]
        current_price = _get_market_price(base, quote)
        if current_price is None:  # Try inverted version
            debug("Trying pair inversion...")
            current_price = _get_market_price(quote, base)
            debug(base + '/' + quote, str(current_price))
            if current_price is not None:  # Re-invert price
                actual_price = 1 / current_price
                debug(quote + '/' + base, str(actual_price))
                current_price = actual_price
        else:
            debug(pair, current_price)
    except Exception as e:
        print(type(e).__name__, e.args, str(e))
    return current_price


def get_gecko_price(**kwargs):
    price = None
    for key, value in list(kwargs.items()):
        debug("The value of {} is {}".format(key, value))  # debug
        if key == "pair_":
            price = get_gecko_price_by_pair(value)
        elif key == "symbol_":
            pair = split_pair(value)  # pair=[quote, base]
            price = get_gecko_price_by_pair(pair)
    return price
