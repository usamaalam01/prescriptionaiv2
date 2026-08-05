"""Encrypted temporary local storage for prescription images (Milestone 3).

Mock note: MinIO can replace this later via STORAGE_BACKEND=minio without changing callers.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import settings
from app.security.encryption import _key


def _storage_root() -> Path:
    root = Path(__file__).resolve().parents[3] / "storage" / "tmp"
    # Prefer configured relative path from backend cwd
    configured = Path(settings.LOCAL_STORAGE_PATH)
    if not configured.is_absolute():
        configured = (Path(__file__).resolve().parents[2] / configured).resolve()
    else:
        configured = configured.resolve()
    configured.mkdir(parents=True, exist_ok=True)
    return configured


def store_encrypted_bytes(data: bytes, *, suffix: str = ".bin") -> str:
    object_key = f"{uuid.uuid4()}{suffix}"
    nonce = os.urandom(12)
    encrypted = AESGCM(_key()).encrypt(nonce, data, None)
    path = _storage_root() / object_key
    path.write_bytes(nonce + encrypted)
    return object_key


def load_decrypted_bytes(object_key: str) -> bytes:
    path = _storage_root() / object_key
    raw = path.read_bytes()
    nonce, ciphertext = raw[:12], raw[12:]
    return AESGCM(_key()).decrypt(nonce, ciphertext, None)


def delete_object(object_key: str) -> bool:
    path = _storage_root() / object_key
    if path.exists():
        path.unlink()
        return True
    return False
