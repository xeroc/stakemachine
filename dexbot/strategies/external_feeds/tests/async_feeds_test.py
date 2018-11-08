import asyncio
import aiohttp

gecko_coins_url = 'https://api.coingecko.com/api/v3/coins/'
waves_symbols = 'http://marketdata.wavesplatform.com/api/symbols'
cwatch_assets = 'https://api.cryptowat.ch/assets'
urls = [cwatch_assets, waves_symbols, gecko_coins_url]


@asyncio.coroutine
def call_url(url):
    print('Starting {}'.format(url))
    response = yield from aiohttp.ClientSession().get(url)
    data = yield from response.text()
    print('url: {} bytes: {}'.format(url, len(data)))
    return data


futures = [call_url(url) for url in urls]
asyncio.run(asyncio.wait(futures))
