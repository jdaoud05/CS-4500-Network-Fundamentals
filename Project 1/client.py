#!/usr/bin/env python3
import socket
import json
import ssl
import sys


# Open wordlist.txt, if it's not found, output an error
try:
    with open("project1-words.txt", "r") as f:
        wordlist = f.read().splitlines()
except FileNotFoundError:
    sys.stderr.write("Error: project1-words.txt not found\n")
    sys.exit(1)


# If there are less than 3 arguments, display the correct usage
if len(sys.argv) < 3:
    sys.stderr.write(
        "Usage: ./client <-p port> <-s> <hostname> <Northeastern-username>"
    )
    sys.exit(1)

PORT = 27993
TLS = False

args = sys.argv[1:]


i = 0
while i < len(args):
    # Set the port number to the integer specified by -p. If the user does not enter a number, display an error.
    if args[i] == "-p":
        if i + 1 >= len(args):
            sys.stderr.write("Error: -p requires a port number\n")
            sys.exit(1)
        PORT = int(args[i + 1])
        i += 2

    # If -s is specified, enable TLS
    elif args[i] == "-s":
        TLS = True
        i += 1
    else:
        break

# After flags, we must have exactly 2 args left
if len(args) - i != 2:
    sys.stderr.write(
        "Usage: ./client [-p port] [-s] <hostname> <Northeastern-username>\n"
    )
    sys.exit(1)

HOST = args[i]
USER = args[i + 1]

# TLS default port adjustment
if TLS and PORT == 27993:
    PORT = 27994



# Connect to the server
def connect(host, port, use_tls):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    if use_tls:
        context = ssl.create_default_context()
        sock = context.wrap_socket(sock, server_hostname=host)

    sock.connect((host, port))
    return sock

# Send socket to the server
def send_json(sock, obj):
    sock.sendall((json.dumps(obj) + "\n").encode())

# Receive socket connection
def recv_json(sock):
    buffer = ""
    while "\n" not in buffer:
        data = sock.recv(4096)
        if not data:
            raise ConnectionError("Server closed connection")
        buffer += data.decode()

    line, _ = buffer.split("\n", 1)
    return json.loads(line)


# Grey character filtering logic
def filter_word(char):
    wordlist[:] = [
        wrd for wrd in wordlist
        if not any(c in wrd for c in char)
    ]

# Green character filtering logic
def only_include(letter, idx):
    wordlist[:] = [
        wrd for wrd in wordlist
        if wrd[idx] == letter
    ]



# Wordle filtering logic based on server feedback.
# The function narrows the candidate wordlist using the marks returned for a given guess.
#
# Mark meanings:
#   0 = letter not in word (gray)
#   2 = correct letter in correct position (green)
def guess_word(word, marks):
    if "[0, 0, 0, 0, 0]" == marks:
        filter_word(word)
        
    if "[0, 0, 0, 0, 2]" == marks:
        only_include(word[4], 4)
        if word[4] not in word[0:4]:
            filter_word(word[0:4])
        
    if "[0, 0, 0, 2, 0]" == marks:
        only_include(word[3], 3)
        if word[3] not in word[0:3] + word[4]:
            filter_word(word[0:3] + word[4])
        
    if "[0, 0, 2, 0, 0]" == marks:
        if word[2] not in word[0:2] + word[3:5]:
            filter_word(word[0:2] + word[3:5])
        only_include(word[2], 2)
        
    if "[0, 2, 0, 0, 0]" == marks:
        if word[1] not in word[0] + word[2:5]:
            filter_word(word[0] + word[2:5])
        only_include(word[1], 1)
        
    if "[2, 0, 0, 0, 0]" == marks:
        fifth = word[1:5]
        if word[0] not in word[1:5]:
            filter_word(word[1:5])
        only_include(word[0], 0)


    if "[0, 0, 0, 0, 1]" == marks:
        if word[4] not in word[0:4]:
            filter_word(word[0:4])
        
    if "[0, 0, 0, 1, 0]" == marks:
        if word[3] not in word[0:3] + word[4]:
            filter_word(word[0:3] + word[4])
        
    if "[0, 0, 1, 0, 0]" == marks:
        if word[2] not in word[0:2] + word[3:5]:
            filter_word(word[0:2] + word[3:5])
        
    if "[0, 1, 0, 0, 0]" == marks:
            filter_word(word[0] + word[2:5])
        
    if "[1, 0, 0, 0, 0]" == marks:
        if word[0] not in word[1:5]:
            filter_word(word[1:5])


    if "[2, 2, 0, 0, 0]" == marks:
        only_include(word[0], 0)
        only_include(word[1], 1)

    if "[2, 0, 2, 0, 0]" == marks:
        only_include(word[0], 0)
        only_include(word[2], 2)
        
    if "[2, 0, 0, 2, 0]" == marks:
        only_include(word[0], 0)
        only_include(word[3], 3)
        
    if "[2, 0, 0, 0, 2]" == marks:
        only_include(word[0], 0)
        only_include(word[4], 4)
        
    if "[0, 2, 2, 0, 0]" == marks:
        only_include(word[1], 1)
        only_include(word[2], 2)

    if "[0, 2, 0, 2, 0]" == marks:
        only_include(word[1], 1)
        only_include(word[3], 3)
        
    if "[0, 2, 0, 0, 2]" == marks:
        only_include(word[1], 1)
        only_include(word[4], 4)
        
    if "[0, 0, 2, 2, 0]" == marks:
        only_include(word[2], 2)
        only_include(word[3], 3)

    if "[0, 0, 2, 0, 2]" == marks:
        only_include(word[2], 2)
        only_include(word[4], 4)
        
    if "[0, 0, 0, 2, 2]" == marks:
        only_include(word[3], 3)
        only_include(word[4], 4)        

    if "[2, 2, 2, 0, 0]" == marks:
        only_include(word[0], 0)
        only_include(word[1], 1)
        only_include(word[2], 2)
        
    if "[0, 2, 2, 2, 0]" == marks:
        only_include(word[1], 1)
        only_include(word[2], 2)
        only_include(word[3], 3)        
        
    if "[0, 0, 2, 2, 2]" == marks:
        only_include(word[2], 2)
        only_include(word[3], 3)
        only_include(word[4], 4)       
        
        
    if "[0, 2, 2, 0, 2]" == marks:
        only_include(word[1], 1)
        only_include(word[2], 2)
        only_include(word[4], 4)        
        
    if "[0, 2, 0, 2, 2]" == marks:
        only_include(word[1], 1)
        only_include(word[3], 3)
        only_include(word[4], 4)        

# Iteratively send the guessed word from the wordlist, while narrowing the server feedback
def play_game(sock, game_id):
    index = 0
    while wordlist:
        word = wordlist.pop(0)
        index += 1

        # Construct and send the guess to the server
        guess_msg = {
            "type": "guess",
            "id": game_id,
            "word": word
        }
        send_json(sock, guess_msg)

        # Receive server response containing feedback for this guess
        response = recv_json(sock)
        print(response)

        # Extract marks from server response
        entry = response["guesses"][index - 1]
        marks = str(entry["marks"])

        # Find the next best word from the wordlist 
        guess_word(word, marks)

    print("Wordlist exhausted")


def main():
    # Establish connection to the Wordle server (TLS optional)
    sock = connect(HOST, PORT, TLS)

    # Construct and send hello message to start a new game session
    hello = {
        "type": "hello",
        "northeastern_username": USER
    }
    send_json(sock, hello)

    # Receive response and extract game ID
    response = recv_json(sock)
    game_id = response["id"]

    # Iteratively send the guessed word from the wordlist, while narrowing the server feedback
    play_game(sock, game_id)

    # Close server connection
    sock.close()

if __name__ == "__main__":
    main()

    
