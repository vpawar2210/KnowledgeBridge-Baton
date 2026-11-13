"""Authentication and role-based access control for Baton.

Provides salted pbkdf2_hmac password verification, brute-force lockout after
5 consecutive failed attempts for 60 seconds, and user role metadata.
"""

import hashlib
import hmac
import time
from typing import Optional, Tuple, Dict, Any


# ── Salted PBKDF2 Hashes for Demo Accounts ─────────────────────────────────────
# Salt and hash generated via hashlib.pbkdf2_hmac('sha256', password, salt, 100000)
ACCOUNTS: Dict[str, Dict[str, str]] = {
    "manager": {
        "username": "manager",
        "name": "Manager",
        "role": "Manager",
        "salt": "d17eed00a5458f8aa40d2adfbdb4c902",
        "hash": "b5ce8cbe91bf02fbbcce797a199e05ae88c083488cc4af941bbf91f0c5a84882",
    },
    "sarah": {
        "username": "sarah",
        "name": "Sarah Chen",
        "role": "Employee",
        "salt": "0a44c42cdda15d0669fede6a38cd6419",
        "hash": "9f82ce872f5320d0b08389b2891c57f688964bb30b22434701dbf2ffdce90f3d",
    },
    "marcus": {
        "username": "marcus",
        "name": "Marcus Vance",
        "role": "Successor",
        "salt": "54b662239eda38a5a81639215cf82a6b",
        "hash": "11fc9b23af897ae1029b92cc7bb7dbdfed8c68cb260e18efd69f7bc9753e5ba6",
    },
}

# ── Module-level Lockout State ────────────────────────────────────────────────
# Tracks wrong attempts and lockout timestamps
_LOGIN_STATE = {
    "failed_attempts": 0,
    "lockout_until": 0.0,
}


def verify_password(stored_salt_hex: str, stored_hash_hex: str, password: str) -> bool:
    """Compare entered password against salted pbkdf2_hmac hash with hmac.compare_digest."""
    try:
        salt = bytes.fromhex(stored_salt_hex)
        computed = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            100000
        ).hex()
        return hmac.compare_digest(stored_hash_hex, computed)
    except Exception:
        return False


def get_lockout_remaining() -> int:
    """Return remaining seconds of lockout, or 0 if not locked."""
    remaining = int(_LOGIN_STATE["lockout_until"] - time.time())
    return max(0, remaining)


def is_locked() -> bool:
    """Check whether login is currently locked due to failed attempts."""
    return get_lockout_remaining() > 0


def record_failed_attempt() -> int:
    """Increment failed attempts. If reaches 5, locks for 60 seconds. Returns remaining lockout seconds."""
    _LOGIN_STATE["failed_attempts"] += 1
    if _LOGIN_STATE["failed_attempts"] >= 5:
        _LOGIN_STATE["lockout_until"] = time.time() + 60.0
        _LOGIN_STATE["failed_attempts"] = 0
        return 60
    return 0


def record_successful_login():
    """Reset failed attempts and lockout timers."""
    _LOGIN_STATE["failed_attempts"] = 0
    _LOGIN_STATE["lockout_until"] = 0.0


def authenticate(username: str, password: str) -> Tuple[bool, str, Optional[Dict[str, str]]]:
    """Authenticate username and password with constant-time check and lockout."""
    if is_locked():
        sec = get_lockout_remaining()
        return False, f"Login temporarily locked due to 5 wrong attempts. Please wait {sec} second(s).", None

    clean_user = (username or "").strip().lower()
    clean_pass = password or ""

    user_record = ACCOUNTS.get(clean_user)
    if user_record and verify_password(user_record["salt"], user_record["hash"], clean_pass):
        record_successful_login()
        return True, "Login successful", {
            "username": user_record["username"],
            "name": user_record["name"],
            "role": user_record["role"],
        }

    # Wrong credentials
    lock_secs = record_failed_attempt()
    if lock_secs > 0:
        return False, f"Login locked for 60 seconds after 5 wrong attempts.", None

    rem = 5 - _LOGIN_STATE["failed_attempts"]
    return False, f"Invalid username or password. {rem} attempt(s) remaining before lockout.", None


def logout(session_state):
    """Clear only login and role keys from session state, leaving project state intact."""
    login_keys = ["authenticated", "auth_username", "auth_role", "auth_name"]
    for k in login_keys:
        session_state.pop(k, None)
    session_state["authenticated"] = False


def authenticate_demo(username: str) -> Tuple[bool, str, Optional[Dict[str, str]]]:
    """Authenticate a predefined demo account without requiring a password.

    Restricted strictly to predefined synthetic accounts (manager, sarah, marcus).
    Does not bypass authentication for real users.
    """
    clean_user = (username or "").strip().lower()
    if clean_user in ("manager", "sarah", "marcus") and clean_user in ACCOUNTS:
        record_successful_login()
        user_record = ACCOUNTS[clean_user]
        return True, "Demo login successful", {
            "username": user_record["username"],
            "name": user_record["name"],
            "role": user_record["role"],
        }
    return False, "Unauthorized demo account access.", None

