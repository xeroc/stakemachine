import re
from urllib.parse import urlsplit
from subprocess import Popen, STDOUT, PIPE
from platform import system


"""
Routines for finding the closest node
"""

# list kindly provided by Cryptick from the DEXBot Telegram channel
ALL_NODES = ["wss://eu.openledger.info/ws",
             "wss://bitshares.openledger.info/ws",
             "wss://dexnode.net/ws",
             "wss://japan.bitshares.apasia.tech/ws",
             "wss://bitshares-api.wancloud.io/ws",
             "wss://openledger.hk/ws",
             "wss://bitshares.apasia.tech/ws",
             "wss://bitshares.crypto.fans/ws",
             "wss://kc-us-dex.xeldal.com/ws",
             "wss://api.bts.blckchnd.com",
             "wss://btsza.co.za:8091/ws",
             "wss://bitshares.dacplay.org/ws",
             "wss://bit.btsabc.org/ws",
             "wss://bts.ai.la/ws",
             "wss://ws.gdex.top"]

FAILED_PING_AMOUNT = 1000000

if system() == 'Windows':
    ping_re = re.compile(r'Average = ([\d.]+)ms')
else:
    ping_re = re.compile(r'min/avg/max/mdev = [\d.]+/([\d.]+)')


def ping_cmd(x):
    if system() == 'Windows':
        return 'ping', '-n', '5', '-w', '1500', x
    else:
        return 'ping', '-c5', '-n', '-w5', '-i0.3', x


def make_ping_proc(host):
    host = urlsplit(host).netloc.split(':')[0]
    return Popen(ping_cmd(host), stdout=PIPE, stderr=STDOUT, universal_newlines=True)


def process_ping_result(host, proc):
    out = proc.communicate()[0]
    try:
        return float(ping_re.search(out).group(1)), host
    except AttributeError:
        return FAILED_PING_AMOUNT, host  # Hosts that fail are last


def start_pings():
    return [(i, make_ping_proc(i)) for i in ALL_NODES]


def best_node(results=start_pings()):
    try:
        r = sorted([process_ping_result(*i) for i in results])
        return r[0][1]
    except BaseException:
        return None


def is_host_online(host):
    result = make_ping_proc(host)
    ping = process_ping_result(host, result)[0]
    if ping >= FAILED_PING_AMOUNT:
        return False
    return True


if __name__ == '__main__':
    print(best_node())
