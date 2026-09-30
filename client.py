import getpass
import secrets
import socket
import sys

from packet_utils import encode_payload, decode_payload, PacketReceiver

try:
    from packet_utils import encode_packet
except ImportError:
    from packet_utils import encode_packets as encode_packet

DEFAULT_HOST = 'localhost'
DEFAULT_PORT = 5000
PROTOCOL_NAME = 'RFMP'
PROTOCOL_VERSION = 'v1.0'

# Meaning of the error codes the server puts in an Exception-Packet (EE, code, description).
ERROR_NAMES = {
    '1': 'Bad request',
    '2': 'Not found',
    '3': 'Command failed',
    '4': 'Server error',
}

# Prompt commands offered in the menu: menu key -> (command, [questions for its arguments]).
PROMPT_COMMANDS = {
    '1': ('mkdir', ['Folder name']),
    '2': ('cd', ['Folder to change into']),
    '3': ('rmdir', ['Folder to delete']),
    '4': ('del', ['File to delete']),
    '5': ('ren', ['Current name', 'New name']),
}

def send_packet(sock, fields):
    """Encode a list of fields as one RFMP packet and send it."""
    sock.sendall(encode_packet(fields))


def read_packet(receiver):
    """Wait for the next full packet. Raises ConnectionError if the server hung up."""
    fields = receiver.get_packet()
    if fields is None:
        raise ConnectionError('The server closed the connection.')
    return fields


def show_error(fields):
    """Print an Exception-Packet (EE, error_code, description) in a readable way."""
    code = fields[1] if len(fields) > 1 else '?'
    description = ','.join(fields[2:]) if len(fields) > 2 else 'No description'
    name = ERROR_NAMES.get(code, 'Unknown error')
    print(f'[ERROR {code} - {name}] {description}')

class Session:

    def __init__(self, algorithm=None, key=None, enc=None):
        self.algorithm = algorithm
        self.key = key
        self.enc = enc

    def encrypt_text(self,text):
        if self.algorithm == 'AES':
            data = self.enc.aes_encrypt(self.key, text.encode('utf-8'))
        elif self.algorithm == 'Caesar':
            data = self.enc.ceasar_encrypt(text, self.key).encode('utf-8')
        else:
            data = text.encode('utf-8')
        return encode_payload(data)

    def decrypt_text(self,field):
        data = decode_payload(field)
        if self.algorithm == 'AES':
            data = self.enc.aes_decrypt(self.key, data)
        elif self.algorithm == 'Ceasar':
            data = self.enc.caesar_decrypt(data.decode('utf-8'), self.key).encode('utf-8')
        return data.decode('utf-8', errors='replace')