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
            * **maxamount**: The max amount of 'quote' for a replicated order
            * **minamount**: The min amount of an order to be replicated

        Only used if run in continuous mode (e.g. with ``stakemachine run``):

        * **skip_blocks**: Checks the market only every x blocks

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
              skip_blocks: 1
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
        self.block_counter = -1

    def init(self):
        if "replicated" not in self.state:
            self.state["replicated"] = {}

        ticker = self.dex.returnTicker()
        for replicate in self.settings["replicate"]:
            source = self.dex._get_assets_from_market(replicate["source"])
            target = self.dex._get_assets_from_market(replicate["target"])

            base_market = target["base"]["symbol"] + self.config.market_separator + source["base"]["symbol"]
            if source["quote"]["symbol"] != target["quote"]["symbol"]:
                raise ValueError("The quotes of source and target in "
                                 "a replicate need to be identical")
            if (replicate["source"] not in self.settings["markets"] or
                    replicate["target"] not in self.settings["markets"]):
                raise ValueError("Please add ALL source and target "
                                 "markets to the 'markets' settings.")
            if base_market not in self.settings["markets"]:
                raise ValueError("Please add %s " % base_market +
                                 "to the 'markets' settings.")
            if ("settlement_price" not in ticker[base_market] and
                    replicate["price"] == "feed"):
                raise ValueError("The market %s " % base_market +
                                 "has no settlement/feed price!")

    def orderFilled(self, oid):
        pass

    def tick(self, *args, **kwargs):
        self.block_counter += 1
        if (self.block_counter % self.settings["skip_blocks"]) != 0:
            return
        self.place()

    def orderCanceled(self, oid):
        for o in self.state["replicated"].copy():  # copy the list so I can iterate AND pop
            if ("replicatedOrder" in self.state["replicated"][o] and
                    self.state["replicated"][o]["replicatedOrder"] == oid):
                self.state["replicated"].pop(o, None)

    def orderPlaced(self, orderid):
        """ Get the new order ID for the replicated order
        """
        pass
        """ Legacy code that could be used eventually to make the bot
            faster
        """
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
        """

    def place(self):
        ticker = self.dex.returnTicker()
        for replicate in self.settings["replicate"]:
            source = self.dex._get_assets_from_market(replicate["source"])
            target = self.dex._get_assets_from_market(replicate["target"])

            # Get base price, e.g. price feed
            if replicate["price"] == "feed":
                base_market = target["base"]["symbol"] + self.config.market_separator + source["base"]["symbol"]
                base_price = ticker[base_market]["settlement_price"]
            else:
                raise ValueError("Invalid option for 'price'!")

            # Obtain order book of the source market
            orderbook = self.dex.returnOrderBook(
                replicate["source"],
                limit=replicate["limit"]
            )

            ###################################################################
            # Test for NEW orders that we have not replicated
            ###################################################################

            # As we are only 'selling' in this strategy, we only
            # consider replicating 'asks' for different markets!
            for order in orderbook[replicate["source"]]["asks"]:
                balances = self.returnBalances()
                quote_symbol = target["quote"]["symbol"]

                # Define and limit the amounts
                amount = order[1]
                if ("maxamount" in replicate and
                        amount > replicate["maxamount"]):
                    amount = replicate["maxamount"]
                if quote_symbol not in balances:
                    continue

                if amount > balances.get(quote_symbol):
                    amount = balances.get(quote_symbol)
                if ("minamount" in replicate and
                        amount < replicate["minamount"]):
                    continue
                if not amount:
                    continue

                # Already have this order replicated?
                orderid = order[2]
                if orderid in self.state["replicated"]:
                    continue

                # derive the new sell price
                price = order[0]
                sell_price = price / base_price
                if "premium" in replicate:
                    sell_price *= float(1 + replicate["premium"] / 100)

                # Print a notification
                print(
                    "Existing bid in %s" % (replicate["source"]) +
                    ": %f @ %f %s/%s, " % (amount, price, source["base"]["symbol"], source["quote"]["symbol"]) +
                    "feed @%f %s/%s, " % (base_price, source["base"]["symbol"], target["base"]["symbol"]) +
                    "new price: %.10f %s/%s" % (sell_price, target["base"]["symbol"], target["quote"]["symbol"])
                )

                # Do the actual sell
                replicatedOrder = self.sell(
                    replicate["target"],
                    sell_price,
                    amount,
                    returnID=True
                )

                # Store side information of the replicated data
                self.state["replicated"][orderid] = {
                    "source": replicate["source"],
                    "target": replicate["target"],
                    "price": price,
                    "sell_price": sell_price,
                    "amount": amount,
                    "replicatedOrder": replicatedOrder
                }

            ###################################################################
            # See if we can clear some orders that no longer exist
            ###################################################################
            orders  = [x[2] for x in orderbook[replicate["source"]]["asks"]]
            for repOrderId in self.state["replicated"]:
                if (repOrderId not in orders and
                        "replicatedOrder" in self.state["replicated"]):
                    self.cancel(self.state["replicated"]["replicatedOrder"])
