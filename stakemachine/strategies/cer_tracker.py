from .basestrategy import BaseStrategy, MissingSettingsException
import logging
log = logging.getLogger(__name__)


class CoreExchangeRateTracker(BaseStrategy):
    """ Play Buy/Sell Walls into a market

        This "strategy" takes the quote of the market and watches the
        core exchange rate. It can be used to keep the core exchange
        rate tracking different price metrics closely over time.

        .. note:: You will receive a warning if the quote is the core
                  asset and the base is not the core asset:

                  * USD:BTS - working
                  * BTS:USD - not working
                  * GOLD:SILVER - not working

        **Settings**:

        * **target_premium_percentage**: target premium relative to specified price metric
        * **target_relative_to**: relative to "highest_bid", "last", "price24h", "midprice"
        * **upper_bound_threshold**: thresholds in percent (CER will be updated if not between upper/lower)
        * **lower_bound_threshold**: thresholds in percent (CER will be updated if not between upper/lower)
        * **force_lower_than_higest_bid**: Force CER to be smaller than highest bid!

        Only used if run in continuous mode (e.g. with ``run_conf.py``):

        * **skip_blocks**: Checks the CER only every x blocks

        .. code-block:: yaml

              CERTracker:
                  module: "stakemachine.strategies.cer_tracker"
                  bot: "CoreExchangeRateTracker"
                  markets:
                    - "MKR:BTS"
                  target_premium_percentage: 2.0
                  target_relative_to: "highest_bid"
                  upper_bound_threshold: 15
                  lower_bound_threshold: 4
                  force_lower_than_higest_bid: True
                  skip_blocks: 100
    """

    block_counter = 0

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def init(self):
        if not self.dex.rpc:
            raise NotImplemented(
                "The CER tracker currently does not run with wif key"
            )
        """ Verify that the markets are against the core asset
        """
        sym = self.dex.core_asset["symbol"]
        for m in self.settings["markets"]:
            if sym != m.split(self.dex.market_separator)[1]:
                raise Exception(
                    "Base needs to be core asset %s" % sym
                )

        """ After startup, execute one tick()
        """
        self.tick()

    def update_asset_cer(self, asset_name, new_cer):
        """ Actually update the asset's cer
        """
        asset = self.dex.ws.get_asset(asset_name)
        options = asset["options"]
        core_asset = self.dex.core_asset

        base_amount = int(10 ** asset["precision"])
        quote_amount = int(new_cer * 10 ** core_asset["precision"])

        options["core_exchange_rate"] = {
            "base": {
                "amount": base_amount,
                "asset_id": asset["id"]},
            "quote": {
                "amount": quote_amount,
                "asset_id": "1.3.0"}
        }
        if not self.dex.rpc:
            log.critical(
                "This bot still requires a cli-wallet connection!"
            )
            return
        self.dex.rpc.update_asset(asset["symbol"], None, options, True)

    def update_cer(self, market):
        """ Calcualte the new CER
        """
        asset = market.split(self.dex.market_separator)[0]
        log.info("Updating CER of %s" % asset)

        ticker = self.dex.returnTicker()[market]
        premium = self.settings["target_premium_percentage"] / 100.0

        if self.settings["target_relative_to"] == "price24h":
            new_cer = ticker["price24h"] * (1.0 - premium)
        elif self.settings["target_relative_to"] == "midprice":
            new_cer = (ticker["lowestAsk"] + ticker["highestBid"]) / 2.0 * (1.0 - premium)
        elif self.settings["target_relative_to"] == "last":
            new_cer = ticker["last"] * (1.0 - premium)
        elif self.settings["target_relative_to"] == "highest_bid":
            new_cer = ticker["highestBid"] * (1.0 - premium)
        else:
            log.critical("Invalid option for 'target_relative_to'.  Skipping")
            return

        if (self.settings["force_lower_than_higest_bid"] and
                new_cer > ticker["highestBid"]):
            new_cer = ticker["highestBid"]

        self.update_asset_cer(asset, new_cer)

    def tick(self):
        """ Every block, see if we should check CER and update it if
            required
        """
        self.block_counter += 1
        if (self.block_counter % self.settings["skip_blocks"]) == 0:
            ticker = self.dex.returnTicker()
            for m in ticker:
                log.info("Checking CER of %s" % m.split(self.dex.market_separator)[0])
                cer = ticker[m]["core_exchange_rate"]
                price24h = ticker[m]["price24h"]
                highest_bid = ticker[m]["highestBid"]
                midprice = (ticker[m]["highestBid"] + ticker[m]["lowestAsk"]) / 2.0
                last = ticker[m]["last"]
                upper_bound = self.settings["upper_bound_threshold"]
                lower_bound = self.settings["lower_bound_threshold"]

                if self.settings["target_relative_to"] == "price24h":
                    premium = (1.0 - cer / price24h) * 100
                elif self.settings["target_relative_to"] == "midprice":
                    premium = (1.0 - cer / midprice) * 100
                elif self.settings["target_relative_to"] == "last":
                    premium = (1.0 - cer / last) * 100
                elif self.settings["target_relative_to"] == "highest_bid":
                    premium = (1.0 - cer / highest_bid) * 100
                else:
                    log.critical("Invalid option for 'target_relative_to'.  Skipping")
                    return

                if (premium < lower_bound or
                    premium > upper_bound or
                    (self.settings["force_lower_than_higest_bid"] and
                        highest_bid < cer)):

                    # Update CER!
                    self.update_cer(m)

    def orderFilled(self, oid):
        """ Do nothing """
        pass

    def place(self) :
        """ Do nothing """
        pass
