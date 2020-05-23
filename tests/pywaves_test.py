import pywaves as pw

"""
pywaves is an open source library for waves. While it is not as stable as REST API,
we leave the test here if integration is desired for future dexbot cross-exchange strategies.
"""

if __name__ == '__main__':

    try:
        # set the asset pair
        WAVES_BTC = pw.AssetPair(pw.WAVES, pw.BTC)

        # get last price and volume
        print(WAVES_BTC.last(), WAVES_BTC.volume(), sep=' ')

        # get ticker
        ticker = WAVES_BTC.ticker()
        print(ticker['24h_open'])
        print(ticker['24h_vwap'])

        # get last 10 trades
        trades = WAVES_BTC.trades(10)
        for t in trades:
            print(t['buyer'], t['seller'], t['price'], t['amount'], sep=' ')

        # get last 10 daily OHLCV candles
        ohlcv = WAVES_BTC.candles(1440, 10)
        for t in ohlcv:
            print(t['open'], t['high'], t['low'], t['close'], t['volume'], sep=' ')

    except Exception as e:
        print(type(e).__name__, e.args, 'Exchange Error (ignoring)')
