import os
import socket
import threading
import shutil
from packet_utils import encode_packet, encode_payload, decode_payload, PacketReceiver

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

    while True:
        # blocks until the client's next packet arrives
        fields = receiver.get_packet()

        if fields is None:
            # client disconnected without sending a proper closing packet
            print(f"Client {addr} disconnected")
            break

        packet_type = fields[0]

        if packet_type == 'EX':
            # client sent the closing packet
            print(f"Client {addr} sent closing packet")
            break

        elif packet_type == 'CM':
            command = fields[1]
            args = fields[2:]

            if command == 'openWrite':
                try:
                    data_fields = receiver.get_packet()
                    if data_fields is None or data_fields[0] != 'DP':
                        conn.sendall(encode_packet(['EE','6','Expected Data-Packet after openWrite']))
                    else:
                        content = decode_payload(data_fields[1])
                        with open(args[0],'wb') as f:
                            f.write(content)
                        conn.sendall(encode_packet(['OK','openWrite']))
                except Exception as e:
                    conn.sendall(encode_packet(['EE','5',str(e)]))

            elif command == 'mkdir':
                try:
                    os.mkdir(args[0])
                    conn.sendall(encode_packet(['OK','mkdir']))
                except FileExistsError:
                    conn.sendall(encode_packet(['EE','4','Folder already exisits']))
                except Exception as e:
                    conn.sendall(encode_packet(['EE','5',str(e)]))

            elif command == 'rmdir':
                try:
                    os.rmdir(args[0])
                    conn.sendall(encode_packet(['OK','rmdir']))
                except FileNotFoundError:
                    conn.sendall(encode_packet(['EE','3','File not found']))
                except Exception as e:
                    conn.sendall(encode_packet(['EE','5',str(e)]))

            elif command == 'del':
                try:
                    os.remove(args[0])
                    conn.sendall(encode_packet(['OK','del']))
                except FileNotFoundError:
                    conn.sendall(encode_packet(['EE','3','File not found']))
                except Exception as e:
                    conn.sendall(encode_packet(['EE','5',str(e)]))

            elif command == 'ren':
                try:
                    os.rename(args[0],args[1])
                    conn.sendall(encode_packet(['OK','ren']))
                except FileNotFoundError:
                    conn.sendall(encode_packet(['EE','3','File or Folder not found']))
                except Exception as e:
                    conn.sendall(encode_packet(['EE','5',str(e)]))

            elif command == 'cd':
                try:
                    os.chdir(args[0])
                    conn.sendall(encode_packet(['OK','cd']))
                except FileNotFoundError:
                    conn.sendall(encode_packet(['EE','3','File not found']))
                except Exception as e:
                    conn.sendall(encode_packet(['EE','5',str(e)]))

            elif command == 'copy':
                try:
                    shutil.copy(args[0], args[1])
                    conn.sendall(encode_packet(['OK','copy']))
                except FileNotFoundError:
                    conn.sendall(encode_packet(['EE','3','File not found']))
                except Exception as e:
                    conn.sendall(encode_packet(['EE','5',str(e)]))

            elif command == 'touch':
                try:
                    open(args[0],'a').close()
                    conn.sendall(encode_packet(['OK','touch']))
                except Exception as e:
                    conn.sendall(encode_packet(['EE','5',str(e)]))

            elif command == 'exists':
                result = 'yes' if os.path.exists(args[0]) else 'no'
                conn.sendall(encode_packet(['OK',result]))

            elif command == 'pwd':
                conn.sendall(encode_packet(['OK',encode_payload(os.getcwd())]))

            elif command == 'list':
                entries = ';'.join(os.listdir('.'))
                conn.sendall(encode_packet(['OK',encode_payload(entries)]))

            elif command == 'openRead':
                try:
                    with open(args[0], 'rb') as f:
                        content = f.read()
                    conn.sendall(encode_packet(['DP', encode_payload(content)]))
                except FileNotFoundError:
                    conn.sendall(encode_payload(['EE','3','File not found']))
                except Exception as e:
                    conn.sendall(encode_packet(['EE','5',str(e)]))

            else:
                conn.sendall(encode_packet(['EE','2',f'Unknown command: {command}']))
            
        else:
            print(f"Received packet type: {packet_type}")

    conn.close() 

while True:
    conn, addr = server_socket.accept()
    print(f"Connection from {addr}")

    #handing this client off to its own thread so main loop can continue
    # goes back to accept() and serves the next client imediately.
    thread = threading.Thread(target=handle_client, args=(conn, addr))
    thread.start()
