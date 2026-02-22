#!/usr/bin/env -S python3 -u

import argparse, socket, time, json, select, struct, sys, math

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
                    self.send(neighbor, json.dumps({ "type": "update", "src": self.our_addr(neighbor), "dst": neighbor, "msg": {"network": inner_msg["network"] }, "netmask":inner_msg["netmask"], "ASPath": inner_msg["ASPath"] }))
    

def send_table(self, message, srcif):
    parsed = json.loads(message)

    inner_msg = parsed["msg"]

    for neighbor in self.sockets:
        if neighbor != srcif:
            if self.decide_send(self, neighbor, srcif):
                self.send(neighbor, json.dumps({ "type": "table", "src": self.our_addr(neighbor), "dst": neighbor, "msg": {"network": inner_msg["network"], "netmask": inner_msg["netmask"], "peer":inner_msg["peer"], "localpref": inner_msg["localpref"], "selfOrigin": inner_msg["selfOrigin"], "origin": inner_msg["origin"], "selfOrigin": inner_msg["selfOrigin"]}  }))
            
    return
    # def return_route(self, message, srcif):
    #     parsed = json.loads(message)
    #     msg_type = parsed["type"]

    #     if msg_type == "update":
    #         self.send_update(srcif)
    #     if msg_type == "withdraw":
    #         self.send_withdraw(srcif)
    #     if msg_type == "dump":
    #         self.send_table(srcif)
        
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
    


