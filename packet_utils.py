"""
packet_utils.py is Shared by server.py and client.py.

Defines the RFMP wire format everyone agreed on:
    -fields are seperated by commas
    -each full packet ends with a '\n'
    -everything is utf-8 encoded
"""

import base64

DELIMITER = ','
TERMINATOR = '\n'
ENCODING = 'utf-8'

def encode_packet(fields):
    """
    This method turns a list of fields into raw bytes to send over a socket.
    """
    line = DELIMITER.join(str(f) for f in fields) + TERMINATOR
    return line.encode(ENCODING)

def decode_packet(line):
    """
    Turns a line back into a list of fields
    """
    return line.split(DELIMITER)

def encode_payload(data):
    """
    Base64-encoding a payload so it safely sits as one field inside a coma or newline-delimited packet
    """
    if isinstance(data,str):
        data = data.encode(ENCODING)
    return base64.b64encode(data).decode(ENCODING)

def decode_payload(field):
    """
    Reverse of encode_payload(). Returns raw bytes
    """
    return base64.b64decode(field)


class PacketReceiver:
    """
    This method wraps a connected socket and buffers the bytes so a recv() call that returns partial or merged packet doesnt break the parsing
    """

    def __init__(self, sock, buffer_size=4096):
        self.sock = sock
        self.buffer_size =  buffer_size
        self._buffer = ''

    def get_packet(self):
        """
        Method blocks until a full packet is available and then returns it as a list of fields.
        Returns None is the connection was closed.
        """
        while TERMINATOR not in self._buffer:
            chunk = self.sock.recv(self.buffer_size)
            if not chunk:
                return None
            self._buffer += chunk.decode(ENCODING)

        line, self._buffer = self._buffer.split(TERMINATOR,1)
        return decode_packet(line)