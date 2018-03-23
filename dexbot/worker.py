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

log_workers = logging.getLogger('dexbot.per_worker')
# NOTE this is the  special logger for per-worker events
# it returns LogRecords with extra fields: worker_name, account, market and is_disabled
# is_disabled is a callable returning True if the worker is currently disabled.
# GUIs can add a handler to this logger to get a stream of events of the running workers.


class WorkerInfrastructure(threading.Thread):

    workers = dict()

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
        
    def init_workers(self):
        """Do the actual initialisation of workers
        Potentially quite slow (tens of seconds)
        So called as part of run()
        """
        # set the module search path
        user_worker_path = os.path.expanduser("~/bots")
        if os.path.exists(user_worker_path):
            sys.path.append(user_worker_path)

        # Load all accounts and markets in use to subscribe to them
        accounts = set()
        markets = set()
        
        # Initialize workers:
        for worker_name, worker in self.config["workers"].items():
            if "account" not in worker:
                log_workers.critical("Worker has no account", extra={
                    'worker_name': worker_name, 'account': 'unknown',
                    'market': 'unknown', 'is_disabled': (lambda: True)
                })
                continue
            if "market" not in worker:
                log_workers.critical("Worker has no market", extra={
                    'worker_name': worker_name, 'account': worker['account'],
                    'market': 'unknown', 'is_disabled': (lambda: True)
                })
                continue
            try:
                strategy_class = getattr(
                    importlib.import_module(worker["module"]),
                    'Strategy'
                )
                self.workers[worker_name] = strategy_class(
                    config=self.config,
                    name=worker_name,
                    bitshares_instance=self.bitshares,
                    view=self.view
                )
                markets.add(worker['market'])
                accounts.add(worker['account'])
            except BaseException:
                log_workers.exception("Worker initialisation", extra={
                    'worker_name': worker_name, 'account': worker['account'],
                    'market': 'unknown', 'is_disabled': (lambda: True)
                })

        if len(markets) == 0:
            log.critical("No workers to launch, exiting")
            raise errors.NoWorkersAvailable()

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
        for worker_name, worker in self.config["workers"].items():
            if worker_name not in self.workers or self.workers[worker_name].disabled:
                continue
            try:
                self.workers[worker_name].ontick(data)
            except Exception as e:
                self.workers[worker_name].error_ontick(e)
                self.workers[worker_name].log.exception("in .tick()")

    def on_market(self, data):
        if data.get("deleted", False):  # No info available on deleted orders
            return
        for worker_name, worker in self.config["workers"].items():
            if self.workers[worker_name].disabled:
                self.workers[worker_name].log.debug('Worker "{}" is disabled'.format(worker_name))
                continue
            if worker["market"] == data.market:
                try:
                    self.workers[worker_name].onMarketUpdate(data)
                except Exception as e:
                    self.workers[worker_name].error_onMarketUpdate(e)
                    self.workers[worker_name].log.exception(".onMarketUpdate()")

    def on_account(self, account_update):
        account = account_update.account
        for worker_name, worker in self.config["workers"].items():
            if self.workers[worker_name].disabled:
                self.workers[worker_name].log.info('Worker "{}" is disabled'.format(worker_name))
                continue
            if worker["account"] == account["name"]:
                try:
                    self.workers[worker_name].onAccount(account_update)
                except Exception as e:
                    self.workers[worker_name].error_onAccount(e)
                    self.workers[worker_name].log.exception(".onAccountUpdate()")

    def run(self):
        self.init_workers()
        self.notify.listen()

    def stop(self):
        for worker in self.workers:
            self.workers[worker].cancel_all()
        self.notify.websocket.close()

    def remove_worker(self):
        for worker in self.workers:
            self.workers[worker].purge()

    @staticmethod
    def remove_offline_worker(config, worker_name):
        # Initialize the base strategy to get control over the data
        strategy = BaseStrategy(config, worker_name)
        strategy.purge()

    def do_next_tick(self, job):
        """Add a callable to be executed on the next tick"""
        self.jobs.add(job)
