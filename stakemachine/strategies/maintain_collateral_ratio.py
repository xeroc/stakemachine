from .basestrategy import BaseStrategy, MissingSettingsException
import logging
log = logging.getLogger(__name__)


class MaintainCollateralRatio(BaseStrategy):
    """ Maintain the collateral ration of a debt position

        This "strategy" takes the quote of the market and watches the
        collateral ratio of an existing debt position. If it passes the
        lower threshold, it will automatically try to reajust it back to
        the specified target.

        .. note:: You will receive a warning if the quote is the core
                  asset and the base is not the asset backing asset:

                  * USD:BTS - working
                  * BTS:USD - not working, wrong orientiation
                  * GOLD:SILVER - not working b/c SILVER is not backing asset
                  * MKR:BTS - not working because MKR is a UIA

        **Settings**:

         * **target_ratio**: target ratio to set on ajustments (should
                             be between lower and upper threshold)
         * **lower_threshold**: if the collateral ratio goes below this
                                point, an adjustment is initiated
         * **upper_threshold**: if the collateral ratio goes above this
                                point, an adjustment is initiated

        Only used if run in continuous mode (e.g. with ``run_conf.py``):

        * **skip_blocks**: Checks the collateral ratio only every x blocks

        .. code-block:: yaml

            Collateral:
                module: "stakemachine.strategies.maintain_collateral_ratio"
                bot: "MaintainCollateralRatio"
                markets:
                    - "USD:BTS"
                    - "SILVER:BTS"
                    - "GOLD:BTS"]
                target_ratio: 2.75
                lower_threshold: 2.5
                upper_threshold: 3.0
                skip_blocks: 1

    """

    block_counter = 0

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def init(self):
        """ Verify that the markets are against the assets
        """
        for m in self.settings["markets"]:
            quote_name, base_name = m.split(self.dex.market_separator)
            quote = self.dex.ws.get_asset(quote_name)
            base  = self.dex.ws.get_asset(base_name)
            if "bitasset_data_id" not in quote:
                raise ValueError(
                    "The quote asset %s is not a bitasset "
                    "and thus has no collateral to maintain!" % quote_name
                )
            collateral_asset_id = self.dex.getObject(
                quote["bitasset_data_id"]
            )["options"]["short_backing_asset"]
            assert collateral_asset_id == base["id"], Exception(
                "Collateral asset of %s doesn't match" % quote_name
            )

        """ After startup, execute one tick()
        """
        self.tick()

    def adjust_collateral(self, symbol):
        """ Actually adjust the collateral ratio
        """
        try:
            self.dex.adjust_debt(0, symbol, self.settings["target_ratio"])
        except ValueError as e:
            log.critical("Couldn't adjust collateral: %s" % str(e))

    def tick(self):
        """ We can check every block if the collateral ratio goes belos
            the lower threshold or above the upper threshold and
            initiate an adjustment
        """
        self.block_counter += 1
        if (self.block_counter % self.settings["skip_blocks"]) == 0:
            debts = self.dex.list_debt_positions()
            for m in self.settings["markets"]:
                quote_symbol = m.split(self.dex.market_separator)[0]
                log.debug("Checking %s collateral of %s" % (
                    quote_symbol, self.config.account)
                )
                if quote_symbol not in debts:
                    log.warn("[Warning] You don't have any %s debt" % quote_symbol)
                    continue
                debt = debts[quote_symbol]
                if (debt["ratio"] < self.settings["lower_threshold"] or
                        debt["ratio"] > self.settings["upper_threshold"]):
                    self.adjust_collateral(
                        quote_symbol
                    )
