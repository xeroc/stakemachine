#!/usr/bin/python3

from bitshares.bitshares import BitShares
import unittest
import time
import os
import threading
import logging
from dexbot.bot import BotInfrastructure


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s'
)


TEST_CONFIG = {
    'node': 'wss://node.testnet.bitshares.eu',
    'bots': {
        'echo':
        {
            'account': 'aud.bot.test4',
            'market': 'TESTUSD:TEST',
            'module': 'dexbot.strategies.echo'
        },
        'follow_orders':
        {
            'account': 'aud.bot.test4',
            'market': 'TESTUSD:TEST',
            'module': 'dexbot.strategies.follow_orders',
            'spread': 5,
            'reset': True,
            'staggers': 2,
            'wall_percent': 5,
            'staggerspread': 5,
            'min': 0,
            'max': 100000,
            'start': 50,
            'bias': 1
        }}}

# user need sto put a key in
KEYS = [os.environ['DEXBOT_TEST_WIF']]


class TestDexbot(unittest.TestCase):

    def test_dexbot(self):
        bitshares_instance = BitShares(node=TEST_CONFIG['node'], keys=KEYS)
        bot_infrastructure = BotInfrastructure(config=TEST_CONFIG,
                                               bitshares_instance=bitshares_instance)

        def wait_then_stop():
            time.sleep(20)
            bot_infrastructure.do_next_tick(bot_infrastructure.stop)

        stopper = threading.Thread(target=wait_then_stop)
        stopper.start()
        bot_infrastructure.run()
        stopper.join()


if __name__ == '__main__':
    unittest.main()
