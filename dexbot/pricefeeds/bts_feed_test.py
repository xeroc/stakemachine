#from bitshares.bitshares import BitShares
from bitshares.market import Market
from dexbot.pricefeeds.bitshares import PriceFeed

node_url = "wss://api.fr.bitsharesdex.com/ws"

TEST_CONFIG = {
    'node': node_url
}

#bitshares = BitShares(node=TEST_CONFIG['node'])

print("this is a test")

market = Market("USD:BTS")
print(market.ticker())

#pf = PriceFeed(market=market, bitshares_instance=bitshares)

#center_price = pf.get_market_center_price(base_amount=0, quote_amount=0, suppress_errors=False)
#print(center_price)

#orders = pf.get_market_buy_orders(depth=10)
#print(orders)
