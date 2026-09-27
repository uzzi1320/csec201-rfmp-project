import socket
import threading
from packet_utils import encode_packet, PacketReceiver

HOST = '0.0.0.0' # Listening on all network interfaces
PORT = 5000

# Creating a TCP socket.
server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

# allowing the port to be reused immediately after restarting the server.
server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server_socket.bind((HOST,PORT))
server_socket.listen(5) # allow upto 5 pending connections in queue
print(f"Server listening on {HOST}:{PORT}")


def handle_client(conn, addr):
    """
    Runs in its own thread for each connected client.
    This will eventually contain the full setup phase and command loop for that client
    """

    print(f"Handling client {addr}")

    #wraps the raw socket so we can read whole packets safely,
    #regardless of how TCP splits the bytes
    receiver = PacketReceiver(conn)

    #block until the client's first packet arrives - this should be the Start-packet
    fields = receiver.get_packet()

    if fields is None:
        #client disconnects before sending anything
        conn.close()
        return

    packet_type = fields[0]

    if packet_type == 'SS':
        security_flag = fields[3]
        print(f"Received Start-Packet, security flag={security_flag}")

        #reply with Confirm-Connection-Packet
        response = encode_packet(['CC','ok'])
        conn.sendall(response)
        
    else:
        print(f"Unexpected first packet type: {packet_type}")
    conn.close()

while True:
    conn, addr = server_socket.accept()
    print(f"Connection from {addr}")

    #handing this client off to its own thread so main loop can continue
    # goes back to accept() and serves the next client imediately.
    thread = threading.Thread(target=handle_client, args=(conn, addr))
    thread.start()
