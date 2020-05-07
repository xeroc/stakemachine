import click

from dexbot.strategies.external_feeds.gecko_feed import get_gecko_price
from dexbot.strategies.external_feeds.process_pair import split_pair
from dexbot.styles import yellow


def print_usage():
    print(
        "Usage: python3 gecko_feed.py",
        yellow('[symbol]'),
        "Symbol is required, for example:",
        yellow('BTC/USD'),
        sep='',
    )


# Unit tests
@click.group()
def main():
    pass


@main.command()
@click.argument('symbol')
def test_feed(symbol):
    """[symbol]  Symbol example: btc/usd or btc:usd."""
    try:
        price = get_gecko_price(symbol_=symbol)
        print(price)
        pair = split_pair(symbol)
        price = get_gecko_price(pair_=pair)
    except Exception as e:
        print_usage()
        print(type(e).__name__, e.args, str(e))


if __name__ == '__main__':
    main()
