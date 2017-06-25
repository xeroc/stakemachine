import importlib
import time
import logging
from bitshares.notify import Notify
from bitshares.instance import shared_bitshares_instance
log = logging.getLogger(__name__)


class BotInfrastructure():

    bots = dict()

    def __init__(
        self,
        config,
        bitshares_instance=None,
    ):
        # BitShares instance
        self.bitshares = bitshares_instance or shared_bitshares_instance()

        self.config = config

        # Load all accounts and markets in use to subscribe to them
        accounts = set()
        markets = set()
        for botname, bot in config["bots"].items():
            if "account" not in bot:
                raise ValueError("Bot %s has no account" % botname)
            if "market" not in bot:
                raise ValueError("Bot %s has no market" % botname)

            accounts.add(bot["account"])
            markets.add(bot["market"])

        # Create notification instance
        # Technically, this will multiplex markets and accounts and
        # we need to demultiplex the events after we have received them
        self.notify = Notify(
            markets=markets,
            accounts=accounts,
            on_market=self.on_market,
            on_account=self.on_account,
            on_block=self.on_block,
            bitshares_instance=self.bitshares
        )

        # Initialize bots:
        for botname, bot in config["bots"].items():
            klass = getattr(
                importlib.import_module(bot["module"]),
                bot["bot"]
            )
            self.bots[botname] = klass(
                config=config,
                name=botname,
                bitshares_instance=self.bitshares
            )

    # Events
    def on_block(self, data):
        for botname, bot in self.config["bots"].items():
            self.bots[botname].ontick(data)

    def on_market(self, data):
        for botname, bot in self.config["bots"].items():
            if bot["market"] == data.market:
                self.bots[botname].onMarketUpdate(data)

    def on_account(self, data):
        pass

    def run(self):
        self.notify.listen()
