#!/usr/bin/env -S python3 -u
import argparse, socket, time, json, select, sys, hashlib

DATA_SIZE = 1400

def checksum(data):
    return hashlib.md5(data.encode()).hexdigest()

class Sender:
    def __init__(self, host, port):
        self.host = host
        self.port = int(port)
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind(('0.0.0.0', 0))
        self.log("Sender starting up using port %s" % self.port)

        self.window = {}
        self.next_seq = 0
        self.base = 0
        self.cwnd = 2
        self.ssthresh = 16
        self.eof = False

        self.rtt_estimate = 1.0
        self.rtt_dev = 0.5
        self.timeout = 2.0

        self.remote_host = None
        self.remote_port = None

    def log(self, message):
        sys.stderr.write(message + "\n")
        sys.stderr.flush()

    def send_packet(self, msg):
        self.socket.sendto(json.dumps(msg).encode("utf-8"), (self.host, self.port))
        self.log("Sending packet seq=%d" % msg["seq"])

    def update_rtt(self, sample):
        alpha = 0.125
        beta = 0.25
        self.rtt_dev = (1 - beta) * self.rtt_dev + beta * abs(sample - self.rtt_estimate)
        self.rtt_estimate = (1 - alpha) * self.rtt_estimate + alpha * sample
        self.timeout = max(0.5, self.rtt_estimate + 4 * self.rtt_dev)
        self.log("RTT estimate=%.3f dev=%.3f timeout=%.3f" % (self.rtt_estimate, self.rtt_dev, self.timeout))

    def handle_ack(self, ack):
     
        seq = ack["seq"]
        if seq in self.window and not self.window[seq]["acked"]:
            rtt = time.time() - self.window[seq]["sent_at"]
            self.window[seq]["acked"] = True
            if self.window[seq]["retransmits"] == 0:
                self.update_rtt(rtt)
            if self.cwnd < self.ssthresh:
                self.cwnd += 1
            else:
                self.cwnd += 1/self.cwnd
            self.cwnd = min(self.cwnd, 64)
            if seq is None:
                print("NO SEQ")
        
        # If the ACK is for an unacked packet in the window // record the RTT (only if this packet was never retransmitted) and mark it as acked.
        #  -> update the congestion window accordingly.
    def validate_packet(self, ack):
        return ack.get("checksum") == checksum(str(ack["seq"]))

    def retransmit_timed_out(self):
        for s, v in list(self.window.items()):
            if v["acked"] == False:
                if (time.time() - v["sent_at"]) > self.timeout:
                    v["sent_at"] = time.time()
                    v["retransmits"] += 1
                    self.send_packet(v["msg"])
                    self.ssthresh = max(self.cwnd / 2, 2)
                    self.cwnd = self.ssthresh    

              

    def run(self):
        while True:
            # Packets that are "in flight" not yet acked but in the window
            in_flight = len([s for s, v in self.window.items() if not v["acked"]])
            can_send = int(self.cwnd) - in_flight

            if can_send > 0 and not self.eof:
                data = sys.stdin.read(DATA_SIZE)
                if len(data) == 0:
                    self.eof = True
                    self.log("Reached EOF on stdin")
                else:
                    seq = self.next_seq
                    self.next_seq += 1
                    msg = {"type": "msg", "seq": seq, "data": data, "checksum": checksum(data)}
                    self.window[seq] = {"msg": msg, "sent_at": time.time(), "acked": False, "retransmits": 0}
                    self.send_packet(msg)
                    can_send -= 1

            socks = select.select([self.socket], [], [], 0.01)[0]
            for conn in socks:
                try:
                    raw, addr = conn.recvfrom(65535)
                    if self.remote_host is None:
                        self.remote_host = addr[0]
                        self.remote_port = addr[1]
                    if addr != (self.remote_host, self.remote_port):
                        continue
                    ack = json.loads(raw.decode("utf-8"))
                    self.log("Received ACK %s" % ack)
                except Exception as e:
                    self.log("Error parsing ACK: %s" % e)
                    continue
                if ack.get("type") != "ack":
                    continue
                if not self.validate_packet(ack):
                     continue
                self.handle_ack(ack)

            while self.base in self.window and self.window[self.base]["acked"]:
                del self.window[self.base]
                self.base += 1

            self.retransmit_timed_out()

            if self.eof and len(self.window) == 0:
                self.log("All done!")
                sys.exit(0)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='send data')
    parser.add_argument('host', type=str, help="Remote host to connect to")
    parser.add_argument('port', type=int, help="UDP port number to connect to")
    args = parser.parse_args()
    Sender(args.host, args.port).run()