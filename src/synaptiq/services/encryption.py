"""
Encryption utility for sensitive data like API keys.

Uses Fernet symmetric encryption (AES-128-CBC) from the cryptography library.
The encryption key is derived from the application's JWT secret.
"""

import base64
import hashlib
from typing import Optional

from cryptography.fernet import Fernet


def _derive_key(secret: str) -> bytes:
    """Derive a 32-byte Fernet key from an arbitrary secret string."""
    digest = hashlib.sha256(secret.encode()).digest()
    return base64.urlsafe_b64encode(digest)


def _get_fernet() -> Fernet:
    from config.settings import get_settings
    settings = get_settings()
    key = _derive_key(settings.jwt_secret_key)
    return Fernet(key)


def encrypt_api_key(plaintext: str) -> str:
    """Encrypt an API key and return the ciphertext as a URL-safe base64 string."""
    if not plaintext:
        return ""
    f = _get_fernet()
    return f.encrypt(plaintext.encode()).decode()


def decrypt_api_key(ciphertext: str) -> str:
    """Decrypt an API key from its ciphertext."""
    if not ciphertext:
        return ""
    f = _get_fernet()
    return f.decrypt(ciphertext.encode()).decode()


def mask_api_key(key: str) -> str:
    """Return a masked version of the key for display (e.g. sk-...abcd)."""
    if not key or len(key) < 8:
        return "****"
    return f"{key[:4]}...{key[-4:]}"
