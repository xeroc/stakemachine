# -*- coding: utf-8 -*-
import click
import asyncio
import functools
import ccxt.async_support as accxt
import ccxt  # noqa: E402
from pprint import pprint
from styles import green, yellow, bold, underline
from process_pair import print_args


def get_exchanges():
    return ccxt.exchanges


def get_ticker(exchange, symbol):
    try:
        ticker = exchange.fetch_ticker(symbol.upper())
    except ccxt.DDoSProtection as e:
        print(type(e).__name__, e.args, 'DDoS Protection (ignoring)')
    except ccxt.RequestTimeout as e:
        print(type(e).__name__, e.args,
            'Request Timeout (ignoring)')
    except ccxt.ExchangeNotAvailable as e:
        print(type(e).__name__, e.args,
            'Exchange Not Available due to downtime or maintenance (ignoring)')
    except ccxt.AuthenticationError as e:
        print(type(e).__name__, e.args,
            'Authentication Error (missing API keys, ignoring)')
    return ticker


async def fetch_ticker(exchange, symbol):
    ticker = await exchange.fetchTicker(symbol)
    await exchange.close()
    return ticker

async def print_ticker(symbol, id):
    # verbose mode will show the order of execution to verify concurrency
    exchange = getattr(accxt, id)({'verbose': True})
    print(await exchange.fetch_ticker(symbol))
    await exchange.close()


# unit tests
@click.group()
def main():
    pass


@main.command()
def test_async2():
    """
    get all tickers from multiple exchanges using async
    """
    symbol = 'ETH/BTC'
    print_ethbtc_ticker = functools.partial(print_ticker, symbol)
    [asyncio.ensure_future(print_ethbtc_ticker(id)) for id in [
        'bitfinex',
        'binance',
        'kraken',
        'gdax',
        'bittrex',
    ]]
    pending = asyncio.Task.all_tasks()
    loop = asyncio.get_event_loop()
    loop.run_until_complete(asyncio.gather(*pending))


@main.command()
def test_async():
    """
    get ticker for bitfinex using async
    """
    bitfinex = accxt.bitfinex({'enableRateLimit': True, })
    ticker = asyncio.get_event_loop().run_until_complete(
        fetch_ticker(bitfinex, 'BTC/USDT'))
    print(ticker)


@main.command()
@click.argument('exchange')
@click.argument('symbol')
def test_feed(exchange, symbol):
    """
    Usage: exchange [symbol]
    Symbol is required, for example:
    python ccxt_feed.py test_feed gdax BTC/USD
    """
    usage = "Usage: python ccxt_feed.py id [symbol]"
    try:
        id = exchange  # get exchange id from command line arguments
        exchange_found = id in ccxt.exchanges
        # check if the exchange is supported by ccxt
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
                print_exchange_symbols(exch)
                print(usage)
        else:
            print_args('Exchange ' + red(id) + ' not found')
            print(usage)
    except Exception as e:
        print(type(e).__name__, e.args, str(e))
        print(usage)


@main.command()
def test_exch_list():
    """
    gets a list of supported exchanges
    """
    supported_exchanges = get_exchanges()
    exch_list = ', '.join(str(name) for name in supported_exchanges)
    print(bold(underline('Supported exchanges: ')))
    pprint(exch_list, width=80)


if __name__ == '__main__':
    main()
