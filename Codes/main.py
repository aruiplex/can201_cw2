import argparse
import json
import queue
import socket
import threading
import time
import os.path
import queue

"""
Router exchange distance algorithm
"""

timeout = 10
msg_queue = queue.Queue()
IP = '127.0.0.1'


def pass_arg():
    """pass arguments to start application
    """
    args = argparse.ArgumentParser()
    args.add_argument('--node', action='store', dest='node')
    ans = args.parse_args()
    return ans


def json_reader(node: str, endwith: str):
    """read json format file
    """
    with open(node + endwith, "r") as f:
        json_dict = json.loads(f.read())
    return json_dict


def update_node_info(node: str, s: socket, peers: [], peer_ports: {}, dvt: {}):
    """updatea node data 
    """
    msg = {node: dvt}
    msg_json = json.dumps(msg)
    msg_json = msg_json.encode()
    for n in peers:
        print(f'send to {n}\n')
        s.sendto(msg_json, (IP, peer_ports[n][1]))


def presist_output_info(node, local_dv_table):
    """persist output distance info to file
    """
    with open(node + '_output.json', 'w') as file_:
        file_.write(json.dumps(local_dv_table, indent=2))


def packup_d_v(dst, nh):
    """distance value to format
    """
    return {'distance': dst, 'next_hop': nh}


def get_peer_dv(s):
    """recv peer info by udp
    """
    while True:
        try:
            message, addr = s.recvfrom(10240)
            msg_queue.put(message)
        except (socket.timeout, OSError):
            print('Done')
            s.close()
            break
    exit(0)


def init_node(node: str, lnd: {}, np: {}, s):
    """when start up, initialize node  
    """
    peers = list(lnd.keys())
    ond = {}
    ldvt = {}

    for n in peers:
        ond[n] = lnd[n]
    for n in lnd:
        ldvt[n] = packup_d_v(lnd[n], n)
    time.sleep(5)
    update_node_info(node, s, peers, np, ldvt)
    return ldvt, peers, ond


def router(node: {}, lnd: {}, node_ports: {}, s):
    err_cnt = 0
    local_distance_value_table, peers, ond = init_node(
        node, lnd, node_ports, s)
    while True:
        msg = None
        try:
            print(f'[Rounds]: {err_cnt}')
            msg = msg_queue.get(block=False)
        except queue.Empty:
            print('<Waiting>')
            err_cnt = err_cnt + 1
            time.sleep(1)
            if err_cnt > 6:
                s.close()
                presist_output_info(node, local_distance_value_table)
                break

        if msg is not None:
            msg_dir = json.loads(msg)
            node_from = list(msg_dir.keys())[0]
            dv_table_received = msg_dir[node_from]
            print(f'From <{node_from}> get {dv_table_received}')
            updated = False

            for n, d_dic in dv_table_received.items():
                ds = local_distance_value_table[node_from]['distance']

                if n not in local_distance_value_table:
                    if node != n:
                        updated = True
                        local_distance_value_table[n] = packup_d_v(
                            ds + d_dic['distance'], node_from)

                else:
                    if local_distance_value_table[n]['distance'] > ds + d_dic['distance']:
                        updated = True
                        local_distance_value_table[n]['distance'] = ds + \
                            d_dic['distance']

                        if ds == ond[node_from]:
                            local_distance_value_table[n]['next_hop'] = node_from

                        else:
                            local_distance_value_table[n]['next_hop'] = local_distance_value_table[node_from]['next_hop']
            if updated:
                update_node_info(node, s, peers, node_ports,
                                 local_distance_value_table)
    exit(0)


def main():
    parser = pass_arg()
    node = parser.node
    print(f'Node <{node}>')
    node_ds = json_reader(node, "_distance.json")
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    node_pt = json_reader(node, "_ip.json")
    s.bind((IP, node_pt[node][1]))
    threads = []
    s.settimeout(timeout)
    route_thread = threading.Thread(
        target=router, args=(node, node_ds, node_pt, s))
    threads.append(route_thread)
    receiving_thread = threading.Thread(target=get_peer_dv, args=(s,))
    threads.append(receiving_thread)
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    print(f'<{node} complete>')


if __name__ == '__main__':
    main()
