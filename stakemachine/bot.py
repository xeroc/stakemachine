from grapheneapi.graphenewsprotocol import GrapheneWebsocketProtocol
from grapheneexchange import GrapheneExchange
import time
import importlib

config = None
bots = {}
dex = None


class BotProtocol(GrapheneWebsocketProtocol):
    """ Bot Protocol to interface with websocket notifications and
        forward notices to the bots
    """

    def onAccountUpdate(self, data):
        """ If the account updates, reload every market
        """
        print("Account Update! Notifying bots: ", end="")
        for name in bots:
            print("%s " % name, end="")
            bots[name].loadMarket(notify=True)
            bots[name].store()
        print()

    def onMarketUpdate(self, data):
        """ If a Market updates upgrades, reload every market
        """
        print("Market Update! Notifying bots: ", end="")
        for name in bots:
            print("%s " % name, end="")
            bots[name].loadMarket(notify=True)
            bots[name].store()
        print()

    def onBlock(self, data) :
        """ Every block let the bots know via ``tick()``
        """
        for name in bots:
            bots[name].loadMarket(notify=True)
            bots[name].tick()
            bots[name].store()

    def onRegisterDatabase(self):
        print("Websocket successfully initialized!")


def init(conf, **kwargs):
    """ Initialize the Bot Infrastructure and setup connection to the
        network
    """
    global dex, bots, config

    config = BotProtocol

    # Take the configuration variables and put them in the current
    # instance of BotProtocol. This step is required to let
    # GrapheneExchange know most of our variables as well!
    # We will also be able to hook into websocket messages from
    # within the configuration file!
    [setattr(config, key, conf[key]) for key in conf.keys()]

    if not hasattr(config, "prefix") or not config.prefix:
        config.prefix = "BTS"

    # Construct watch_markets attribute from all bots:
    watch_markets = set()
    for name in config.bots:
        watch_markets = watch_markets.union(config.bots[name]["markets"])
    watch_markets = (watch_markets)
    setattr(config, "watch_markets", watch_markets)

    # Connect to the DEX
    dex    = GrapheneExchange(config,
                              safe_mode=config.safe_mode,
                              prefix=config.prefix)

    # Initialize all bots
    for index, name in enumerate(config.bots, 1):
        if "module" not in config.bots[name]:
            raise ValueError("No 'module' defined for bot %s" % name)
        klass = getattr(
            importlib.import_module(config.bots[name]["module"]),
            config.bots[name]["bot"]
        )
        bots[name] = klass(config=config, name=name,
                           dex=dex, index=index)
        # Maybe the strategy/bot has some additional customized
        # initialized besides the basestrategy's __init__()
        bots[name].loadMarket(notify=False)
        bots[name].init()
        bots[name].store()


def wait_block():
    """ This is sooo dirty! FIXIT!
    """
    time.sleep(6)


def cancel_all():
    """ Cancel all orders of all markets that are served by the bots
    """
    for name in bots:
        bots[name].loadMarket(notify=False)
        bots[name].cancel_this_markets()
        bots[name].store()


def once():
    """ Execute the core unit of the bot
    """
    for name in bots:
        print("Executing bot %s" % name)
        bots[name].loadMarket(notify=True)
        bots[name].place()
        bots[name].store()


def run():
    """ This call will run the bot in **continous mode** and make it
        receive notification from the network
    """
    dex.run()
