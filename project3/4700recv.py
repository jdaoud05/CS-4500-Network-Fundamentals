#!/usr/bin/env -S python3 -u
import argparse, socket, time, json, select, sys, hashlib

def checksum(data):
    return hashlib.md5(data.encode()).hexdigest()

class Receiver:
    def __init__(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind(('0.0.0.0', 0))
        self.port = self.socket.getsockname()[1]
        self.log("Bound to port %d" % self.port)

        self.remote_host = None
        self.remote_port = None
        self.next_seq = 0
        self.buffer = {}

    def log(self, message):
        sys.stderr.write(message + "\n")
        sys.stderr.flush()

    def send_ack(self, seq):
        cs = checksum(str(seq))
        msg = {"type": "ack", "seq": seq, "checksum": cs}
        self.socket.sendto(json.dumps(msg).encode("utf-8"), (self.remote_host, self.remote_port))
        self.log("Sent ACK seq=%d" % seq)

    def validate_packet(self, msg):
        return checksum(msg["data"]) == msg.get("checksum", "")

    def run(self):
        while True:
            socks = select.select([self.socket], [], [])[0]
            for conn in socks:
                try:
                    raw, addr = conn.recvfrom(65535)
                except Exception as e:
                    self.log("Socket error: %s" % e)
                    continue

                if self.remote_host is None:
                    self.remote_host = addr[0]
                    self.remote_port = addr[1]
                if addr != (self.remote_host, self.remote_port):
                    continue

                try:
                    msg = json.loads(raw.decode("utf-8"))
                except Exception as e:
                    self.log("Error parsing packet: %s" % e)
                    continue

                if msg.get("type") != "msg":
                    continue

                seq = msg.get("seq")
                
                if seq is None:
                    continue
                # validate the packet before doing anything with it. corrupted?, log it and move on without acking.

                self.log("Received packet seq=%d" % seq)
                
                if not self.validate_packet(msg):
                    continue 
                self.send_ack(seq)

                if seq < self.next_seq or seq in self.buffer:
                    self.log("Duplicate seq=%d, ignoring" % seq)
                    continue

                self.buffer[seq] = msg["data"]

                while self.next_seq in self.buffer:
                    print(self.buffer.pop(self.next_seq), end='', flush=True)
                    self.log("Printed seq=%d" % self.next_seq)
                    self.next_seq += 1

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='receive data')
    args = parser.parse_args()
    Receiver().run()