import importlib
import sys
import logging
import os.path
import threading

from dexbot.basestrategy import BaseStrategy

from bitshares.notify import Notify
from bitshares.instance import shared_bitshares_instance

import dexbot.errors as errors

log = logging.getLogger(__name__)

log_bots = logging.getLogger('dexbot.per_bot')
# NOTE this is the  special logger for per-bot events
# it  returns LogRecords with extra fields: botname, account, market and is_disabled
# is_disabled is a callable returning True if the bot is currently disabled.
# GUIs can add a handler to this logger to get a stream of events re the running bots.


class BotInfrastructure(threading.Thread):

    bots = dict()

    def __init__(
        self,
        config,
        bitshares_instance=None,
        view=None
    ):
        super().__init__()

        # BitShares instance
        self.bitshares = bitshares_instance or shared_bitshares_instance()
        self.config = config
        self.view = view
        self.jobs = set()
        self.notify = None
        
    def init_bots(self):
        """Do the actual initialisation of bots
        Potentially quite slow (tens of seconds)
        So called as part of run()
        """
        # set the module search path
        user_bot_path = os.path.expanduser("~/bots")
        if os.path.exists(user_bot_path):
            sys.path.append(user_bot_path)

        # Load all accounts and markets in use to subscribe to them
        accounts = set()
        markets = set()
        
        # Initialize bots:
        for botname, bot in self.config["bots"].items():
            if "account" not in bot:
                log_bots.critical("Bot has no account", extra={
                    'botname': botname, 'account': 'unknown', 'market': 'unknown', 'is_disabled': (lambda: True)
                })
                continue
            if "market" not in bot:
                log_bots.critical("Bot has no market", extra={
                    'botname': botname, 'account': bot['account'], 'market': 'unknown', 'is_disabled': (lambda: True)
                })
                continue
            try:
                klass = getattr(
                    importlib.import_module(bot["module"]),
                    'Strategy'
                )
                self.bots[botname] = klass(
                    config=self.config,
                    name=botname,
                    bitshares_instance=self.bitshares,
                    view=self.view
                )
                markets.add(bot['market'])
                accounts.add(bot['account'])
            except BaseException:
                log_bots.exception("Bot initialisation", extra={
                    'botname': botname, 'account': bot['account'], 'market': 'unknown', 'is_disabled': (lambda: True)
                })

        if len(markets) == 0:
            log.critical("No bots to launch, exiting")
            raise errors.NoBotsAvailable()

        # Create notification instance
        # Technically, this will multiplex markets and accounts and
        # we need to demultiplex the events after we have received them
        self.notify = Notify(
            markets=list(markets),
            accounts=list(accounts),
            on_market=self.on_market,
            on_account=self.on_account,
            on_block=self.on_block,
            bitshares_instance=self.bitshares
        )

    # Events
    def on_block(self, data):
        if self.jobs:
            try: 
                for job in self.jobs:
                    job()
            finally:
                self.jobs = set()
        for botname, bot in self.config["bots"].items():
            if botname not in self.bots or self.bots[botname].disabled:
                continue
            try:
                self.bots[botname].ontick(data)
            except Exception as e:
                self.bots[botname].error_ontick(e)
                self.bots[botname].log.exception("in .tick()")

    def on_market(self, data):
        if data.get("deleted", False):  # No info available on deleted orders
            return
        for botname, bot in self.config["bots"].items():
            if self.bots[botname].disabled:
                self.bots[botname].log.debug('Worker "{}" is disabled'.format(botname))
                continue
            if bot["market"] == data.market:
                try:
                    self.bots[botname].onMarketUpdate(data)
                except Exception as e:
                    self.bots[botname].error_onMarketUpdate(e)
                    self.bots[botname].log.exception(".onMarketUpdate()")

    def on_account(self, accountupdate):
        account = accountupdate.account
        for botname, bot in self.config["bots"].items():
            if self.bots[botname].disabled:
                self.bots[botname].log.info('Worker "{}" is disabled'.format(botname))
                continue
            if bot["account"] == account["name"]:
                try:
                    self.bots[botname].onAccount(accountupdate)
                except Exception as e:
                    self.bots[botname].error_onAccount(e)
                    self.bots[botname].log.exception(".onAccountUpdate()")

    def run(self):
        self.init_bots()
        self.notify.listen()

    def stop(self):
        for bot in self.bots:
            self.bots[bot].cancel_all()
        self.notify.websocket.close()

    def remove_bot(self):
        for bot in self.bots:
            self.bots[bot].purge()

    @staticmethod
    def remove_offline_bot(config, bot_name):
        # Initialize the base strategy to get control over the data
        strategy = BaseStrategy(config, bot_name)
        strategy.purge()

    def do_next_tick(self, job):
        """Add a callable to be executed on the next tick"""
        self.jobs.add(job)
