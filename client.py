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
        