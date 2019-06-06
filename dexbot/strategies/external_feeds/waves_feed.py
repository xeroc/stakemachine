import dexbot.strategies.external_feeds.process_pair
import requests
import asyncio

WAVES_URL = 'https://marketdata.wavesplatform.com/api/'
SYMBOLS_URL = "/symbols"
MARKET_URL = "/ticker/"


async def get_json(url):
    response = requests.get(url)
    return response.json()


def get_last_price(base, quote):
    current_price = None
    try:
        market_bq = MARKET_URL + quote + '/' + base  # external exchange format
        async_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(async_loop)
        ticker = asyncio.get_event_loop().run_until_complete(get_json(WAVES_URL + market_bq))
        current_price = ticker['24h_close']
    except Exception:
        pass  # No pair found on waves dex for external price.
    return current_price


def get_waves_symbols():
    async_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(async_loop)
    symbol_list = asyncio.get_event_loop().run_until_complete(get_json(WAVES_URL + SYMBOLS_URL))
    return symbol_list


def get_waves_by_pair(pair):
    current_price = get_last_price(pair[1], pair[0])  # base, quote
    if current_price is None:  # try inversion
        price = get_last_price(pair[0], pair[1])
        if price is not None:
            current_price = 1 / float(price)
    return current_price


def get_waves_price(**kwargs):
    price = None
    for key, value in list(kwargs.items()):
        dexbot.strategies.external_feeds.process_pair.debug("The value of {} is {}".format(key, value))
        if key == "pair_":
            price = get_waves_by_pair(value)
            dexbot.strategies.external_feeds.process_pair.debug(value, price)
        elif key == "symbol_":
            pair = dexbot.strategies.external_feeds.process_pair.split_pair(value)
            price = get_waves_by_pair(pair)
            dexbot.strategies.external_feeds.process_pair.debug(pair, price)
    return price
