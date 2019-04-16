from bitshares.bitshares import BitShares
from bitshares.market import Market
from dexbot.pricefeeds.bts_feed import PriceFeed

node_url = "wss://api.fr.bitsharesdex.com/ws"

TEST_CONFIG = {
    'node': node_url
}

bts = BitShares(node=TEST_CONFIG['node'])

print("Bitshares Price Feed Test")

market = Market("USD:BTS")
#print(market.ticker())

pf = PriceFeed(market=market)

center_price = pf.get_market_center_price(base_amount=0, quote_amount=0, suppress_errors=False)
print(center_price)

orders = pf.get_market_buy_orders(depth=10)
print(orders)
