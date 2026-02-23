#!/usr/bin/env -S python3 -u

import argparse, socket, time, json, select, struct, sys, math

from run import router

class Router:

    relations = {}
    sockets = {}
    ports = {}

    def __init__(self, asn, connections):
        print("Router at AS %s starting up" % asn)
        self.asn = asn
        for relationship in connections:
            port, neighbor, relation = relationship.split("-")

            self.sockets[neighbor] = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sockets[neighbor].bind(('localhost', 0))
            self.ports[neighbor] = int(port)
            self.relations[neighbor] = relation
            self.routes = []
            
            # Sends handshake message
            self.send(neighbor, json.dumps({ "type": "handshake", "src": self.our_addr(neighbor), "dst": neighbor, "msg": {}  }))

# Takes oru IP address and asisgns the last integer to 1
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

    def send_update(self, message, srcif):
        # 1. Save a copy of the announcement
        parsed = json.loads(message)


        inner_msg = parsed["msg"]
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


        # 3. Send copies of the announcement to neighboring routers

        # For every node in sockets
        for neighbor in self.sockets:
            # If the neighbor does not equal the incoming connection (not sending back to)
            if neighbor != srcif:
                # And decide_send is true:
                if self.decide_send(neighbor, srcif):
                    # Send the update message to the neighbor
                    self.send(neighbor, json.dumps({ "type": "update", "src": self.our_addr(neighbor), "dst": neighbor, "msg": {"network": inner_msg["network"] }, "netmask":inner_msg["netmask"], "ASPath": [self.asn] + inner_msg["ASPath"] } ))
    
    def send_withdraw(self, message, srcif):
        parsed = json.loads(message)
        inner_msg = parsed["msg"]

        for entry in inner_msg:
            self.routes = [route for route in self.routes
                            if not (route["network"] == entry["network"]
                            and route["netmask"] == entry["netmask"]
                            and route["peer"] == srcif)]

        for neighbor in self.sockets:
            if neighbor != srcif:
                if self.decide_send(neighbor, srcif):
                    self.send(neighbor, json.dumps({ "type": "withdraw", "src": self.our_addr(neighbor), "dst": neighbor, "msg": inner_msg }))
        return

    def send_data(self, message, srcif):
        parsed = json.loads(message)
        dst_ip = parsed["dst"]
        
        # 1. Which route is the best route to use for the given dest IP
        
        # 2. Is the data packet being forwarded legally 

        matches = []
        for route in self.routes:
            # If the inteded IP address is in the same network as us, send
            if ip_and(dst_ip, route["netmask"] , route["network"]):
                matches.append(route)
        if len(matches) == 0:                
            self.send(srcif, json.dumps({ "type":"no route", "src":self.our_addr(srcif), "dst":srcif, "msg": {} }))
        if len(matches) == 1:
        return

    def ip_and(self, dst_ip, netmask, network):
        bit_dst_ip = [int(x) for x in dst_ip.split('.')]
        saved_bit_dst_ip = bit_dst_ip[0] << 24 | bit_dst_ip[1] << 16 | bit_dst_ip[2] << 8 | bit_dst_ip[3]
        
        bit_netmask = [int(x) for x in netmask.split('.')]
        saved_bit_netmask = bit_netmask[0] << 24 | bit_netmask[1] << 16 | bit_netmask[2] << 8 | bit_netmask[3]

        bit_network = [int(x) for x in network.split('.')]
        saved_bit_network = bit_network[0] << 24 | bit_network[1] << 16 | bit_network[2] << 8 | bit_network[3]


        if saved_bit_dst_ip & saved_bit_netmask == saved_bit_network & saved_bit_netmask:
            return True
        else:
            return False
    

        # if dest_ip & netmask = route add it tgo matches
        # def send_table(self, message, srcif):

        #     for neighbor in self.sockets:
        #         if neighbor != srcif:
        #             if self.decide_send(self, neighbor, srcif):
        #                 self.send(neighbor, json.dumps({ "type": "table", "src": self.our_addr(neighbor), "dst": neighbor, "msg": <network.in.quad.notation>", "netmask" : "<netmask.in.quad.notation>", "peer" : "<peer-ip.in.quad.notation>", "localpref": pref, "ASPath": [path, of, ASes], "selfOrigin": trueorfalse, "origin": "EGP-IGP-UNK" }}))
                    
        #     return
    def return_route(self, message, srcif):
        parsed = json.loads(message)
        msg_type = parsed["type"]

        if msg_type == "update":
            self.send_update(srcif)
        if msg_type == "withdraw":
            self.send_withdraw(srcif)
        # if msg_type == "dump":
        #     self.send_table(srcif)
            
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
                message = k.decode('utf-8')
                parsed = json.loads(message)
                inner_msg = parsed["msg"]
                network = inner_msg["network"]
                #  self.return_route(msg, srcif)
                print(f"MESSAGE: {message}")
                print(f"INCOMING: {srcif}")
                print(f"INNERMSG: {inner_msg}")
                print(f"NETWORK: {network}")

                print("Received message '%s' from %s" % (message, srcif))
                
        return

if __name__ == "__main__": 
    parser = argparse.ArgumentParser(description='route packets')
    parser.add_argument('asn', type=int, help="AS number of this router")
    parser.add_argument('connections', metavar='connections', type=str, nargs='+', help="connections")
    args = parser.parse_args()
    router = Router(args.asn, args.connections)
    router.run()
    


