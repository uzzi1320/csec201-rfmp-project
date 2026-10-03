import os
import socket
import threading
from packet_utils import encode_packet, encode_payload, decode_payload, PacketReceiver
try:
    import encryption
except ImportError:
    encryption = None

# Error codes for Exception-Packets (EE)
ERR_BAD_REQUEST = '1'
ERR_NOT_FOUND = '2'
ERR_COMMAND_FAILED = '3'
ERR_SERVER = '4'

HOST = '0.0.0.0' # Listening on all network interfaces
PORT = 5000

# Creating a TCP socket.
server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

# allowing the port to be reused immediately after restarting the server.
server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server_socket.bind((HOST,PORT))
server_socket.listen(5) # allow upto 5 pending connections in queue
server_socket.settimeout(1.0)
print(f"Server listening on {HOST}:{PORT}")

def send_error(conn, code, description):
    """ Send an exception packet: (EE, error_code, description)."""
    #flattening commas and newlines since they would break packet framing
    description = str(description).replace(',',';').replace('\r',' ').replace('\n',' ')
    conn.sendall(encode_packet(['EE', code, description]))

def encrypt_text(session, text):
    """
    To encrypt text with the session's key, using whichever algorithm the client chooses
    """
    if session['algorithm'] == 'aes':
        return encryption.aes_encrypt(text, session['key'])
    return encryption.caesar_encrypt(text, session['key'])

def decrypt_text(session, text):
    """Decrypt text with the session's key, using whichever algorithm the client chose."""
    if session['algorithm'] == 'aes':
        return encryption.aes_decrypt(text, session['key'])
    return encryption.caesar_decrypt(text, session['key'])

def run_prompt_command(conn, command_text):
    """Runs a system command sent as (CM, prompt, full command text),
    eg. 'mkdir folder1' or 'ren homework1 homework2'.
    Replies with SC on success or EE on failure."""

    parts = command_text.split(None, 1)
    if not parts:
        send_error(conn, ERR_BAD_REQUEST, 'Empty command')
        return

    #cd has to change the server's own folder. os.system runs each command in its own shell, so a cd run through it would be forgotten straight away.    
    if parts[0].lower() =='cd':
        if len(parts) == 1:
            send_error(conn, ERR_BAD_REQUEST, 'cd needs a folder')
            return
        try:
            os.chdir(parts[1].strip().strip('"'))
            conn.sendall(encode_packet(['SC']))
        except FileNotFoundError:
            send_error(conn, ERR_NOT_FOUND, 'Folder not found')
        except Exception as e:
            send_error(conn, ERR_COMMAND_FAILED, e)
        return

    exit_code = os.system(command_text)
    if exit_code == 0:
        conn.sendall(encode_packet(['SC']))
    else:
        send_error(conn, ERR_COMMAND_FAILED, 'Command failed')

def open_read(conn, session, filename):
    """
    openRead sends the file's content to the client in a Data-Packet, then ends with a SC packet
    """
    try:
        with open(filename, 'rb') as f: #rb is to read raw bytes
            content = f.read()
    except FileNotFoundError:
        send_error(conn, ERR_NOT_FOUND, 'File not found')
        return
    except Exception as e:
        send_error(conn, ERR_SERVER, e)
        return

    try:
        if session['secure']:
            text = content.decode('utf-8')
            text = encrypt_text(session, text)
        else:
            text = content
        conn.sendall(encode_packet(['DP', encode_payload(text)]))
        conn.sendall(encode_packet(['SC']))
    except Exception as e:
        send_error(conn, ERR_SERVER, e)

def open_write(conn, receiver, session, filename):
    """
    the files content arrive in a seperate Data-PAcket right after the command, openWrite saves it to the file
    """
    data = receiver.get_packet()
    if data is None or data[0] != 'DP' or len(data) < 2:
        send_error(conn, ERR_BAD_REQUEST, 'Expected Data-Packet after openWrite')
        return
    try:
        content = decode_payload(data[1])
        if session['secure']:
            text = content.decode('utf-8')
            text = decrypt_text(session, text)
            content = text.encode('utf-8')
        with open(filename, 'wb') as f:
            f.write(content)
        conn.sendall(encode_packet(['SC']))
    except Exception as e:
        send_error(conn, ERR_SERVER, e)
            

def setup_phase(conn, receiver):
    """
    Handles the setup phase for one client.
    Returns a session dict, or None if setup fails
    """
    fields = receiver.get_packet()
    if fields is None:
        return None

    if (len(fields) != 4 or fields[0] != 'SS' or fields[1] != 'RFMP'
        or fields[2] != 'v1.0' or fields[3] not in ('0','1')):
        send_error(conn, ERR_BAD_REQUEST, 'Invalid Start-Packet')
        return None

    security_flag = fields[3]
    print(f"Received Start-Packet security flag={security_flag}")

    if security_flag == '0':
        conn.sendall(encode_packet(['CC']))
        return {'secure': False}

    if encryption is None:
        send_error(conn, ERR_SERVER, 'Secure communication is not available on this server')
        return None

    public_key, private_key = encryption.generate_rsa_keypair()
    conn.sendall(encode_packet(['CC',public_key]))

    ec = receiver.get_packet()
    if ec is None or ec[0] != 'EC' or len(ec) < 4:
        send_error(conn, ERR_BAD_REQUEST, "Expected Encryption-Packet")
        return None

    algorithm = ec[1].strip().lower()
    if algorithm not in ('aes', 'caesar'):
        send_error(conn, ERR_BAD_REQUEST, "Unknown encryption algorithm")
        return None

    try:
        session_key = encryption.rsa_decrypt(ec[2], private_key)
    except Exception:
        send_error(conn, ERR_SERVER, 'Could not decrypt session key')
        return None

    print(f"Secure connection established, algorithm={algorithm}")
    return {'secure': True, 'algorithm':algorithm, 'key':session_key}

    
def handle_client(conn, addr):
    """
    Runs in its own thread for each connected client.
    Handles one client: setup phase, then the command loop until the client closes.
    """

    print(f"Handling client {addr}")

    #wraps the raw socket so we can read whole packets safely,
    #regardless of how TCP splits the bytes
    receiver = PacketReceiver(conn)

    session = setup_phase(conn, receiver)
    if session is None:
        conn.close()
        return



    while True:
        # blocks until the client's next packet arrives
        fields = receiver.get_packet()

        if fields is None:
            # client disconnected without sending a proper closing packet
            print(f"Client {addr} disconnected")
            break

        packet_type = fields[0]

        if packet_type == 'End':
            # client sent the closing packet
            print(f"Client {addr} sent Close-Packet")
            break

        # anything else must be a Command-Packet: (CM, command_type, argument)
        if packet_type != 'CM' or len(fields) < 3:
            send_error(conn, ERR_BAD_REQUEST, 'Unknown or malformed packet')
            continue

        command_type = fields[1]
        # rejoin the argument in case the command text itself contained commas
        argument = ','.join(fields[2:])

        if command_type == 'prompt':
            run_prompt_command(conn, argument)
        elif command_type == 'openRead':
            open_read(conn, session, argument)
        elif command_type == 'openWrite':
            open_write(conn, receiver, session, argument)
        else:
            send_error(conn, ERR_BAD_REQUEST, f'Unknown command type: {command_type}')

    conn.close() 

try:
    while True:
        try:
            conn, addr = server_socket.accept()
        except socket.timeout:
            # nobody connected during this second; loop again so Ctrl+C gets noticed
            continue

        conn.settimeout(None)  # the client's socket should wait normally, no timeout
        print(f"Connection from {addr}")

        # hand this client off to its own thread so the loop can go straight
        # back to accept() and serve the next client
        thread = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
        thread.start()
except KeyboardInterrupt:
    print("\nServer shutting down")
finally:
    server_socket.close()
