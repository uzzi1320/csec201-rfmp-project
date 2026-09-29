import os
import base64
from typing import Optional, Tuple

from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

RSA_KEY_SIZE = 2048
AES_KEY_SIZE = 32          # AES-256
GCM_NONCE_SIZE = 12


def generate_rsa_keypair(bits: int = RSA_KEY_SIZE) -> Tuple[bytes, bytes]:
    """Return (private_pem, public_pem)."""
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=bits,
    )

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )

    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    return private_pem, public_pem


def _load_public_key(public_pem: bytes):
    return serialization.load_pem_public_key(public_pem)


def _load_private_key(private_pem: bytes):
    return serialization.load_pem_private_key(private_pem, password=None)


def rsa_encrypt(public_pem: bytes, plaintext: bytes) -> bytes:
    public_key = _load_public_key(public_pem)
    return public_key.encrypt(
        plaintext,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )


def rsa_decrypt(private_pem: bytes, ciphertext: bytes) -> bytes:
    private_key = _load_private_key(private_pem)
    return private_key.decrypt(
        ciphertext,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )

def generate_aes_key() -> bytes:
    """32-byte AES-256 key."""
    return os.urandom(AES_KEY_SIZE)


def aes_encrypt(key: bytes, plaintext: bytes, aad: Optional[bytes] = None) -> bytes:
    """Return nonce + AES-GCM ciphertext/tag."""
    if len(key) not in (16, 24, 32):
        raise ValueError("AES key must be 16, 24, or 32 bytes")

    nonce = os.urandom(GCM_NONCE_SIZE)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext, aad)
    return nonce + ciphertext


def aes_decrypt(key: bytes, blob: bytes, aad: Optional[bytes] = None) -> bytes:
    """Input is nonce + AES-GCM ciphertext/tag."""
    if len(key) not in (16, 24, 32):
        raise ValueError("AES key must be 16, 24, or 32 bytes")
    if len(blob) < GCM_NONCE_SIZE + 16:
        raise ValueError("AES blob too short")

    nonce = blob[:GCM_NONCE_SIZE]
    ciphertext = blob[GCM_NONCE_SIZE:]
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ciphertext, aad)

def caesar_encrypt(text: str, shift: int) -> str:
    shift %= 26
    result = []

    for ch in text:
        if "a" <= ch <= "z":
            result.append(chr((ord(ch) - ord("a") + shift) % 26 + ord("a")))
        elif "A" <= ch <= "Z":
            result.append(chr((ord(ch) - ord("A") + shift) % 26 + ord("A")))
        else:
            result.append(ch)

    return "".join(result)


def caesar_decrypt(text: str, shift: int) -> str:
    return caesar_encrypt(text, -shift)

def bytes_to_b64(data: bytes) -> str:
    return base64.b64encode(data).decode("utf-8")


def b64_to_bytes(data: str) -> bytes:
    return base64.b64decode(data.encode("utf-8"))


def hybrid_encrypt(public_pem: bytes, plaintext: bytes, aad: Optional[bytes] = None) -> bytes:
    """RSA-encrypt an AES key, then AES-GCM encrypt the message."""
    aes_key = generate_aes_key()
    encrypted_key = rsa_encrypt(public_pem, aes_key)
    encrypted_msg = aes_encrypt(aes_key, plaintext, aad)

    return len(encrypted_key).to_bytes(2, "big") + encrypted_key + encrypted_msg


def hybrid_decrypt(private_pem: bytes, blob: bytes, aad: Optional[bytes] = None) -> bytes:
    if len(blob) < 2:
        raise ValueError("Hybrid blob too short")

    key_len = int.from_bytes(blob[:2], "big")

    if len(blob) < 2 + key_len:
        raise ValueError("Hybrid blob missing RSA key")

    encrypted_key = blob[2:2 + key_len]
    encrypted_msg = blob[2 + key_len:]

    aes_key = rsa_decrypt(private_pem, encrypted_key)
    return aes_decrypt(aes_key, encrypted_msg, aad)