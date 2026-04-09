#!/usr/bin/env python3

import argparse
import socket
import html
from html.parser import HTMLParser
import ssl

class FakebookParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.flags = []
        self.csrf = None
        self.in_flag = False

    def handle_starttag(self, tag, attrs):

        # find all links and append it to self.links
        if tag == "a":
            for attr, value in attrs:
                if attr == "href":
                    self.links.append(value)

        # find instance flags and set to true
        if tag == "h3":
            for attr, value in attrs:
                if attr == "class" and value == "secret_flag":
                    self.in_flag = True
        # find the csrfmiddlewaretoken and assign it to self.csrf
        if tag == "input":
            attrs_dict = dict(attrs)
            if attrs_dict.get("name") == "csrfmiddlewaretoken":
                self.csrf = attrs_dict.get("value")

    # if flag exists append it to self.flags
    def handle_data(self, data):
        if self.in_flag:
            self.flags.append(data.strip())
            self.in_flag = False

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
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((self.server, self.port))

        # tls
        context = ssl.create_default_context()
        self.socket = context.wrap_socket(sock, server_hostname=DEFAULT_SERVER)

    def scrape(self, html):
        parser = FakebookParser()
        parser.feed(html)

        # If link hasn't been visited add it to frontier
        for link in parser.links:
            if self.server in link or link.startswith("/"):
                if link not in self.visited:
                    self.frontier.append(link)
        # if flag doesn't already exist, add flag to self.flags
        # double check this
        for flag in parser.flags:
            if flag not in self.flags:
                self.flags.append(flag)

    def get_request(self, path, host):
        request = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {host}\r\n"
            f"Cookie: csrftoken={self.cookies.get('csrftoken', '')}; sessionid={self.cookies.get('sessionid', '')}\r\n"
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
        return response

    def parse_response(self, response):
        response_text = response.decode('ascii')
        response_header = response_text.split('\r\n\r\n')[0]
        response_body = response_text.split('\r\n\r\n')[1]

        status_code = int(response_text.split()[1])

            
        return status_code, response_header, response_body
    def login(self):


        self.get_request("/accounts/login/?next=/fakebook/", self.server)
        response = self.receive_response()
        status_code, response_header, response_body, = self.parse_response(response)
        
        
        parser = FakebookParser()
        parser.feed(response_body)
        token = parser.csrf
        for l in response_header.split('\r\n'):
            if "Set-Cookie" in l:
                cookie = l.split("csrftoken=")[1].split(";")[0]
                self.cookies['csrftoken'] = cookie
        
        self.post_request('/accounts/login/?next=/fakebook/', self.server, token, self.username, self.password)
        response = self.receive_response()
        status_code, response_header, response_body, = self.parse_response(response) 

        for l in response_header.split('\r\n'):
            if "Set-Cookie" in l and "sessionid" in l:
                self.cookies['sessionid'] = l.split("sessionid=")[1].split(";")[0]


    def find_flag(self):
        self.frontier.append("/fakebook/")

        while self.frontier and len(self.flags) < 5:
            path = self.frontier.pop()
            self.visited.add(path)
            self.get_request(path, self.server)
            response = self.receive_response()
            status_code, response_header, response_body = self.parse_response(response)

            # Handle status codes
            if status_code == 200:
                self.scrape(response_body)
            while status_code == 302:
                for l in response_header.split('\r\n'):
                    if "Location" in l:
                        redirect = l.split(": ")[1]
                        self.get_request(redirect, self.server)
                        response = self.receive_response()
                        status_code, response_header, response_body = self.parse_response(response)


            if status_code == 403 or status_code == 404:
                pass
            while status_code == 503:
                self.get_request(path, self.server)
                response = self.receive_response()
                status_code, response_header, response_body = self.parse_response(response)

    def run(self):
        self.connect()
        self.login()
        self.find_flag()
        
        for flag in self.flags:
            print(flag)
       
        # response = self.receive_response()
        # status_code, response_header, response_body = self.parse_response(response)

     
        





if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='crawl Fakebook')
    parser.add_argument('-s', dest="server", type=str, default=DEFAULT_SERVER, help="The server to crawl")
    parser.add_argument('-p', dest="port", type=int, default=DEFAULT_PORT, help="The port to use")
    parser.add_argument('username', type=str, help="The username to use")
    parser.add_argument('password', type=str, help="The password to use")
    args = parser.parse_args()
    sender = Crawler(args)
    sender.run()
