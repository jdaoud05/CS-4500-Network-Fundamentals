import socket
import re
import sys


def parse_ftp():
    if len(sys.argv) < 2:
        sys.stderr.write("Usage: ./4700ftp [operation] [param1] [param2]")
        sys.exit(1)

    ftp_url = sys.argv[-1]
    match = re.search(r'ftp://([^:]+):([^@]+)@([^/]+)', ftp_url)
    if not match:
        sys.stderr.write("Error: Incorrect FTP URL Format")
        sys.exit(1)
    
    return str(match.group(1)), str(match.group(2)), str(match.group(3))

#Connect to the FTP server
def control_connect(HOST, PORT):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((HOST, PORT))
    return sock

def recv_reply(sock):
    
   buffer = ""
   while b"\r\n" not in buffer:
       data = sock.recv(4096)
       if not data:
           break
       buffer += data  
   return buffer.decode(errors="ignore")

def multi_line(sock):
    complete = False

    response = b""
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




def send_command(sock, command):
    sock.send(command.encode() + b"\r\n")
    return multi_line(sock)
 

def login(sock, username, password):
    response = send_command(sock, f"USER {username}")
    print(f"Server: USER {username}")
    if password:
        response = send_command(sock, f"PASS {password}")
        print(f"Server: PASS {password}")
    return response


def pasv_connect(control_sock):
    reply = send_command(control_sock, "PASV")
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
        raise Exception("PASV failed: " + reply)
    
def list(control_sock, data_sock):
    reply = send_command(control_sock, "LIST")
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
    reply = send_command(control_sock, "DELE")
    print(reply)

    buffer = b""
    while True:
        data = data_sock.recv(4096)
        if not data:
            break
        buffer += data
    data_sock.close()

def create_dir(control_sock):
    reply = send_command(control_sock, "MKD")
    print(reply)
    
    buffer = b""
    while True:
        data = control_sock.recv(4096)
        if not data:
            break
        buffer += data
    control_sock.close()

    print(buffer.decode())

# def remove_dir(control_sock, data_sock):

# def type(control_sock, data_sock):
# def stru(control_sock, data_sock):
# def quit(control_sock, data_sock):



    

# def remove_file(control_sock, data_sock):
# def upload(control_sock, data_sock):
# def download(control_sock, data_sock):




# def input(control_sock, data_sock):
    # if len(sys.argv) < 3:
    #     sys.stderr.write("Usage: ./4700ftp [operation] [param1] [param2]")
    #     sys.exit(1)

#     if sys.argv[1] == 'ls':
#         list(control_sock, data_sock)
#     if sys.argv[1] == 'rm':
#         remove_file(control_sock, data_sock)
#     if sys.argv[1] == 'rmdir':
#         remove_dir(control_sock, data_sock)
#     if sys.argv[1] == 'mkdir':
#         create_dir(control_sock, data_sock)
#     if sys.argv[1] == 'cp':
#         copy(control_sock, data_sock)
#     if sys.argv[1] == 'mv':
#         move(control_sock, data_sock)



# ftp://USER:PASS@url
# USER = everything after ftp:// to :
# PASS = everything after : to @
# url = everything after @

def main():


    user, password, hostname = parse_ftp()
    
#    serv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock = control_connect(hostname, 21)
    login(sock, user, password)

    multi_line(sock)
    data_sock = pasv_connect(sock)
    list(sock, data_sock)
    #delete(sock, data_sock)
    #remove_dir(sock)
    


if __name__ == "__main__":
    main()

# NEXT STEPS:
    # Write code that successfully implements the required command line syntax and can parse the incoming data
    # Figure out TYPE, MODE, STRU, and QUIT commands
    # Implement support for making and deleting remote directories