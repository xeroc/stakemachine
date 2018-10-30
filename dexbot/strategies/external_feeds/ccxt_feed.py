# -*- coding: utf-8 -*-
import os, sys, time, math
import click
import ccxt  # noqa: E402
from pprint import pprint
from styles import *
from process_pair import *


def get_exch_symbols(exchange):
    return exchange.symbols
    

def get_exchanges():
    return ccxt.exchanges


def get_ticker(exchange, symbol):
    try:        
        # get raw json data
        ticker = exchange.fetch_ticker(symbol.upper())    

    except ccxt.DDoSProtection as e:
        print(type(e).__name__, e.args, 'DDoS Protection (ignoring)')
    except ccxt.RequestTimeout as e:
        print(type(e).__name__, e.args, 'Request Timeout (ignoring)')
    except ccxt.ExchangeNotAvailable as e:
        print(type(e).__name__, e.args, 'Exchange Not Available due to downtime or maintenance (ignoring)')
    except ccxt.AuthenticationError as e:
        print(type(e).__name__, e.args, 'Authentication Error (missing API keys, ignoring)')
        
    return ticker



###### unit tests ######
@click.group()
def main():
    pass


@main.command()
@click.argument('exchange')
@click.argument('symbol')
def test_feed(exchange, symbol):
    '''
    Usage: exchange [symbol]   
    Symbol is required, for example:
    python ccxt_feed.py test_feed gdax BTC/USD
    ''' 
    usage = "Usage: python ccxt_feed.py id [symbol]\nSymbol is required, for example: python ccxt_feed.py gdax BTC/USD"

    try:
        id = exchange  # get exchange id from command line arguments

        # check if the exchange is supported by ccxt
        exchange_found = id in ccxt.exchanges

        if exchange_found:
            print_args('Instantiating', green(id))

            # instantiate the exchange by id
            exch = getattr(ccxt, id)()

            # load all markets from the exchange
            markets = exch.load_markets()
            
            sym = symbol
            if sym:
                ticker = get_ticker(exch, sym) 
                print_args(
                    green(exch.id),
                    yellow(sym),
                    'ticker',
                    ticker['datetime'],
                    'high: ' + str(ticker['high']),
                    'low: ' + str(ticker['low']),
                    'bid: ' + str(ticker['bid']),
                    'ask: ' + str(ticker['ask']),
                    'volume: ' + str(ticker['quoteVolume']))
            else: 
                print_args('Symbol not found')
                print_exch_symbols(exch)
                print(usage)
        
        else:
            print_args('Exchange ' + red(id) + ' not found')
            print(usage)
    except Exception as e:
        print(type(e).__name__, e.args, str(e))
        print(usage)


@main.command()
def test_exch_list():
    '''
    gets a list of supported exchanges
    '''
    supported_exchanges = get_exchanges()
    exch_list = ', '.join(str(name) for name in supported_exchanges)
    print(bold(underline('Supported exchanges: ')))
    pprint(exch_list, width=80)


@main.command()
@click.argument('exchange')
def test_exch_sym(exchange):
    ''' 
    print all symbols from an exchange
    '''
    # output all symbols    
    print_args(green(id), 'has', len(exchange.symbols), 'symbols:', yellow(', '.join(exchange.symbols)))



if __name__ == '__main__':
    main()
    

