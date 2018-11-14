import requests

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


def get_waves_price(base, quote):
    current_price = get_last_price(base, quote)
    
    if current_price is None: # try inversion
        price = get_last_price(quote, base)
        current_price = 1/float(price)        
    return current_price



if __name__ == '__main__':
    
    symbol = 'BTC/USD'  # quote/base for external exchanges
    print(symbol, "=")
    pair = split_pair(symbol)             
    current_price = get_waves_price(pair[1], pair[0])
    print(current_price)
    
