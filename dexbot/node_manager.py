from websocket import create_connection as wss_create
from time import time
from itertools import repeat
import logging
import multiprocessing as mp
import subprocess
import platform


log = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s'
)

max_timeout = 2.0  # default ping time is set to 2s. use for internal testing.
host_ip = '1.1.1.1'  # default host to ping to check internet


def ping(host, network_timeout=3):
    """ Send a ping packet to the specified host, using the system "ping" command.
        Covers the Windows, Unix and OSX
    """
    args = ['ping']
    platform_os = platform.system().lower()
    if platform_os == 'windows':
        args.extend(['-n', '1'])
        args.extend(['-w', str(network_timeout * 1000)])
    elif platform_os in ('linux', 'darwin'):
        args.extend(['-c', '1'])
        args.extend(['-W', str(network_timeout)])
    else:
        raise NotImplementedError('Unsupported OS: {}'.format(platform_os))
    args.append(host)

    try:
        if platform_os == 'windows':
            output = subprocess.run(args, check=True, universal_newlines=True, shell=False).stdout
            if output and 'TTL' not in output:
                return False
        else:
            subprocess.run(args, check=True, shell=False)
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False


def wss_test(node, timeout):
    """ Test websocket connection to a node
    """
    try:
        start = time()
        wss_create(node, timeout=timeout)
        latency = (time() - start)
        return latency
    except Exception as e:
        log.info('websocket test: {}'.format(e))
        return None


def check_node(node, timeout):
    """ Check latency of an individual node
    """
    log.info('# pinging {}'.format(node))
    latency = wss_test(node, timeout)
    node_info = {'Node': node, 'Latency': latency}
    return node_info


def get_sorted_nodelist(nodelist, timeout):
    """ Check all nodes and poll for latency, eliminate nodes with no response, then sort
        nodes by increasing latency and return as a list
    """

    print('get_sorted_nodelist max timeout: {}'.format(timeout))
    pool_size = mp.cpu_count()*2

    with mp.Pool(processes=pool_size) as pool:
        latency_info = pool.starmap(check_node, zip(nodelist, repeat(timeout)))

    pool.close()
    pool.join()

    filtered_list = [i for i in latency_info if i['Latency'] is not None]
    sorted_list = sorted(filtered_list, key=lambda k: k['Latency'])
    sorted_nodes = [i['Node'] for i in sorted_list]
    return sorted_nodes
