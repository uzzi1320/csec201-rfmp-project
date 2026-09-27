import socket
HOST = '0.0.0.0'
PORT = 5000

server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server_socket.bind((HOST,PORT))
server_socket.listen(5)
print(f"Server listening on {HOST}:{PORT}")

while True:
    conn, addr = server_socket.accept()
    print(f"Connection from {addr}")
    conn.close()
    
