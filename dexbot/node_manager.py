#!/usr/bin/env python3
from websocket import create_connection as wss_create
from time import time
import logging
import multiprocessing as mp

log = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s'
)

max_timeout = 2.0 # max ping time is set to 2

def wss_test(node):
    """
    Test websocket connection to a node
    """
    try:
        start = time()
        rpc = wss_create(node, timeout=max_timeout)
        latency = (time() - start)
        return latency
    except Exception as e:
        # suppress errors
        return None


def check_node(node):
    """
    check latency of an individual node
    """
    log.info(f'# pinging {node}')
    latency = wss_test(node)
    node_info = {'Node': node, 'Latency': latency}
    return node_info


def get_sorted_nodelist(nodelist):
    """
    check all nodes and poll for latency, 
    eliminate nodes with no response, then sort  
    nodes by increasing latency and return as a list
    """
    pool_size = mp.cpu_count()*2

    with mp.Pool(processes=pool_size) as pool:
        latency_info = pool.map(check_node, nodelist)

    pool.close()
    pool.join()

    filtered_list = [i for i in latency_info if i['Latency'] is not None]             
    sorted_list = sorted(filtered_list, key=lambda k: k['Latency'])
    sorted_nodes = [i['Node'] for i in sorted_list]
    
    return sorted_nodes
