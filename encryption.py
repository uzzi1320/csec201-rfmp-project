import os
import base64
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding as sym_padding

# 1. RSA (Used to securely send the session key)

def generate_rsa_keypair():
    # Generates keys and returns them as Base64 strings to prevent newline bugs in packets
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    
    # Base64 encode internally so the returned strings are safe for packets
    public_str = base64.b64encode(public_pem).decode('utf-8')
    private_str = base64.b64encode(private_pem).decode('utf-8')
    
    # Returns (public, private) exactly as the guide specifies
    return public_str, private_str

def rsa_encrypt(text, public_key):
    # Decodes the Base64 string back to PEM bytes
    public_pem = base64.b64decode(public_key)
    pub_key = serialization.load_pem_public_key(public_pem)
    
    encrypted = pub_key.encrypt(
        text.encode('utf-8'),
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )
    return base64.b64encode(encrypted).decode('utf-8')

def rsa_decrypt(text, private_key):
    private_pem = base64.b64decode(private_key)
    priv_key = serialization.load_pem_private_key(private_pem, password=None)
    
    decrypted = priv_key.decrypt(
        base64.b64decode(text),
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )
    return decrypted.decode('utf-8')

# 2. AES (Used to encrypt the actual data)

def generate_session_key():
    # Generates a random 32-byte key and returns it as a Base64 string
    return base64.b64encode(os.urandom(32)).decode('utf-8')

def aes_encrypt(text, key):
    # Decodes the Base64 key string back to raw bytes
    key_bytes = base64.b64decode(key)
    
    # Simple AES-ECB encryption (easiest to explain, no nonce management needed)
    cipher = Cipher(algorithms.AES(key_bytes), modes.ECB())
    encryptor = cipher.encryptor()
    
    # Pad the text so it fits AES block size
    padder = sym_padding.PKCS7(128).padder()
    padded_data = padder.update(text.encode('utf-8')) + padder.finalize()
    
    encrypted = encryptor.update(padded_data) + encryptor.finalize()
    return base64.b64encode(encrypted).decode('utf-8')

def aes_decrypt(text, key):
    key_bytes = base64.b64decode(key)
    
    cipher = Cipher(algorithms.AES(key_bytes), modes.ECB())
    decryptor = cipher.decryptor()
    
    decrypted_padded = decryptor.update(base64.b64decode(text)) + decryptor.finalize()
    
    # Remove the padding
    unpadder = sym_padding.PKCS7(128).unpadder()
    decrypted = unpadder.update(decrypted_padded) + unpadder.finalize()
    
    return decrypted.decode('utf-8')

# 3. Caesar Cipher (Simple text shifting)

def caesar_encrypt(text, key):
    # Converts the session key string into a number (shift) internally
    shift = sum(ord(c) for c in key) % 26
    
    result = ""
    for char in text:
        if char.isalpha():
            start = ord('A') if char.isupper() else ord('a')
            result += chr((ord(char) - start + shift) % 26 + start)
        else:
            result += char
    return result

def caesar_decrypt(text, key):
    # Converts the session key string into a number (shift) internally
    shift = sum(ord(c) for c in key) % 26
    
    result = ""
    for char in text:
        if char.isalpha():
            start = ord('A') if char.isupper() else ord('a')
            result += chr((ord(char) - start - shift) % 26 + start)
        else:
            result += char
    return result