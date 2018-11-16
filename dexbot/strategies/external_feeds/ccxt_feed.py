import click
import json
import asyncio
import functools
import ccxt.async_support as accxt
from pprint import pprint


async def print_ticker(symbol, id):
    # Verbose mode will show the order of execution to verify concurrency
    exchange = getattr(accxt, id)({'verbose': True})
    await exchange.fetch_ticker(symbol)
    await exchange.close()


async def get_ccxt_load_markets(exchange_id):
    exchange = getattr(accxt, exchange_id)({'verbose': False})
    symbols  = await exchange.load_markets()
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
    exchange = getattr(accxt, exchange_name)({'verbose':False})
    ticker = asyncio.get_event_loop().run_until_complete(fetch_ticker(exchange, symbol))
    if ticker:
        center_price = (ticker['bid'] + ticker['ask'])/2
    return center_price


if __name__ == '__main__':
    #    result = asyncio.get_event_loop().run_until_complete(print_ticker(symbol, 'bitfinex'))    
    exchanges =['bitfinex', 'kraken', 'binance', 'gdax']
    symbol = 'BTC/USDT'
    
    # testing get all pairs.
    for exchange_id in exchanges:
        print("\n\n\n")
        print(exchange_id)
        result = asyncio.get_event_loop().run_until_complete(get_ccxt_load_markets(exchange_id))
        all_symbols= [obj for obj in result]
        print(all_symbols)
        
    # testing get center price
    # center_price = [asyncio.get_event_loop().run_until_complete(get_ccxt_price(symbol, e)) for e in exchanges]

    center_price = [get_ccxt_price(symbol, e) for e in exchanges]
    print(' exchange: ', exchanges, ' symbol: ', symbol, sep=':')
    print(' center_price: ', center_price)

