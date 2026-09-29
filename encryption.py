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
