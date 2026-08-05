import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import settings


def _key() -> bytes:
    key = base64.b64decode(settings.FIELD_ENCRYPTION_KEY)
    if len(key) != 32:
        raise ValueError("FIELD_ENCRYPTION_KEY must decode to exactly 32 bytes")
    return key


def encrypt_field(value: str | None) -> str | None:
    if value is None:
        return None
    nonce = os.urandom(12)
    ciphertext = AESGCM(_key()).encrypt(nonce, value.encode("utf-8"), None)
    return base64.b64encode(nonce + ciphertext).decode("utf-8")


def decrypt_field(value: str | None) -> str | None:
    if value is None:
        return None
    raw = base64.b64decode(value)
    nonce, ciphertext = raw[:12], raw[12:]
    return AESGCM(_key()).decrypt(nonce, ciphertext, None).decode("utf-8")
