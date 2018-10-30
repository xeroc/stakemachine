# Python imports
import requests, json, sys
import click
from styles import *
from  process_pair import *

GECKO_COINS_URL = 'https://api.coingecko.com/api/v3/coins/'

"""To use Gecko API, first get coinlist to search for base/quote individually
gecko does not provide pairs by default. for base/quote one must be listed as ticker
and the other lsited as fullname, i.e. BTCUSD is vs_currency = usd , ids = bitcoin
https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&ids=bitcoin    
"""

isDebug = True

def debug(*args):
    if isDebug:
        print(' '.join([str(arg) for arg in args]))


def print_usage():
   print("Usage: python3 gecko_feed.py",
         yellow('[symbol]'), 
         "Symbol is required, for example:", 
         yellow('BTC/USD'), sep='')


def get_gecko_json(url): 
    r = requests.get(url)
    json_obj = r.json()
    return json_obj
    

def check_gecko_symbol_exists(coinlist, symbol):    
    try:
        symbol_name = [obj for obj in coinlist if obj['symbol']==symbol][0]['id']
        return symbol_name
    except IndexError:
        return None
    

def get_gecko_market_price(base, quote):

    try:        
        coin_list = get_gecko_json(GECKO_COINS_URL+'list')
        quote_name = check_gecko_symbol_exists(coin_list, quote.lower())
        
        lookup_pair = "?vs_currency="+base.lower()+"&ids="+quote_name
        market_url = GECKO_COINS_URL+'markets'+lookup_pair
        debug(market_url)
                
        ticker = get_gecko_json(market_url)

        for entry in ticker:
            current_price = entry['current_price']
            high_24h = entry['high_24h']
            low_24h = entry['low_24h']
            total_volume = entry['total_volume']
            
        return current_price

    except TypeError:
        return None


### Unit tests
@click.group()
def main():
    pass

@main.command()
@click.argument('symbol')
def test_feed(symbol):
    '''
    [symbol]  Symbol example: btc/usd or btc:usd

    base currency for coin gecko is in USD,EUR,JPY, CAD, etc, 
    see entire list here: https://api.coingecko.com/api/v3/global
    
    Gecko Example of no market = BTC/USDT
    Gecko Example of working market BTC/EUR or BTC/USD
    '''
    try:
        pair = split_pair(symbol) #  pair = [quote, base]
        filtered_pair = [filter_bit_symbol(j) for j in  [filter_prefix_symbol(i) for i in pair]]
        debug(filtered_pair)

        new_quote = filtered_pair[0]
        new_base = filtered_pair[1]

        current_price = get_gecko_market_price(new_base, new_quote)
        debug(current_price)
        
        if current_price is None:
            # try inverted version
            debug(" Trying pair inversion...")
            current_price = get_gecko_market_price(new_quote, new_base)
            # invert price
            debug(new_base+"/"+new_quote+ ":"+ str(current_price))
            if current_price is not None:
                actual_price = 1/current_price
                debug(new_quote+"/"+new_base+ ":"+ str(actual_price))

    except Exception as e:
        print(type(e).__name__, e.args, str(e))
        print_usage()




if __name__ == '__main__':
    main()

