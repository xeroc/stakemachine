from .basestrategy import BaseStrategy, MissingSettingsException
from pprint import pprint


class RefundFeePool(BaseStrategy):
    """ Keep an asset's fee pool funded

        This "strategy" takes the quote of the market and watches the
        asset's fee pool. If it passes the lower threshold, it will
        automatically try to refill it back to the specified balance.

        .. note:: You will receive a warning if the quote is the core
                  asset and the base is not the core asset:

                  * USD:BTS - working
                  * BTS:USD - not working
                  * GOLD:SILVER - not working

        **Settings**:

        * **target_fill_rate**: target balance of the fee pool (in BTS). The bot will not put more than this into the pool
        * **lower_threshold**: lower threshold of the core asset (e.g.  BTS). If this is reached, the bot will try to refill the pool

        Only used if run in continuous mode (e.g. with ``run_conf.py``):

        * **skip_blocks**: Checks the CER only every x blocks

        .. code-block:: yaml

            PoolRefill:
                module: "stakemachine.strategies.refund_fee_pool"
                bot: "RefundFeePool"
                markets:
                    - "MKR:BTS"
                    - "OPEN.BTC:BTS"
                target_fill_rate: 5000.0
                lower_threshold: 100.0
                skip_blocks: 1

    """

    block_counter = 0

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def init(self):
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

    def refill_fee_pool(self, quote_symbol, amount):
        """ Actually refill the fee pool
        """
        if not self.dex.rpc:
            raise Exception(
                "This bot still requires a cli-wallet connection"
            )
        pprint(self.dex.rpc.fund_asset_fee_pool(
            self.config.account,
            quote_symbol,
            amount,
            False)
        )

    def tick(self):
        """ We can check every block if the fee pool goes belos the
            lower threshold and initiate a refill
        """
        self.block_counter += 1
        if (self.block_counter % self.settings["skip_blocks"]) == 0:
            for m in self.settings["markets"]:
                quote_symbol = m.split(self.dex.market_separator)[0]
                print("Checking fee pool of %s" % quote_symbol)
                asset = self.dex.ws.get_asset(quote_symbol)
                core_asset = self.dex.getObject("1.3.0")
                asset_data = self.dex.getObject(asset["dynamic_asset_data_id"])
                fee_pool = int(asset_data["fee_pool"]) / 10 ** core_asset["precision"]

                amount = '{:.{prec}f}'.format(self.settings["target_fill_rate"] - fee_pool,
                                              prec=core_asset["precision"])
                if fee_pool < self.settings["lower_threshold"]:
                    self.refill_fee_pool(
                        quote_symbol,
                        amount
                    )
