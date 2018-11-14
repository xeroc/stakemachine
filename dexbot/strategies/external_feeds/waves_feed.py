import requests
from dexbot.strategies.external_feeds.process_pair import split_pair, filter_prefix_symbol, filter_bit_symbol, debug

WAVES_URL = 'https://marketdata.wavesplatform.com/api/'
SYMBOLS_URL = "/symbols"
MARKET_URL = "/ticker/"


def get_json(url):
    r = requests.get(url)
    json_obj = r.json()
    return json_obj


def get_waves_symbols():
    symbol_list = get_json(WAVES_URL + SYMBOLS_URL)
    return symbol_list


def get_last_price(base, quote):
    current_price = None
    try:                
        market_bq = MARKET_URL + quote  +'/'+ base # external exchange format
        ticker = get_json(WAVES_URL + market_bq)
        current_price = ticker['24h_close']        
    except Exception as e:       
        pass  # No pair found on waves dex for external price. 
    return current_price


def get_waves_by_pair(pair):
    current_price = get_last_price(pair[1], pair[0]) # base, quote
    if current_price is None: # try inversion
        price = get_last_price(pair[0], pair[1])
        current_price = 1/float(price)        
    return current_price


def get_waves_price(**kwargs):
    price = None
    for key, value in list(kwargs.items()):
        print("The value of {} is {}".format(key, value))
        if key == "pair_":
            price = get_waves_by_pair(value)
        elif key == "symbol_":
            pair = split_pair(value)
            price = get_waves_by_pair(pair)
    return price
    

if __name__ == '__main__':
    
    symbol = 'BTC/USD'  # quote/base for external exchanges
    print(symbol, "=")
    raw_pair = split_pair(symbol)
    pair = [filter_bit_symbol(j) for j in [filter_prefix_symbol(i) for i in raw_pair]]

    pair_price = get_waves_price(pair_=pair)
    print("pair price", pair_price)
    
#    current_price = get_waves_price(pair[1], pair[0])
    current_price = get_waves_price(symbol_=symbol)
    print("symbol price", current_price)
    
