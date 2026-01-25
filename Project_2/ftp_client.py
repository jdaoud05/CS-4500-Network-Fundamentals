import socket


# Connect to the FTP server
def connect(HOST, PORT):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((HOST, PORT))


def recv_reply(sock):
    buffer = b""
    while b"\r\n" not in buffer:
        data = sock.recv(4096)
        if not data:
            break
        buffer += data  
    return buffer.decode(errors="ignore")

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