"""Fernet-based encryption primitives for Baton.

Key source priority:
  1. Environment variable BATON_DATA_KEY (base64url Fernet key)
  2. File data/.baton_key (auto-created if missing)

NEVER print or log the key.
Encrypted values carry prefix 'enc:v1:' so plaintext and ciphertext can be told apart.
Decryption failure returns REDACTION_PLACEHOLDER, never crashes.
"""

import os
import re
from pathlib import Path

_ENC_PREFIX = "enc:v1:"
_KEY_ENV = "BATON_DATA_KEY"
_KEY_FILE = Path(__file__).resolve().parent.parent / "data" / ".baton_key"

REDACTION_PLACEHOLDER = "[REDACTED - request access]"


def _load_or_create_key() -> bytes:
    """Load key from env var or key file; create key file if neither exists."""
    env_val = os.environ.get(_KEY_ENV, "").strip()
    if env_val:
        return env_val.encode()

    if _KEY_FILE.exists():
        return _KEY_FILE.read_bytes().strip()

    # Create new key
    from cryptography.fernet import Fernet
    key = Fernet.generate_key()
    _KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    _KEY_FILE.write_bytes(key)
    return key


def get_key() -> bytes:
    """Return the Fernet key bytes. Never print or log this value."""
    return _load_or_create_key()


def encrypt_text(plain: str) -> str:
    """Encrypt plain text, returning an 'enc:v1:...' prefixed string.

    If input already has the prefix (already encrypted), returns it unchanged.
    Empty/None input is returned as-is.
    """
    if not plain:
        return plain
    if isinstance(plain, str) and plain.startswith(_ENC_PREFIX):
        return plain  # idempotent
    try:
        from cryptography.fernet import Fernet
        f = Fernet(get_key())
        token = f.encrypt(plain.encode("utf-8")).decode("ascii")
        return _ENC_PREFIX + token
    except Exception:
        # Fail closed: return placeholder, not plain text
        return REDACTION_PLACEHOLDER


def decrypt_text(token: str) -> str:
    """Decrypt an 'enc:v1:...' prefixed string.

    If input does NOT have the prefix (plain text), returns it unchanged.
    On any decryption failure, returns REDACTION_PLACEHOLDER, never crashes.
    Empty/None input is returned as-is.
    """
    if not token:
        return token
    if not isinstance(token, str):
        return REDACTION_PLACEHOLDER
    if not token.startswith(_ENC_PREFIX):
        return token  # already plain text
    raw_token = token[len(_ENC_PREFIX):]
    try:
        from cryptography.fernet import Fernet
        f = Fernet(get_key())
        return f.decrypt(raw_token.encode("ascii")).decode("utf-8")
    except Exception:
        # Fail closed: return placeholder, never return garbage
        return REDACTION_PLACEHOLDER


def is_encrypted(value: str) -> bool:
    """Return True if the value already carries the enc:v1: prefix."""
    return isinstance(value, str) and value.startswith(_ENC_PREFIX)
