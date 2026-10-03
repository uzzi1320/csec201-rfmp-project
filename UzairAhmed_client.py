#client.py - simple RFMP client

import socket
import sys

from packet_utils import encode_packet, encode_payload, decode_payload, PacketReceiver

try:
    import encryption
except ImportError:
    encryption = None

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

def setup_phase(sock, receiver):
   #Asks the user whether they want a secured connection, then runs either the plain handshake (SS,0 -> CC) or the secured one
   #None if setup failed.
    
    choice = input('Use a secured connection? (y/n): ').strip().lower()
    secure = choice == 'y'

    send_packet(sock, ['SS', 'RFMP', 'v1.0', '1' if secure else '0'])
    reply = read_reply(receiver)

    if reply[0] != 'CC':
        show_result(reply)
        return None

    if not secure:
        print('Connected to the server (unsecured)')
        return {'secure': False}

    if encryption is None:
        print('encryption.py is not available - cannot use a secured connection')
        return None

    server_public_key = reply[1]

    algorithm = ''
    while algorithm not in ('aes', 'caesar'):
        algorithm = input('Algorithm (aes/caesar): ').strip().lower()

    session_key = encryption.generate_session_key()
    encrypted_session_key = encryption.rsa_encrypt(session_key, server_public_key)
    client_public_key, _ = encryption.generate_rsa_keypair()
    username = input('Username: ').strip() or 'client'

    send_packet(sock, ['EC', algorithm, encrypted_session_key, f'{username}:{client_public_key}'])

    print(f'Connected to the server (secured, {algorithm})')
    return {'secure': True, 'algorithm': algorithm, 'key': session_key}

def run_prompt(sock, receiver, command):
    #asks server to run commands 
    send_packet(sock, ['CM', 'prompt', command])
    show_result(read_reply(receiver))

def encrypt_text(session, text):
    if session['algorithm'] == 'aes':
        return encryption.aes_encrypt(text, session['key'])
    return encryption.caesar_encrypt(text, session['key'])

def decrypt_text(session, text):
    if session['algorithm'] == 'aes':
        return encryption.aes_decrypt(text, session['key'])
    return encryption.caesar_decrypt(text, session['key'])

def read_file(sock, receiver, session, filename):
    #asks server for a file, it answers with a data packet and then SC
    send_packet(sock, ['CM', 'openRead', filename])
    reply = read_reply(receiver)
    if reply[0] == 'DP':
        text = decode_payload(reply[1]).decode('utf-8')
        if session['secure']:
            text = decrypt_text(session, text)
        print('---- file content ----')
        print(text)
        print('----------------------')
        reply =  read_reply(receiver) #the SC packet that comes after the data
    show_result(reply)

def write_file(sock, receiver, session, filename):
    #sends the file & text as data packet, server saves it
    lines = []
    while True:
        line = input()
        if line == '.':
            break
        lines.append(line)
    text = '\n'.join(lines)

    if session['secure']:
        text = encrypt_text(session, text)

    send_packet(sock, ['CM', 'openWrite', filename])
    send_packet(sock, ['DP', encode_payload(text)])
    show_result(read_reply(receiver))

def show_menu():
    print()
    print('1) mkdir      - create a folder')
    print('2) cd         - change a folder')
    print('3) rmdir      - delete a folder')
    print('4) del        - delete a file')
    print('5) ren        - rename a file or folder')
    print('6) other system command')
    print('7) openRead   - read a file on the server')
    print('8) openWrite  - write a file on the server')
    print('9) quit')

def command_loop(sock, receiver, session):
    #keeps showing the menu until the user chooses quit
    while True:
        show_menu()
        choice =  input('Choose an option:').strip()

        if choice == '1':
            run_prompt(sock, receiver, 'mkdir ' + input('Folder name: '))
        elif choice == '2':
            run_prompt(sock, receiver, 'cd ' + input('Folder name: '))
        elif choice == '3':
            run_prompt(sock, receiver, 'rmdir ' + input('Folder name: '))
        elif choice == '4':
            run_prompt(sock, receiver, 'del ' + input('File name: '))
        elif choice == '5':
            old_name =  input('Current name: ')
            new_name = input('New name: ')
            run_prompt(sock, receiver, 'ren ' + old_name + ' ' + new_name)
        elif choice == '6':
            run_prompt(sock, receiver, input('Command: '))
        elif choice == '7':
            read_file(sock, receiver, session, input('File name: '))
        elif choice == '8':
            write_file(sock, receiver, session, input('File name: '))
        elif choice == '9':
            break
        else:
            print('Please choose a number from 1 to 9.')

def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect((HOST, PORT))
    except OSError:
        print(f'Could not connect to {HOST}:{PORT}. Is the server running? ')
        return

    receiver = PacketReceiver(sock)

    session = setup_phase(sock, receiver)
    if session is not None:
        command_loop(sock, receiver, session)
        send_packet(sock, ['End']) #closing phase

    sock.close()
    print('Connection closed.')

if __name__ == '__main__':
    main()