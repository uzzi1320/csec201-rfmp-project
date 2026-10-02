#client.py - simple RFMP client

import socket
import sys

from packet_utils import encode_packet, encode_payload, decode_payload, PacketReceiver

HOST = sys.argv[1] if len(sys.argv) > 1 else 'localhost'
PORT = 5000

def send_packet(sock, fields):
    #turns a list of fields into a packet and sends it, quits if server stops
    sock.sendall(encode_packet(fields))

def read_reply(receiver):
    #wait for the next packet from the server
    fields = receiver.get_packet()
    if fields is None:
        print("The server closed the connection.")
        sys.exit()
    return fields

def show_result(reply):
    #prints the servers answer
    #SC means success, EE means error
    if reply[0] == 'SC':
        print("Success")
    elif reply[0] == 'EE':
        print(f'Error {reply[1]}: {reply[2]}')
    else: 
        print('Unexpected reply:', reply)

def setup_phase(sock,receiver):
    #sends the start-packet and checks the servers answer with CC
    send_packet(sock, ['SS','RFMP', 'v1.0', '0'])
    reply = read_reply(receiver)
    if reply[0] == 'CC':
        print('Connected to the server')
        return True
    show_result(reply)
    return False

def run_prompt(sock, receiver, command):
    #asks server to run commands 
    send_packet(sock, ['CM', 'prompt', command])
    show_result(read_reply(receiver))

def read_file(sock, receiver, filename):
    #asks server for a file, it answers with a data packet and then SC
    send_packet(sock, ['CM', 'openRead', filename])
    reply = read_reply(receiver)
    if reply[0] == 'DP':
        print('---- file content ----')
        print(decode_payload(reply[1]).decode('utf-8'))
        print('----------------------')
        reply =  read_reply(receiver) #the SC packet that comes after the data
    show_result(reply)

def write_file(sock, receiver, filename):
    #sends the file & text as data packet, server saves it
    lines = []
    while True:
        line = input()
        if line == '.':
            break
        lines.append(line)
    text = '\n'.join(lines)

    send_packet(sock, ['CM', 'openWrite', filename])
    send_packet(sock, ['DP', encode_payload(text)])
    show_result(read_reply(receiver))