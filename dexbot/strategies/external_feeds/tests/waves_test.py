import pywaves as pw

# GET /ticker/{AMOUNT_ASSET}/{PRICE_ASSET}
#ticker_url = https://marketdata.wavesplatform.com/api/ticker/BTC/USD

def get_asset(symbol, coin_list):
        asset_id = None
        try:
                asset_id = [obj for obj in coin_list if obj['symbol'] == symbol][0]['assetID']                
        except IndexError as e:
                print(e)
        return pw.Asset(asset_id)

# set the asset pair
WAVES_BTC = pw.AssetPair(pw.WAVES, pw.BTC)

# get last price and volume
print("%s %s" % (WAVES_BTC.last(), WAVES_BTC.volume()))

# get ticker
ticker = WAVES_BTC.ticker()
print(ticker['24h_open'])
print(ticker['24h_vwap'])

# get last 10 trades
trades = WAVES_BTC.trades(10)
for t in trades:
	print("%s %s %s %s" % (t['buyer'], t['seller'], t['price'], t['amount']))
	
# get last 10 daily OHLCV candles
ohlcv = WAVES_BTC.candles(1440, 10)
for t in ohlcv:
	print("%s %s %s %s %s" % (t['open'], t['high'], t['low'], t['close'], t['volume']))
