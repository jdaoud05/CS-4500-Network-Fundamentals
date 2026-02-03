#!/usr/bin/env python3

import socket
import re
import sys


# Parse the input. Extract the parameters
# Example input: ftp://john:secret123@ftp.example.com/path
def parse_ftp():
    if len(sys.argv) < 2:
        sys.stderr.write("Usage: ./4700ftp [operation] [param1] [param2]")
        sys.exit(1)

    ftp_url = sys.argv[-1]
    match = re.search(r'ftp://([^:]+):([^@]+)@([^/]+)', ftp_url)
    if not match:
        sys.stderr.write("Error: Incorrect FTP URL Format")
        sys.exit(1)
    
    # Return the user, password, and hostname
    return str(match.group(1)), str(match.group(2)), str(match.group(3))

# Connect to the FTP server
def control_connect(HOST, PORT):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((HOST, PORT))
    return sock

def recv_reply(sock):
    
   buffer = b""
   while b"\r\n" not in buffer:
       data = sock.recv(4096)
       if not data:
           break
       buffer += data  
   return buffer.decode(errors="ignore")

def multi_line(sock):
    complete = False

    response = b""

    # Receive the data until there's a string like %d%d%d xxxx
    # This indicates its the end of the line
    while True:
        data = sock.recv(4096)
        if not data:
            break
        response += data

        lines = response.split(b'\r\n')
        for line in lines:
            match = re.match(rb'^(\d{3})', line)


            if match:
                code = match.group(0)
                if code + b'-' in line:
                    pass
                if code + b' ' in line:
                    complete = True
                    break
            else: 
                break
        if complete:
            break

    return response.decode('utf-8', errors='ignore')



# Helper function used to send commands
def send_command(sock, command):
    sock.send(command.encode() + b"\r\n")
 

def login(sock, username, password):
    send_command(sock, f"USER {username}")
    response = recv_reply(sock)
    print(f"Server: USER {username}")
    if password:
        send_command(sock, f"PASS {password}")
        response = recv_reply(sock)
        print(f"Server: PASS {password}")
    return response

# Send PASV command. Open a separate port for data transfer
# This is used for actual file/directory data transfer
def pasv_connect(control_sock):
    send_command(control_sock, "PASV")
    reply = multi_line(control_sock)  # Use multi_line
    # ...
    print(reply)

    match = re.search(r'\(([^)]+)\)', reply)

    if match:
        inside = match.group(1).split(',')
        ip = '.'.join(inside[0:4])

        port = (int(inside[4])*256) + int(inside[5])

        data_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        data_sock.connect((ip, port))
        return data_sock   
    else:
        print("ERRORRRR")

# Send "Type I" 8-bit binary
def set_up(control_sock):
    send_command(control_sock, "TYPE I")
    type_msg = multi_line(control_sock)  # Use multi_line
    
    send_command(control_sock, "MODE S")
    mode_msg = multi_line(control_sock)  # Use multi_line

    send_command(control_sock, "STRU F")
    stru_msg = multi_line(control_sock)  # Use multi_line

    return type_msg, mode_msg, stru_msg

    return type_msg, mode_msg, stru_msg
def quit(control_sock):
    quit_msg = send_command(control_sock, "QUIT")
    print(quit_msg)

    return quit_msg


def extract_path():
    re_path = re.search("^ftp://[^/]+/(.*)$", sys.argv[-1])
    path = str(re_path.group(1))
    return path




# Sends LIST, to list all files in the FTP server
def list(sock):
    data_sock = pasv_connect(sock)

    send_command(sock, "LIST")
    reply = recv_reply(sock)
    print(reply)
    
    buffer = b""
    while True:
        data = data_sock.recv(4096)
        if not data:
            break
        buffer += data
    data_sock.close()

    print(buffer.decode())



def delete(control_sock, data_sock):
    send_command(control_sock, "DELE")
    reply = recv_reply(control_sock)
    print(reply)

    buffer = b""
    while True:
        data = data_sock.recv(4096)
        if not data:
            break
        buffer += data
    data_sock.close()

def create_dir(control_sock, path):

    path = extract_path()

    send_command(control_sock, f"MKD {path}")
    reply = multi_line(control_sock)
    print(path)
    print(reply)
    

    return reply

def remove_dir(control_sock, path):

    path = extract_path()
    print(f"pp: {path}")

    send_command(control_sock, f"RMD {path}")
    reply = recv_reply(control_sock)
    print(reply)


    return reply


def remove_file(control_sock, path):

    path = extract_path()

    send_command(control_sock, f"DELE {path}")
    reply = recv_reply(control_sock)

    return reply


# def remove_file(control_sock, data_sock):
# def upload(control_sock, data_sock):
# def download(control_sock, data_sock):




def input(sock):
    #data_sock = pasv_connect(sock)
   
    

   

    if len(sys.argv) < 3:
        sys.stderr.write("Usage: ./4700ftp [operation] [param1] [param2]")
        sys.exit(1)



    if sys.argv[1] == 'ls':
        list(sock)
    if sys.argv[1] == 'rm':
         remove_file(sock, extract_path())
    if sys.argv[1] == 'rmdir':
         remove_dir(sock, extract_path())
    if sys.argv[1] == 'mkdir':
         create_dir(sock, extract_path())
#     if sys.argv[1] == 'cp':
#         copy(control_sock, data_sock)
#     if sys.argv[1] == 'mv':
#         move(control_sock, data_sock)

# user sends ls to term. client sends set up to server ... then client sends LIST to server...
#  then client sends QUIT to server


# ftp://USER:PASS@url

# USER = everything after ftp:// to :
# PASS = everything after : to @
# url = everything after @

def main():


    user, password, hostname = parse_ftp()
    #print(hostname)

    
#    serv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock = control_connect(hostname, 21)
    login(sock, user, password)
#   multi_line(sock)

    set_up(sock)
    input(sock)
    #quit(sock)
    #input(sock, data_sock)
    #delete(sock, data_sock)
    #remove_dir(sock)
    


if __name__ == "__main__":
    main()

# NEXT STEPS:
    # Implement support for uploading and downloading files
    # Read hello file