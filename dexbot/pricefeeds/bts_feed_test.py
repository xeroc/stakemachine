from bitshares.bitshares import BitShares
from bitshares.market import Market
#from bitshares.price import Order

from dexbot.pricefeeds.bts_feed import PriceFeed

node_url = "wss://api.fr.bitsharesdex.com/ws"

TEST_CONFIG = {
    'node': node_url
}

bts = BitShares(node=TEST_CONFIG['node'])

print("Bitshares Price Feed Test")

market = Market("USD:BTS")
print(market.ticker())

pf = PriceFeed(market=market, bitshares_instance=bts)

market = pf.market
print("Market we are examining:", market, sep=':')

center_price = pf.get_market_center_price(base_amount=0, quote_amount=0, suppress_errors=False)
print("center price:", center_price, sep=':')

print("\nList of buy orders:")
buy_orders = pf.get_market_buy_orders(depth=10)
for order in buy_orders:
    print(order)

order1 = buy_orders[0]
print("\nGet top of buy orders", order1, sep=':')

print("\nList of Buy orders in ASC price")
asc_buy_orders = pf.sort_orders_by_price(buy_orders, sort='ASC')
for order in asc_buy_orders:
    print(order)

sell_orders = pf.get_market_sell_orders(depth=10)
print("\nMarket Sell Orders", sell_orders, sep=':')

mkt_orders = pf.get_market_orders(depth=1, updated=True)
print("\nMarket Orders", mkt_orders, sep=":")

mkt_buy_price = pf.get_market_buy_price(quote_amount=0, base_amount=0)
print("market buy price", mkt_buy_price, sep=':')

mkt_sell_price = pf.get_market_sell_price(quote_amount=0, base_amount=0)
print("market sell price", mkt_sell_price, sep=':')

mkt_spread = pf.get_market_spread(quote_amount=0, base_amount=0)
print("market spread", mkt_spread, sep=':')


# todo:
# filter buy/sell orders (2)
# get_updated_limit_order (static method)

