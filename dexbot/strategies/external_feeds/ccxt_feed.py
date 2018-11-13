import click
import asyncio
import functools
import ccxt.async_support as accxt
from pprint import pprint

def get_exchanges():
    return ccxt.exchanges


async def print_ticker(symbol, id):
    # Verbose mode will show the order of execution to verify concurrency
    exchange = getattr(accxt, id)({'verbose': True})
    await exchange.fetch_ticker(symbol)
    await exchange.close()


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
    exchange = getattr(accxt, exchange_name)({'verbose':False})
    ticker = asyncio.get_event_loop().run_until_complete(
        fetch_ticker(exchange, symbol))
    if ticker:
        center_price = (ticker['bid'] + ticker['ask'])/2
    return center_price


if __name__ == '__main__':

    exchanges =['bitfinex', 'kraken', 'binance', 'gdax']
    symbol = 'BTC/USDT'    
    center_price = [get_ccxt_price(symbol, e) for e in exchanges]
    print(' exchange: ', exchanges, ' symbol: ', symbol, sep=':')
    print(' center_price: ', center_price)
