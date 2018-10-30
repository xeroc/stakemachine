import asyncio
import aiohttp

# docs
# Gecko https://www.coingecko.com/api_doc/3.html
# CCXT https://github.com/ccxt/ccxt
# Waves https://marketdata.wavesplatform.com/

# Cryptowat.ch  https://cryptowat.ch/docs/api#pairs-index
# Asset: Returns a single asset. Lists all markets which have this asset as a base or quote.
# Example: https://api.cryptowat.ch/assets/btc

#Index: Returns all assets (in no particular order).
# Example: https://api.cryptowat.ch/assets

gecko_coins_url = 'https://api.coingecko.com/api/v3/coins/'
waves_symbols = 'http://marketdata.wavesplatform.com/api/symbols'
cwatch_assets='https://api.cryptowat.ch/assets'

urls = [cwatch_assets, waves_symbols, gecko_coins_url]

@asyncio.coroutine
def call_url(url):
    print('Starting {}'.format(url))
    response = yield from aiohttp.ClientSession().get(url)
    data = yield from response.text()
    print('url: {} bytes: {}'.format(url, len(data)))
#    print('{}: {} bytes: {}'.format(url, len(data), data))    
    return data



futures = [call_url(url) for url in urls]

asyncio.run(asyncio.wait(futures))
