import asyncio

import ccxt.async_support as accxt


async def print_ticker(symbol, exchange_id):
    # Verbose mode will show the order of execution to verify concurrency
    exchange = getattr(accxt, exchange_id)({'verbose': True})
    await exchange.fetch_ticker(symbol)
    await exchange.close()


async def get_ccxt_load_markets(exchange_id):
    exchange = getattr(accxt, exchange_id)({'verbose': False})
    symbols = await exchange.load_markets()
    await exchange.close()
    return symbols


async def fetch_ticker(exchange, symbol):
    ticker = None
    try:
        ticker = await exchange.fetch_ticker(symbol.upper())
    except Exception as e:
        print(type(e).__name__, e.args, 'Exchange Error (ignoring)')
    except ccxt.RequestTimeout as e:
        print(type(e).__name__, e.args, 'Request Timeout (ignoring)')
    except ccxt.ExchangeNotAvailable as e:
        print(type(e).__name__, e.args, 'Exchange Not Available due to downtime or maintenance (ignoring)')
    await exchange.close()
    return ticker


def get_ccxt_price(symbol, exchange_name):
    """ Get all tickers from multiple exchanges using async """
    center_price = None
    exchange = getattr(accxt, exchange_name)({'verbose': False})
    ticker = asyncio.get_event_loop().run_until_complete(fetch_ticker(exchange, symbol))
    if ticker:
        center_price = (ticker['bid'] + ticker['ask']) / 2
    return center_price
