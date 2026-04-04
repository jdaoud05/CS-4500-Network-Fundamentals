#!/usr/bin/env python3

import argparse
import socket

DEFAULT_SERVER = "fakebook.khoury.northeastern.edu"
DEFAULT_PORT = 443

class Crawler:
    def __init__(self, args):
        self.server = args.server
        self.port = args.port
        self.username = args.username
        self.password = args.password

        self.socket = None
        self.cookies = {}
        self.frontier = []
        self.visited = set()
        self.flags = []
    
    def connect(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((self.server, self.port))

    def scrape(self, html):
        html = 

    def get_request(self, path, host):
        request = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {host}\r\n"
            f"Connection: keep-alive\r\n"
            f"\r\n"
        )
        self.socket.send(request.encode('ascii'))
        return request

    def post_request(self, path, host, token, username, password):
        body = f"username={username}&password={password}&csrfmiddlewaretoken={token}&next=%2Ffakebook%2F"
        request = (
            f"POST {path} HTTP/1.1\r\n"
            f"Host: {host}\r\n"
            f"Content-Type: application/x-www-form-urlencoded\r\n"
            f"Content-Length: {len(body)}\r\n"
            f"Cookie: csrftoken={token}\r\n"
            f"Connection: keep-alive\r\n\r\n"
            f"{body}"
        )
        self.socket.send(request.encode('ascii'))
        return request
        
    def receive_response(self):
        response = b""
        done = False
        while True:
            data = self.socket.recv(1000)

            response += data
            if "\r\n\r\n" in response.decode():
                line = response.decode().split("\r\n")
                body = response.decode().split("\r\n\r\n")[1]
            
                print(f"DATA {data}")
                for l in line:
                    if "Content-Length" in l:
                        length = int(l.split(":")[1])
                        if length == len(body):
                            done = True
                    if "Transfer-Encoding" in l:
                        if "0\r\n\r\n" in body:
                            done = True
                if done:
                    break
    
    def run(self):
        request = "GET / HTTP/1.0\r\n\r\n"

        print("Request to %s:%d" % (self.server, self.port))
        print(request)

        self.connect()
        
        data = self.receive_response()

        if len(data) == 0:
            print("Response:\nSocket closed by %s" % self.server)
        else:
            print("Response:\n%s" % data.decode('ascii'))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='crawl Fakebook')
    parser.add_argument('-s', dest="server", type=str, default=DEFAULT_SERVER, help="The server to crawl")
    parser.add_argument('-p', dest="port", type=int, default=DEFAULT_PORT, help="The port to use")
    parser.add_argument('username', type=str, help="The username to use")
    parser.add_argument('password', type=str, help="The password to use")
    args = parser.parse_args()
    sender = Crawler(args)
    sender.run()
