"""Authentication and role-based access control for Baton.

Provides salted pbkdf2_hmac password verification, brute-force lockout after
5 consecutive failed attempts for 60 seconds, and user role metadata.
"""

import hashlib
import hmac
import os
import re
import time
import uuid
from typing import Optional, Tuple, Dict, Any, List


# ── Salted PBKDF2 Hashes for Demo Accounts ─────────────────────────────────────
# Salt and hash generated via hashlib.pbkdf2_hmac('sha256', password, salt, 100000)
ACCOUNTS: Dict[str, Dict[str, str]] = {
    "manager": {
        "username": "manager",
        "name": "Manager",
        "role": "Manager",
        "org_id": "default_org",
        "org_type": "company",
        "salt": "d17eed00a5458f8aa40d2adfbdb4c902",
        "hash": "b5ce8cbe91bf02fbbcce797a199e05ae88c083488cc4af941bbf91f0c5a84882",
    },
    "sarah": {
        "username": "sarah",
        "name": "Sarah Chen",
        "role": "Employee",
        "org_id": "default_org",
        "org_type": "company",
        "salt": "0a44c42cdda15d0669fede6a38cd6419",
        "hash": "9f82ce872f5320d0b08389b2891c57f688964bb30b22434701dbf2ffdce90f3d",
    },
    "marcus": {
        "username": "marcus",
        "name": "Marcus Vance",
        "role": "Successor",
        "org_id": "default_org",
        "org_type": "company",
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


def hash_password(password: str) -> Tuple[str, str]:
    """Generate random 16-byte salt and pbkdf2_hmac sha256 hash (100k iterations)."""
    salt = os.urandom(16).hex()
    computed = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt),
        100000
    ).hex()
    return salt, computed


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


def authenticate(username: str, password: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """Authenticate username and password with constant-time check and lockout."""
    if is_locked():
        sec = get_lockout_remaining()
        return False, f"Login temporarily locked due to 5 wrong attempts. Please wait {sec} second(s).", None

    clean_user = (username or "").strip().lower()
    clean_pass = password or ""

    if not clean_user or not clean_pass:
        return False, "Username and password cannot be empty.", None

    # 1. First check SQLite dynamic users table
    try:
        import utils.store as store
        store._init_db()
        with store._db() as con:
            row = con.execute(
                "SELECT id, username, name, role, org_id, org_type, salt, hash FROM users WHERE LOWER(username) = ?",
                (clean_user,)
            ).fetchone()
            if row and verify_password(row["salt"], row["hash"], clean_pass):
                record_successful_login()
                return True, "Login successful", {
                    "id": row["id"],
                    "username": row["username"],
                    "name": row["name"],
                    "role": row["role"],
                    "org_id": row["org_id"],
                    "org_type": row["org_type"],
                }
    except Exception:
        pass

    # 2. Fallback to hardcoded ACCOUNTS dict (for demo/offline/mock compatibility)
    user_record = ACCOUNTS.get(clean_user)
    if user_record and verify_password(user_record["salt"], user_record["hash"], clean_pass):
        record_successful_login()
        return True, "Login successful", {
            "id": user_record["username"],
            "username": user_record["username"],
            "name": user_record["name"],
            "role": user_record["role"],
            "org_id": user_record.get("org_id", "default_org"),
            "org_type": user_record.get("org_type", "company"),
        }

    # Wrong credentials
    lock_secs = record_failed_attempt()
    if lock_secs > 0:
        return False, f"Login locked for 60 seconds after 5 wrong attempts.", None

    rem = 5 - _LOGIN_STATE["failed_attempts"]
    return False, f"Invalid username or password. {rem} attempt(s) remaining before lockout.", None


def logout(session_state):
    """Clear login, role, and org keys from session state, leaving project state intact."""
    login_keys = [
        "authenticated",
        "auth_username",
        "auth_role",
        "auth_name",
        "auth_org_id",
        "auth_org_type",
        "auth_org_name",
    ]
    for k in login_keys:
        session_state.pop(k, None)
    session_state["authenticated"] = False


def authenticate_demo(username: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """Authenticate a predefined demo account without requiring a password."""
    clean_user = (username or "").strip().lower()
    if clean_user in ("manager", "sarah", "marcus") and clean_user in ACCOUNTS:
        record_successful_login()
        user_record = ACCOUNTS[clean_user]
        return True, "Demo login successful", {
            "id": user_record["username"],
            "username": user_record["username"],
            "name": user_record["name"],
            "role": user_record["role"],
            "org_id": user_record.get("org_id", "default_org"),
            "org_type": user_record.get("org_type", "company"),
        }
    return False, "Unauthorized demo account access.", None


def register_organization_and_leader(
    org_name: str,
    org_type: str,
    username: str,
    password: str,
    full_name: str,
    project_name: str = "",
) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """Register a new student team or company, its team leader/manager, and initial project."""
    import utils.store as store

    clean_org_name = (org_name or "").strip()
    if not clean_org_name or len(clean_org_name) < 2:
        return False, "Organization or team name must be at least 2 characters.", None

    if org_type not in ("student_team", "company"):
        return False, "Organization type must be 'student_team' or 'company'.", None

    clean_user = (username or "").strip().lower()
    if not re.match(r"^[a-zA-Z0-9_-]{3,30}$", clean_user):
        return False, "Username must be 3-30 alphanumeric characters, hyphens or underscores.", None

    if clean_user in ACCOUNTS:
        return False, f"Username '{clean_user}' is reserved for demo accounts. Please choose another.", None

    if not password or len(password) < 6:
        return False, "Password must be at least 6 characters.", None

    clean_name = (full_name or "").strip() or clean_user

    store._init_db()
    now_ts = time.strftime("%Y-%m-%d %H:%M:%S")
    salt, p_hash = hash_password(password)

    org_id = f"org_{str(uuid.uuid4())[:8]}"
    project_id = f"proj_{str(uuid.uuid4())[:8]}"
    proj_title = (project_name or "").strip() or f"{clean_org_name} Project"

    try:
        with store._db() as con:
            # Check if username exists
            existing = con.execute("SELECT 1 FROM users WHERE LOWER(username) = ?", (clean_user,)).fetchone()
            if existing:
                return False, f"Username '{clean_user}' is already taken.", None

            con.execute(
                "INSERT INTO organizations(id, name, org_type, created_at) VALUES (?, ?, ?, ?)",
                (org_id, clean_org_name, org_type, now_ts)
            )
            con.execute(
                "INSERT INTO projects(id, name, org_id, description, created_at) VALUES (?, ?, ?, ?, ?)",
                (project_id, proj_title, org_id, f"Initial project for {clean_org_name}", now_ts)
            )
            con.execute(
                """INSERT INTO users(id, username, name, role, org_id, org_type, salt, hash, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (clean_user, clean_user, clean_name, "Manager", org_id, org_type, salt, p_hash, now_ts)
            )
            con.execute(
                "INSERT OR IGNORE INTO members(id, username, name, role, joined_at) VALUES (?, ?, ?, ?, ?)",
                (clean_user, clean_user, clean_name, "Manager", now_ts)
            )

        user_data = {
            "id": clean_user,
            "username": clean_user,
            "name": clean_name,
            "role": "Manager",
            "org_id": org_id,
            "org_type": org_type,
            "org_name": clean_org_name,
            "project_id": project_id,
        }
        return True, "Registration successful", user_data
    except Exception as e:
        return False, f"Registration failed: {e}", None


def create_member_account(
    creator_user: Dict[str, Any],
    username: str,
    password: str,
    full_name: str,
    role: str,
) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """Create a member or employee account within the creator's organization."""
    import utils.store as store

    if not creator_user or creator_user.get("role") != "Manager":
        return False, "Only Team Leaders and Managers can create member accounts.", None

    clean_user = (username or "").strip().lower()
    if not re.match(r"^[a-zA-Z0-9_-]{3,30}$", clean_user):
        return False, "Username must be 3-30 alphanumeric characters, hyphens or underscores.", None

    if clean_user in ACCOUNTS:
        return False, f"Username '{clean_user}' is reserved.", None

    if not password or len(password) < 6:
        return False, "Password must be at least 6 characters.", None

    if role not in ("Employee", "Successor"):
        return False, "Role must be 'Employee' (Contributor) or 'Successor' (New Joiner).", None

    clean_name = (full_name or "").strip() or clean_user
    org_id = creator_user.get("org_id", "default_org")
    org_type = creator_user.get("org_type", "company")

    store._init_db()
    now_ts = time.strftime("%Y-%m-%d %H:%M:%S")
    salt, p_hash = hash_password(password)

    try:
        with store._db() as con:
            existing = con.execute("SELECT 1 FROM users WHERE LOWER(username) = ?", (clean_user,)).fetchone()
            if existing:
                return False, f"Username '{clean_user}' is already taken.", None

            con.execute(
                """INSERT INTO users(id, username, name, role, org_id, org_type, salt, hash, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (clean_user, clean_user, clean_name, role, org_id, org_type, salt, p_hash, now_ts)
            )
            con.execute(
                "INSERT OR IGNORE INTO members(id, username, name, role, joined_at) VALUES (?, ?, ?, ?, ?)",
                (clean_user, clean_user, clean_name, role, now_ts)
            )

        new_user = {
            "id": clean_user,
            "username": clean_user,
            "name": clean_name,
            "role": role,
            "org_id": org_id,
            "org_type": org_type,
        }
        return True, "Member account created successfully.", new_user
    except Exception as e:
        return False, f"Account creation failed: {e}", None


def list_org_users(org_id: str) -> List[Dict[str, Any]]:
    """List all users belonging to an organization or team."""
    import utils.store as store
    store._init_db()
    try:
        with store._db() as con:
            rows = con.execute(
                "SELECT id, username, name, role, org_id, org_type, created_at FROM users WHERE org_id = ? ORDER BY created_at ASC",
                (org_id,)
            ).fetchall()
            return [dict(r) for r in rows]
    except Exception:
        return []


