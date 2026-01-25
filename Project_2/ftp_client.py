import socket


# Connect to the FTP server
def control_connect(HOST, PORT):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((HOST, PORT))
    welcome = recv_reply(sock)  # ← Read welcome message!
    print(f"Server: {welcome}")
    return sock

def pasv_connect(HOST, PORT):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((HOST, PORT))
    return sock

def send_command(sock, command):
    sock.send(command.encode() + b"\r\n")
    return recv_reply(sock)

def login(sock, username, password):
    response = send_command(sock, f"USER {username}")
    print(f"Server: USER {username}")
    if password:
        response = send_command(sock, f"PASS {password}")
        print(f"Server: PASS {password}")
    return response

def recv_reply(sock):
    buffer = b""
    while b"\r\n" not in buffer:
        data = sock.recv(4096)
        if not data:
            break
        buffer += data  
    return buffer.decode(errors="ignore")

def main():
#    serv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    serv = control_connect("ftp.4700.network", 21)
    login(serv, 'daoud.ja', '97c30eb79ad37d6013afd7acee24226c49d705b1c4c40567449ae6532fd83cc3')
    print("test")

if __name__ == "__main__":
    main()
# def handle_ls():

# def handle_mkdir():

# def handle_rm():

# def handle_rmdir():

# def handle_cp():

# def handle_mv():

# if arg1 = ls
# call handle_ls

# if arg1 = mkdir
# call handle_mkdir