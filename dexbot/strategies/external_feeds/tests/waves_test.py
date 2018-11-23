from dexbot.strategies.external_feeds.process_pair import split_pair, filter_prefix_symbol, filter_bit_symbol
from dexbot.strategies.external_feeds.waves_feed import get_waves_price        

if __name__ == '__main__':

        symbol = 'BTC/USD'  # quote/base for external exchanges
        print(symbol, "=")
        raw_pair = split_pair(symbol)
        pair = [filter_bit_symbol(j) for j in [filter_prefix_symbol(i) for i in raw_pair]]
        
        pair_price = get_waves_price(pair_=pair)
        if pair_price is not None:
                print("pair price", pair_price, sep=":")

        current_price = get_waves_price(symbol_=symbol)
        if current_price is not None:
                print("symbol price", current_price, sep=":")
    
