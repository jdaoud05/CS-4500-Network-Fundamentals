#!/usr/bin/env -S python3 -u

import argparse, socket, json, select, sys

class Router:

    relations = {}
    sockets = {}
    ports = {}

    def __init__(self, asn, connections):
        print("Router at AS %s starting up" % asn)
        self.asn = asn
        self.updates = []
        self.withdrawals = []
        self.routes = []
        for relationship in connections:
            port, neighbor, relation = relationship.split("-")

            self.sockets[neighbor] = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sockets[neighbor].bind(('localhost', 0))
            self.ports[neighbor] = int(port)
            self.relations[neighbor] = relation
            
            # Sends handshake message
            self.send(neighbor, json.dumps({ "type": "handshake", "src": self.our_addr(neighbor), "dst": neighbor, "msg": {}  }))

# Takes oru IP address and asisgns the last integer to 1 , this is lowk redundant but leaving since send_data using it 
    def our_addr(self, dst):
        quads = list(int(qdn) for qdn in dst.split('.'))
        quads[3] = 1
        return "%d.%d.%d.%d" % (quads[0], quads[1], quads[2], quads[3])

    def send(self, network, message):
        self.sockets[network].sendto(message.encode('utf-8'), ('localhost', self.ports[network]))

    # Send update message to neighbor depending on received route
    def decide_send(self, neighbor, srcif):
        from_rel = self.relations[srcif]
        to_rel = self.relations[neighbor]

        if from_rel == 'cust':
            return True
        if from_rel == 'peer' or from_rel == 'prov':
            if to_rel == 'cust':
                return True
            else:
                return False

    # needed for ip_and and prefix matching... essentially a replacement for ip&
    def ip_to_int(self, ip):
        # converts dotted quad IP to 32-bit int for bitwise ops
        parts = [int(x) for x in ip.split('.')]
        return parts[0] << 24 | parts[1] << 16 | parts[2] << 8 | parts[3]

    def int_to_ip(self, n):
        # converts 32-bit int back to dotted quad
        return "%d.%d.%d.%d" % ((n >> 24) & 0xFF, (n >> 16) & 0xFF, (n >> 8) & 0xFF, n & 0xFF)

    def ip_and(self, dst_ip, netmask, network):
        # checks if dst_ip falls within the given network/netmask
        d = self.ip_to_int(dst_ip)
        mask = self.ip_to_int(netmask)
        net = self.ip_to_int(network)
        return (d & mask) == (net & mask)

    def netmask_length(self, netmask):
        # counts set bits in netmask used for lognest prefiecx   match
        n = self.ip_to_int(netmask)
        count = 0
        while n:
            count += n & 1
            n >>= 1
        return count

    def origin_rank(self, origin):
        # IGP > EGP > UNK
        return {'IGP': 0, 'EGP': 1, 'UNK': 2}.get(origin, 2)

    def best_route(self, matches):
        """
        tiebreak rules in order: localpref > selfOrigin > ASPath length > origin > lowest peer IP
        """
        def key(r):
            return (-r['localpref'], 0 if r['selfOrigin'] else 1, len(r['ASPath']), self.origin_rank(r['origin']), self.ip_to_int(r['peer']))
        return min(matches, key=key)

    def routes_aggregatable(self, r1, r2):
        # two routes can be aggregated if all attrs match and they are numerically adjacent at the same prefix length
        if r1['peer'] != r2['peer'] or r1['localpref'] != r2['localpref'] or r1['selfOrigin'] != r2['selfOrigin'] or r1['ASPath'] != r2['ASPath'] or r1['origin'] != r2['origin'] or r1['netmask'] != r2['netmask']:
            return False
        mask_len = self.netmask_length(r1['netmask'])
        if mask_len == 0:
            return False
        # build the supernet mask (one bit shorter)
        new_mask_int = ((1 << 32) - 1) ^ ((1 << (32 - (mask_len - 1))) - 1)
        n1, n2 = self.ip_to_int(r1['network']), self.ip_to_int(r2['network'])
        if (n1 & new_mask_int) != (n2 & new_mask_int):  # must be in same supernet
            return False
        if abs(n1 - n2) != (1 << (32 - mask_len)): # must differ by exactly one prefix-length block
            return False
        return True

    def aggregate_two(self, r1, r2):
        # merges two adjacent routes into their supernet, inheriting all attrs from r1
        mask_len = self.netmask_length(r1['netmask'])
        new_mask_int = ((1 << 32) - 1) ^ ((1 << (32 - (mask_len - 1))) - 1)
        return {**r1, 'netmask': self.int_to_ip(new_mask_int), 'network': self.int_to_ip(self.ip_to_int(r1['network']) & new_mask_int)}

    def aggregate(self, routes):
        # repeatedly merges aggregatable pairs until no more emregefks are posible
        changed = True
        while changed:
            changed = False
            new_routes = []
            used = [False] * len(routes)
            for i in range(len(routes)):
                if used[i]:
                    continue
                merged = False
                for j in range(i + 1, len(routes)):
                    if used[j]:
                        continue
                    if self.routes_aggregatable(routes[i], routes[j]):
                        new_routes.append(self.aggregate_two(routes[i], routes[j]))
                        used[i] = used[j] = True
                        merged = changed = True
                        break
                if not merged:
                    new_routes.append(routes[i])
            routes = new_routes
        return routes

    def rebuild_table(self):
        self.routes = []
        for (msg, srcif) in self.updates:
            inner = msg['msg']
            self.routes.append({**inner, 'peer': srcif})
        for (msg, srcif) in self.withdrawals:
            for entry in msg['msg']:
                self.routes = [r for r in self.routes if not (r['network'] == entry['network'] and r['netmask'] == entry['netmask'] and r['peer'] == srcif)]

    def send_update(self, message, srcif):
        # message is already a dict from run)
        self.updates.append((message, srcif))
        inner_msg = message["msg"]
        # 2. Add an entry to your forwarding table
        self.routes.append( {
            "network":inner_msg["network"],
            "netmask":inner_msg["netmask"],
            "localpref":inner_msg["localpref"],
            "selfOrigin":inner_msg["selfOrigin"],
            "ASPath":inner_msg["ASPath"],
            "origin":inner_msg["origin"],
            "peer":srcif
            } )

        self.routes = self.aggregate(self.routes)

        # 3. Send copies of the announcement to neighboring routers

        # For every node in sockets
        for neighbor in self.sockets:
            # If the neighbor does not equal the incoming connection (not sending back to)
            if neighbor != srcif:
                # And decide_send is true:
                if self.decide_send(neighbor, srcif):
                    # Send the update message to the neighbor
                    self.send(neighbor, json.dumps({ "type": "update", "src": self.our_addr(neighbor), "dst": neighbor, "msg": {"network": inner_msg["network"] , "netmask":inner_msg["netmask"], "ASPath": [self.asn] + inner_msg["ASPath"] } } ))
    def send_withdraw(self, message, srcif):
        self.withdrawals.append((message, srcif))
        self.rebuild_table()
        self.routes = self.aggregate(self.routes)
        for neighbor in self.sockets:
            if neighbor != srcif:
                if self.decide_send(neighbor, srcif):
                    self.send(neighbor, json.dumps({ "type": "withdraw", "src": self.our_addr(neighbor), "dst": neighbor, "msg": message['msg'] }))

    def send_data(self, message, srcif):
        dst_ip = message["dst"]
        # 1. Which route is the best route to use for the given dest IP

        # 2. Is the data packet being forwarded legally 

        matches = []
        for route in self.routes:
            # If the inteded IP address is in the same network as us, send
            if self.ip_and(dst_ip, route["netmask"] , route["network"]):
                matches.append(route)
        if not matches:
            self.send(srcif, json.dumps({"type": "no route", "src": self.our_addr(srcif), "dst": message['src'], "msg": {}}))
            return
        # longest prefix match then tie-break
        max_len = max(self.netmask_length(r['netmask']) for r in matches)
        matches = [r for r in matches if self.netmask_length(r['netmask']) == max_len]
        route = self.best_route(matches)
        if not self.can_forward_data(srcif, route): # drop if neither src nor dst is a cst
            self.send(srcif, json.dumps({"type": "no route", "src": self.our_addr(srcif), "dst": message['src'], "msg": {}}))
            return
        self.send(route['peer'], json.dumps(message))

    def can_forward_data(self, srcif, best_route):
        # legal forwarding: src or dst must be a cst
        if self.relations[srcif] == 'cust' or self.relations[best_route['peer']] == 'cust':
            return True
        return False

    def send_table(self, message, srcif):
        # responds to dump with aggregated forwarding table
        self.send(srcif, json.dumps({"type": "table", "src": self.our_addr(srcif), "dst": message['src'], "msg": self.aggregate(list(self.routes))}))
    def run(self):
        while True:
            socks = select.select(self.sockets.values(), [], [], 0.1)[0]
            for conn in socks:
                k, addr = conn.recvfrom(65535)
                srcif = None
                for sock in self.sockets:
                    if self.sockets[sock] == conn:
                        srcif = sock
                        break
                msg = json.loads(k.decode('utf-8'))
                msg_type = msg["type"]
                # IMPORTANT: dump first
                if msg_type == "dump":
                    self.send_table(msg, srcif)
                elif msg_type == "update":
                    self.send_update(msg, srcif)
                elif msg_type == "withdraw":
                    self.send_withdraw(msg, srcif)
                elif msg_type == "data":
                    self.send_data(msg, srcif)

if __name__ == "__main__": 
    parser = argparse.ArgumentParser(description='route packets')
    parser.add_argument('asn', type=int, help="AS number of this router")
    parser.add_argument('connections', metavar='connections', type=str, nargs='+', help="connections")
    args = parser.parse_args()
    router = Router(args.asn, args.connections)
    router.run()
    


