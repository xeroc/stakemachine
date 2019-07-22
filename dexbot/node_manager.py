from websocket import create_connection as wss_create
from time import time

import multiprocessing as mp
import pandas as pd

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
        # print(e) # suppress errors
        return None


def check_node(node):
    """
    check latency of an individual node
    """
    print('#', end='', flush=True)
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

    df_nodes = pd.DataFrame(latency_info)
    df_active = df_nodes.dropna()
    df_sorted = df_active.sort_values('Latency', ascending=True)

    sorted_nodes = df_sorted.Node.tolist()
    return sorted_nodes
