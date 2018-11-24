import click
import asyncio
from dexbot.strategies.external_feeds.ccxt_feed import get_ccxt_load_markets, get_ccxt_price

"""
This is the unit test for getting external feed data from CCXT using ccxt_feed module.
"""


if __name__ == '__main__':

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
    center_price = [get_ccxt_price(symbol, e) for e in exchanges]
    print(' exchange: ', exchanges, ' symbol: ', symbol, sep=':')
    print(' center_price: ', center_price)


