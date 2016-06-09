from .basestrategy import BaseStrategy, MissingSettingsException
from pprint import pprint


class ReplicateBooks(BaseStrategy):
    """ This strategy can be used to replicate orders from *similar*
        source markets into a target market.

        * **markets**: **ALL** markets that are used in either source, or target in the replication process
        * **replicate**: A list of to replicate markets and settings

            * **source**: Source Market
            * **target**: Target Market
            * **price**: derive the price according to "feed" (only option available atm)
            * **limit**: Limit to x orders per replication
            * **premium**: Percentage premium for replication

        **Example Configuration**:

        The following example replicates orders from

        * CASH.USD:BTS
        * CASH.BTC:BTS

        into

        * CASH.USD:CASH.BTC

        and uses the corresponding price feed to derive a price.
        E.g., when copying orders from CASH.USD:BTS, into
        CASH.USD:CASH.BTC the price for CASH.BTC is taken from the price
        feed against BTS.

        .. code-block:: yaml

             BitCashReplicate:
              module: "stakemachine.strategies.replicatebooks"
              bot: "ReplicateBooks"
              markets:
               - "CASH.BTC:CASH.USD"
               - "CASH.BTC:BTS"
               - "CASH.USD:BTS"
              replicate:
               - source: "CASH.USD:BTS"
                 target: "CASH.USD:CASH.BTC"
                 price: "feed"
                 premium: 0.0
                 limit: 25
               - source: "CASH.BTC:BTS"
                 target: "CASH.BTC:CASH.USD"
                 price: "feed"
                 premium: 0.0
                 limit: 25
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def init(self):
        if "replicated" not in self.state:
            self.state["replicated"] = {}

    def orderFilled(self, oid):
        pass

    def tick(self, *args, **kwargs):
        self.place()
        pass

    def orderCanceled(self, oid):
        for o in self.state["replicated"].copy():  # copy the list so I can iterate AND pop
            if ("replicatedOrder" in self.state["replicated"][o] and
                    self.state["replicated"][o]["replicatedOrder"] == oid):
                self.state["replicated"].pop(o, None)

    def orderPlaced(self, orderid):
        """ Get the new order ID for the replicated order
        """
        orders = self.dex.returnOpenOrders()
        for i in self.state["replicated"]:
            replicated = self.state["replicated"][i]
            m = replicated["target"]
            for order in orders[m]:
                # Get the placed order and compare prices.
                # If the match, we have the order id for that
                # particular replicated order
                if (order["orderNumber"] == orderid):
                    # prices are normalized because of float
                    # represenation differing from the ratio of two
                    # integers (as it is done in graphene/bitshares)
                    priceA = self.dex.normalizePrice(replicated["target"], replicated["sell_price"])
                    priceB = self.dex.normalizePrice(replicated["target"], order["rate"])
                    if priceA == priceB:
                        self.state["replicated"][i]["replicatedOrder"] = order["orderNumber"]
                    break

    def place(self):
        ticker = self.dex.returnTicker()
        for replicate in self.settings["replicate"]:
            source = self.dex._get_assets_from_market(replicate["source"])
            target = self.dex._get_assets_from_market(replicate["target"])
            if replicate["price"] == "feed":
                base_market = target["base"]["symbol"] + self.config.market_separator + source["base"]["symbol"]
                base_price = ticker[base_market]["settlement_price"]
            else:
                raise ValueError("Invalid option for 'price'!")

            openOrders = self.dex.returnOpenOrders(replicate["target"])
            orderbook = self.dex.returnOrderBook(
                replicate["source"],
                limit=replicate["limit"]
            )
            # As we are only 'selling' in this strategy, we only
            # consider replicating 'asks' for different markets!
            for order in orderbook[replicate["source"]]["asks"]:
                price = order[0]
                amount = order[1] if ("maxamount" in replicate and
                                      order[1] < replicate["maxamount"]) else replicate["maxamount"]
                orderid = order[2]
                sell_price = price / base_price
                if "premium" in replicate:
                    sell_price *= float(1 + replicate["premium"] / 100)

                if orderid in self.state["replicated"]:
                    # Already have a matching order
                    continue

                existingOrder = False
                for openorder in openOrders[replicate["target"]]:
                    if sell_price == openorder["rate"]:
                        existingOrder = True
                        break

                if not existingOrder:
                    print(
                        "Existing bid in %s" % (replicate["source"]) +
                        ": %f @ %f %s/%s, " % (amount, price, source["base"]["symbol"], source["quote"]["symbol"]) +
                        "feed @%f %s/%s, " % (base_price, source["base"]["symbol"], target["base"]["symbol"]) +
                        "new price: %.10f %s/%s" % (sell_price, target["base"]["symbol"], target["quote"]["symbol"])
                    )
                    self.sell(
                        replicate["target"],
                        sell_price,
                        amount
                    )
                    self.state["replicated"][orderid] = {
                        "source": replicate["source"],
                        "target": replicate["target"],
                        "price": price,
                        "sell_price": sell_price,
                        "amount": amount
                    }
