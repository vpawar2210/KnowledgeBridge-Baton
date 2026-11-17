"""Shared project state persistence for Baton.

Storage backend: SQLite (data/baton.db) with WAL mode.
Every change is a targeted row-level transaction; no full state rewrites.
Public function signatures are identical to the JSON-backed version so app.py
needs only minor updates.
"""

import copy
import json
import os
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_FILE  = DATA_DIR / "baton.db"
STATE_FILE = DATA_DIR / "project_state.json"   # kept for migration reference
UPLOADS_DIR = DATA_DIR / "uploads"

# ── keys whose values are stored as JSON blobs in the kv table ──────────────
_KV_KEYS = [
    "knowledge_profile",
    "employee_name",
    "project_role",
    "employee_verifications",
    "employee_gap_answers",
    "employee_tribal_knowledge",
    "approvals",
    "corrections",
    "manager_handover",
    "newhire_handover",
    "employee_handover",
    "acknowledgement",
    "all_sources",
    "analyses_run",
    "handovers_run",
    "successor_notes",
]

# Full list that load_into_session / save_project_state understand
PROJECT_KEYS = _KV_KEYS + [
    "action_history",
    "notifications",
    "access_requests",
    "members",
    "grants",
    "confidential_files",
]


# ═══════════════════════════════════════════════════════════════════════════════
# DB CONNECTION
# ═══════════════════════════════════════════════════════════════════════════════

def ensure_data_dir() -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR


@contextmanager
def _db(timeout: float = 5.0):
    """Yield a SQLite connection with WAL, FK enforcement and busy timeout."""
    ensure_data_dir()
    con = sqlite3.connect(str(DB_FILE), timeout=timeout,
                          check_same_thread=False)
    con.row_factory = sqlite3.Row
    try:
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA foreign_keys=ON")
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


# ═══════════════════════════════════════════════════════════════════════════════
# SCHEMA
# ═══════════════════════════════════════════════════════════════════════════════

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS kv (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL DEFAULT 'null'
);

CREATE TABLE IF NOT EXISTS members (
    id          TEXT PRIMARY KEY,
    username    TEXT NOT NULL,
    name        TEXT NOT NULL DEFAULT '',
    role        TEXT NOT NULL DEFAULT 'Successor',
    joined_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS grants (
    member_id   TEXT NOT NULL,
    grant_type  TEXT NOT NULL,
    PRIMARY KEY (member_id, grant_type)
);

CREATE TABLE IF NOT EXISTS notifications (
    id          TEXT PRIMARY KEY,
    to_id       TEXT NOT NULL,
    kind        TEXT NOT NULL DEFAULT '',
    message     TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL,
    read        INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_notif_to ON notifications(to_id);

CREATE TABLE IF NOT EXISTS access_requests (
    id               TEXT PRIMARY KEY,
    requester_id     TEXT NOT NULL,
    requester_name   TEXT NOT NULL DEFAULT '',
    requester_role   TEXT NOT NULL DEFAULT '',
    type             TEXT NOT NULL,
    reason           TEXT NOT NULL DEFAULT '',
    status           TEXT NOT NULL DEFAULT 'pending',
    created_at       TEXT NOT NULL,
    decided_at       TEXT,
    decided_by       TEXT,
    decision_comment TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    who         TEXT NOT NULL DEFAULT '',
    action      TEXT NOT NULL DEFAULT '',
    reason      TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS files (
    id              TEXT PRIMARY KEY,
    original_name   TEXT NOT NULL,
    stored_name     TEXT NOT NULL,
    classification  TEXT NOT NULL DEFAULT 'normal',
    owner_id        TEXT NOT NULL DEFAULT '',
    owner_name      TEXT NOT NULL DEFAULT '',
    size_bytes      INTEGER NOT NULL DEFAULT 0,
    sha256          TEXT NOT NULL DEFAULT '',
    extracted_text  TEXT,
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS confidential_meta (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    size_bytes      INTEGER NOT NULL DEFAULT 0,
    uploaded_by     TEXT NOT NULL DEFAULT '',
    uploaded_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS gap_answers (
    id            TEXT PRIMARY KEY,
    gap_id        TEXT NOT NULL,
    question_text TEXT NOT NULL,
    answer_text   TEXT NOT NULL,
    grade         TEXT NOT NULL DEFAULT 'ATTESTED',
    status        TEXT NOT NULL,
    author        TEXT NOT NULL DEFAULT '',
    created_at    TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_gap_answers_gap_id ON gap_answers(gap_id);
"""


def _ensure_schema(con: sqlite3.Connection) -> None:
    con.executescript(_SCHEMA_SQL)


def _init_db() -> None:
    with _db() as con:
        _ensure_schema(con)


# ═══════════════════════════════════════════════════════════════════════════════
# MIGRATION  (JSON → SQLite, runs once)
# ═══════════════════════════════════════════════════════════════════════════════

def _migrate_from_json() -> Optional[str]:
    """
    If baton.db is new (no kv rows) and project_state.json exists, import it.
    Returns a notice string or None.
    """
    if not STATE_FILE.exists():
        return None

    # Check if already migrated
    with _db() as con:
        _ensure_schema(con)
        row = con.execute("SELECT COUNT(*) FROM kv").fetchone()
        if row[0] > 0:
            return None   # already has data
        # Also check members
        row2 = con.execute("SELECT COUNT(*) FROM members").fetchone()
        if row2[0] > 0:
            return None

    # Load JSON
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return "Project state file was corrupted. Starting with empty state."
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return "Project state file was corrupted. Starting with empty state."

    # Import
    with _db() as con:
        _ensure_schema(con)

        # kv keys
        for key in _KV_KEYS:
            val = data.get(key)
            con.execute(
                "INSERT OR REPLACE INTO kv(key,value) VALUES(?,?)",
                (key, json.dumps(val, default=str))
            )

        # members
        for m in data.get("members", []):
            con.execute(
                "INSERT OR IGNORE INTO members(id,username,name,role,joined_at) VALUES(?,?,?,?,?)",
                (m.get("id") or m.get("username",""),
                 m.get("username",""),
                 m.get("name",""),
                 m.get("role","Successor"),
                 m.get("joined_at", time.strftime("%Y-%m-%d %H:%M:%S")))
            )

        # grants
        for member_id, grant_list in data.get("grants", {}).items():
            for g in (grant_list or []):
                con.execute(
                    "INSERT OR IGNORE INTO grants(member_id,grant_type) VALUES(?,?)",
                    (member_id, g)
                )

        # notifications
        for n in data.get("notifications", []):
            con.execute(
                "INSERT OR IGNORE INTO notifications(id,to_id,kind,message,created_at,read) VALUES(?,?,?,?,?,?)",
                (n.get("id", str(uuid.uuid4())[:8]),
                 n.get("to",""),
                 n.get("kind",""),
                 n.get("message",""),
                 n.get("created_at", time.strftime("%Y-%m-%d %H:%M:%S")),
                 1 if n.get("read") else 0)
            )

        # access_requests
        for r in data.get("access_requests", []):
            con.execute(
                """INSERT OR IGNORE INTO access_requests
                   (id,requester_id,requester_name,requester_role,type,reason,
                    status,created_at,decided_at,decided_by,decision_comment)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (r.get("id", str(uuid.uuid4())[:8]),
                 r.get("requester_id",""),
                 r.get("requester_name",""),
                 r.get("requester_role",""),
                 r.get("type",""),
                 r.get("reason",""),
                 r.get("status","pending"),
                 r.get("created_at", time.strftime("%Y-%m-%d %H:%M:%S")),
                 r.get("decided_at"),
                 r.get("decided_by"),
                 r.get("decision_comment",""))
            )

        # audit_log
        for entry in data.get("action_history", []):
            con.execute(
                "INSERT INTO audit_log(who,action,reason,created_at) VALUES(?,?,?,?)",
                (entry.get("who",""),
                 entry.get("action",""),
                 entry.get("reason",""),
                 entry.get("timestamp", time.strftime("%Y-%m-%d %H:%M:%S")))
            )

        # confidential_files metadata only (no bytes stored in old JSON)
        for cf in data.get("confidential_files", []):
            cf_id = cf.get("id", str(uuid.uuid4())[:8])
            con.execute(
                "INSERT OR IGNORE INTO confidential_meta(id,name,size_bytes,uploaded_by,uploaded_at) VALUES(?,?,?,?,?)",
                (cf_id,
                 cf.get("name",""),
                 cf.get("size", 0),
                 cf.get("uploaded_by",""),
                 cf.get("uploaded_at", time.strftime("%Y-%m-%d %H:%M:%S")))
            )

    # Verify row counts match
    with _db() as con:
        kv_count = con.execute("SELECT COUNT(*) FROM kv").fetchone()[0]
        member_count = con.execute("SELECT COUNT(*) FROM members").fetchone()[0]

    expected_members = len(data.get("members", []))
    notice = None
    if kv_count < len(_KV_KEYS) or member_count < expected_members:
        notice = "Migration from project_state.json completed with warnings. Some rows may be missing."
    else:
        notice = None
        # Rename old file
        bak = STATE_FILE.parent / (STATE_FILE.name + ".bak")
        try:
            STATE_FILE.rename(bak)
        except Exception:
            pass

    return notice


# ═══════════════════════════════════════════════════════════════════════════════
# READ HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _read_kv(con: sqlite3.Connection, key: str) -> Any:
    row = con.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
    if row is None:
        return None
    try:
        return json.loads(row[0])
    except Exception:
        return None


def _read_all_kv(con: sqlite3.Connection) -> Dict[str, Any]:
    rows = con.execute("SELECT key,value FROM kv").fetchall()
    result = {}
    for r in rows:
        try:
            result[r["key"]] = json.loads(r["value"])
        except Exception:
            result[r["key"]] = None
    return result


def _read_members(con: sqlite3.Connection) -> List[Dict[str, Any]]:
    rows = con.execute("SELECT id,username,name,role,joined_at FROM members").fetchall()
    return [dict(r) for r in rows]


def _read_grants(con: sqlite3.Connection) -> Dict[str, List[str]]:
    rows = con.execute("SELECT member_id, grant_type FROM grants").fetchall()
    result: Dict[str, List[str]] = {}
    for r in rows:
        result.setdefault(r["member_id"], []).append(r["grant_type"])
    return result


def _read_notifications(con: sqlite3.Connection) -> List[Dict[str, Any]]:
    rows = con.execute(
        "SELECT id,to_id,kind,message,created_at,read FROM notifications ORDER BY created_at"
    ).fetchall()
    out = []
    for r in rows:
        out.append({
            "id": r["id"],
            "to": r["to_id"],
            "kind": r["kind"],
            "message": r["message"],
            "created_at": r["created_at"],
            "read": bool(r["read"]),
        })
    return out


def _read_access_requests(con: sqlite3.Connection) -> List[Dict[str, Any]]:
    rows = con.execute(
        """SELECT id,requester_id,requester_name,requester_role,type,reason,
                  status,created_at,decided_at,decided_by,decision_comment
           FROM access_requests ORDER BY created_at"""
    ).fetchall()
    return [dict(r) for r in rows]


def _read_action_history(con: sqlite3.Connection) -> List[Dict[str, Any]]:
    rows = con.execute(
        "SELECT who,action,reason,created_at as timestamp FROM audit_log ORDER BY id"
    ).fetchall()
    return [dict(r) for r in rows]


def _read_confidential_files(con: sqlite3.Connection) -> List[Dict[str, Any]]:
    rows = con.execute(
        "SELECT id,name,size_bytes as size,uploaded_by,uploaded_at FROM confidential_meta ORDER BY uploaded_at"
    ).fetchall()
    result = []
    uploads_dir = Path(__file__).resolve().parent.parent / "data" / "uploads"
    if not uploads_dir.exists():
        uploads_dir = Path("data/uploads")
    for r in rows:
        d = dict(r)
        doc_id = d.get("id", "")
        content = None
        if uploads_dir.exists() and doc_id:
            matches = list(uploads_dir.glob(f"seed_{doc_id}_*")) + list(uploads_dir.glob(f"*{doc_id}*"))
            if matches:
                try:
                    content = matches[0].read_bytes()
                except Exception:
                    content = None
        d["content"] = content
        result.append(d)
    return result


def _assemble_state(con: sqlite3.Connection) -> Dict[str, Any]:
    """Read all tables and assemble into the same dict shape app.py expects."""
    state = get_empty_state()
    kv = _read_all_kv(con)
    for key in _KV_KEYS:
        if key in kv and kv[key] is not None:
            state[key] = kv[key]
    state["members"]           = _read_members(con)
    state["grants"]            = _read_grants(con)
    state["notifications"]     = _read_notifications(con)
    state["access_requests"]   = _read_access_requests(con)
    state["action_history"]    = _read_action_history(con)
    state["confidential_files"] = _read_confidential_files(con)
    return state


# ═══════════════════════════════════════════════════════════════════════════════
# EMPTY / DEFAULT STATE
# ═══════════════════════════════════════════════════════════════════════════════

def get_empty_state() -> Dict[str, Any]:
    return {
        "knowledge_profile": None,
        "employee_name": "",
        "project_role": "",
        "employee_verifications": {},
        "employee_gap_answers": {},
        "employee_tribal_knowledge": [],
        "approvals": {},
        "corrections": {},
        "manager_handover": None,
        "newhire_handover": None,
        "employee_handover": None,
        "action_history": [],
        "acknowledgement": None,
        "all_sources": [],
        "analyses_run": 0,
        "handovers_run": 0,
        "notifications": [],
        "access_requests": [],
        "members": [],
        "grants": {},
        "confidential_files": [],
        "successor_notes": [],
    }


# ═══════════════════════════════════════════════════════════════════════════════
# PUBLIC API  (same names as old store.py)
# ═══════════════════════════════════════════════════════════════════════════════

def load_project_state() -> Tuple[Dict[str, Any], Optional[str]]:
    """Return (state_dict, notice). Initialises DB and runs migration if needed."""
    try:
        _init_db()
        notice = _migrate_from_json()
        with _db() as con:
            state = _assemble_state(con)
        return state, notice
    except Exception as exc:
        return get_empty_state(), f"Database error on load: {exc}"


def load_into_session(session_state) -> Optional[str]:
    """Load all state from SQLite into Streamlit session_state. Returns notice."""
    data, notice = load_project_state()
    for key in PROJECT_KEYS:
        if key in data:
            if hasattr(session_state, "__setitem__"):
                session_state[key] = data[key]
            elif hasattr(session_state, key):
                setattr(session_state, key, data[key])
    if hasattr(session_state, "__setitem__"):
        session_state["_last_disk_snapshot"] = copy.deepcopy(data)
    return notice


def save_project_state(source, keys: Optional[List[str]] = None) -> bool:
    """
    Persist changed kv keys from session_state to SQLite.
    Only kv-table keys are handled here; structured tables (members, grants,
    notifications, access_requests, audit_log) are always written via
    modify_project_state / the targeted helpers.
    """
    try:
        if keys is None:
            snapshot = {}
            if hasattr(source, "get"):
                snapshot = source.get("_last_disk_snapshot") or {}
            keys_to_update = []
            for k in _KV_KEYS:
                src_val = source.get(k) if hasattr(source, "get") else getattr(source, k, None)
                snap_val = snapshot.get(k)
                if src_val != snap_val:
                    keys_to_update.append(k)
        else:
            keys_to_update = [k for k in keys if k in _KV_KEYS]

        if not keys_to_update:
            return True

        with _db() as con:
            _ensure_schema(con)
            for k in keys_to_update:
                val = source.get(k) if hasattr(source, "get") else getattr(source, k, None)
                con.execute(
                    "INSERT OR REPLACE INTO kv(key,value) VALUES(?,?)",
                    (k, json.dumps(val, default=str))
                )
        return True
    except Exception:
        return False


def modify_project_state(modifier_fn: Callable[[Dict[str, Any]], Any],
                         session_state: Any = None) -> Dict[str, Any]:
    """
    Load full state, apply modifier_fn(state), write only changed rows back.
    Keeps backward compatibility: modifier_fn receives a plain dict and may
    mutate any key. Structured table changes are detected and written back.
    """
    _init_db()
    with _db() as con:
        _ensure_schema(con)
        state = _assemble_state(con)
        old_state = copy.deepcopy(state)

        modifier_fn(state)

        # --- kv keys ---
        for key in _KV_KEYS:
            if state.get(key) != old_state.get(key):
                con.execute(
                    "INSERT OR REPLACE INTO kv(key,value) VALUES(?,?)",
                    (key, json.dumps(state.get(key), default=str))
                )

        # --- members (new rows only) ---
        old_member_ids = {m["id"] for m in old_state.get("members", [])}
        for m in state.get("members", []):
            mid = m.get("id") or m.get("username", "")
            if mid not in old_member_ids:
                con.execute(
                    "INSERT OR IGNORE INTO members(id,username,name,role,joined_at) VALUES(?,?,?,?,?)",
                    (mid, m.get("username",""), m.get("name",""),
                     m.get("role","Successor"),
                     m.get("joined_at", time.strftime("%Y-%m-%d %H:%M:%S")))
                )

        # --- grants (full replace for changed members) ---
        new_grants: Dict[str, List[str]] = state.get("grants", {})
        old_grants: Dict[str, List[str]] = old_state.get("grants", {})
        for member_id, grant_list in new_grants.items():
            if set(grant_list) != set(old_grants.get(member_id, [])):
                con.execute("DELETE FROM grants WHERE member_id=?", (member_id,))
                for g in grant_list:
                    con.execute(
                        "INSERT OR IGNORE INTO grants(member_id,grant_type) VALUES(?,?)",
                        (member_id, g)
                    )
        # Revoked grants for members not in new_grants
        for member_id in old_grants:
            if member_id not in new_grants:
                con.execute("DELETE FROM grants WHERE member_id=?", (member_id,))

        # --- notifications (append new) ---
        old_notif_ids = {n["id"] for n in old_state.get("notifications", [])}
        for n in state.get("notifications", []):
            if n.get("id") not in old_notif_ids:
                con.execute(
                    "INSERT OR IGNORE INTO notifications(id,to_id,kind,message,created_at,read) VALUES(?,?,?,?,?,?)",
                    (n.get("id", str(uuid.uuid4())[:8]),
                     n.get("to",""),
                     n.get("kind",""),
                     n.get("message",""),
                     n.get("created_at", time.strftime("%Y-%m-%d %H:%M:%S")),
                     1 if n.get("read") else 0)
                )
            else:
                # update read flag if changed
                old_n = next((x for x in old_state.get("notifications", []) if x["id"] == n["id"]), None)
                if old_n and old_n.get("read") != n.get("read"):
                    con.execute(
                        "UPDATE notifications SET read=? WHERE id=?",
                        (1 if n.get("read") else 0, n["id"])
                    )

        # --- access_requests (append new + update status) ---
        old_req_ids = {r["id"] for r in old_state.get("access_requests", [])}
        for r in state.get("access_requests", []):
            rid = r.get("id", str(uuid.uuid4())[:8])
            if rid not in old_req_ids:
                con.execute(
                    """INSERT OR IGNORE INTO access_requests
                       (id,requester_id,requester_name,requester_role,type,reason,
                        status,created_at,decided_at,decided_by,decision_comment)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                    (rid,
                     r.get("requester_id",""),
                     r.get("requester_name",""),
                     r.get("requester_role",""),
                     r.get("type",""),
                     r.get("reason",""),
                     r.get("status","pending"),
                     r.get("created_at", time.strftime("%Y-%m-%d %H:%M:%S")),
                     r.get("decided_at"),
                     r.get("decided_by"),
                     r.get("decision_comment",""))
                )
            else:
                old_r = next((x for x in old_state.get("access_requests", []) if x["id"] == rid), None)
                if old_r and (old_r.get("status") != r.get("status") or
                              old_r.get("decided_at") != r.get("decided_at")):
                    con.execute(
                        """UPDATE access_requests
                           SET status=?,decided_at=?,decided_by=?,decision_comment=?
                           WHERE id=?""",
                        (r.get("status","pending"),
                         r.get("decided_at"),
                         r.get("decided_by"),
                         r.get("decision_comment",""),
                         rid)
                    )

        # --- audit_log / action_history (append new) ---
        old_len = len(old_state.get("action_history", []))
        new_entries = state.get("action_history", [])[old_len:]
        for entry in new_entries:
            con.execute(
                "INSERT INTO audit_log(who,action,reason,created_at) VALUES(?,?,?,?)",
                (entry.get("who",""),
                 entry.get("action",""),
                 entry.get("reason",""),
                 entry.get("timestamp", time.strftime("%Y-%m-%d %H:%M:%S")))
            )

        # --- confidential_meta (append new) ---
        old_cf_ids = {cf.get("id","") for cf in old_state.get("confidential_files", [])}
        for cf in state.get("confidential_files", []):
            cf_id = cf.get("id","")
            if cf_id and cf_id not in old_cf_ids:
                con.execute(
                    "INSERT OR IGNORE INTO confidential_meta(id,name,size_bytes,uploaded_by,uploaded_at) VALUES(?,?,?,?,?)",
                    (cf_id,
                     cf.get("name",""),
                     cf.get("size", 0),
                     cf.get("uploaded_by",""),
                     cf.get("uploaded_at", time.strftime("%Y-%m-%d %H:%M:%S")))
                )

    # Sync back to session_state
    if session_state is not None:
        for k in PROJECT_KEYS:
            if k in state:
                if hasattr(session_state, "__setitem__"):
                    session_state[k] = state[k]
                elif hasattr(session_state, k):
                    setattr(session_state, k, state[k])
        if hasattr(session_state, "__setitem__"):
            session_state["_last_disk_snapshot"] = copy.deepcopy(state)

    return state


def log_audit_entry(session_state, who: str, action: str, reason: str = "") -> None:
    """Append an audit log entry directly to the audit_log table."""
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    try:
        with _db() as con:
            _ensure_schema(con)
            con.execute(
                "INSERT INTO audit_log(who,action,reason,created_at) VALUES(?,?,?,?)",
                (who, action, reason, ts)
            )
        # Also update session_state action_history list
        if session_state is not None and hasattr(session_state, "get"):
            hist = session_state.get("action_history")
            if not isinstance(hist, list):
                hist = []
            hist.append({"who": who, "action": action, "reason": reason, "timestamp": ts})
            if hasattr(session_state, "__setitem__"):
                session_state["action_history"] = hist
    except Exception:
        pass


# ── Targeted notification mark-read (used by notifications page) ─────────────

def mark_notifications_read(user_id: str, session_state=None) -> None:
    """Mark all notifications for user_id as read in DB and session_state."""
    with _db() as con:
        _ensure_schema(con)
        con.execute(
            "UPDATE notifications SET read=1 WHERE to_id=? AND read=0",
            (user_id,)
        )
    if session_state is not None and hasattr(session_state, "get"):
        notifs = session_state.get("notifications", [])
        for n in notifs:
            if n.get("to") == user_id:
                n["read"] = True


# ── File registry (Phase 4) ───────────────────────────────────────────────────

def register_file(original_name: str, stored_name: str, classification: str,
                  owner_id: str, owner_name: str, size_bytes: int,
                  sha256: str, extracted_text: Optional[str]) -> str:
    """Insert a row into the files table. Returns the new file id."""
    file_id = str(uuid.uuid4())
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    with _db() as con:
        _ensure_schema(con)
        con.execute(
            """INSERT INTO files
               (id,original_name,stored_name,classification,owner_id,owner_name,
                size_bytes,sha256,extracted_text,created_at)
               VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (file_id, original_name, stored_name, classification,
             owner_id, owner_name, size_bytes, sha256,
             extracted_text, ts)
        )
    return file_id


def register_confidential_meta(name: str, size_bytes: int,
                                uploaded_by: str) -> str:
    """Insert a row into confidential_meta. Returns the new id."""
    cf_id = str(uuid.uuid4())[:8]
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    with _db() as con:
        _ensure_schema(con)
        con.execute(
            "INSERT INTO confidential_meta(id,name,size_bytes,uploaded_by,uploaded_at) VALUES(?,?,?,?,?)",
            (cf_id, name, size_bytes, uploaded_by, ts)
        )
    return cf_id


# ═══════════════════════════════════════════════════════════════════════════════
# GAP INTERVIEW ENGINE (ATTESTED leaver memory)
# ═══════════════════════════════════════════════════════════════════════════════

_CTRL_CHARS = set(range(0, 32)) - {9, 10, 13}  # allow tab, LF, CR

def _clean_answer_text(text: str) -> str:
    """Strip control characters and limit to 2000 characters."""
    if not text:
        return ""
    cleaned = "".join(ch for ch in text if ord(ch) not in _CTRL_CHARS)
    return cleaned.strip()[:2000]


def add_gap_answer(
    gap_id: str,
    question_text: str,
    answer_text: str,
    status: str = "answered",
    author: str = "Sarah Chen",
    grade: str = "ATTESTED"
) -> Dict[str, Any]:
    """Store or update a gap answer with strict ATTESTED grade.
    
    Rules:
    - Grade is ALWAYS 'ATTESTED', never 'VERIFIED' (even if 'VERIFIED' is passed).
    - Saving the same gap again UPDATES it (no duplicate rows).
    - Rejects empty or whitespace-only answers when status == 'answered'.
    - Limits answer to 2000 characters and strips control characters.
    """
    valid_statuses = ("answered", "unknown", "skipped")
    if status not in valid_statuses:
        status = "answered"

    # Enforce strict ATTESTED grade - leaver memory is never source-verified
    enforced_grade = "ATTESTED"

    cleaned_answer = _clean_answer_text(answer_text)

    # Empty/whitespace check for answered status
    if status == "answered":
        if not cleaned_answer:
            raise ValueError("Answer text cannot be empty or whitespace-only.")
        final_answer = cleaned_answer
    else:
        final_answer = cleaned_answer if cleaned_answer else status.capitalize()

    ts = time.strftime("%Y-%m-%d %H:%M:%S")

    with _db() as con:
        _ensure_schema(con)
        # Check if record for this gap_id already exists
        existing = con.execute("SELECT id FROM gap_answers WHERE gap_id = ?", (gap_id,)).fetchone()
        if existing:
            rec_id = existing[0]
            con.execute(
                """UPDATE gap_answers
                   SET question_text = ?, answer_text = ?, grade = ?, status = ?, author = ?, created_at = ?
                   WHERE gap_id = ?""",
                (question_text, final_answer, enforced_grade, status, author, ts, gap_id)
            )
        else:
            rec_id = str(uuid.uuid4())
            con.execute(
                """INSERT INTO gap_answers
                   (id, gap_id, question_text, answer_text, grade, status, author, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (rec_id, gap_id, question_text, final_answer, enforced_grade, status, author, ts)
            )

    return {
        "id": rec_id,
        "gap_id": gap_id,
        "question_text": question_text,
        "answer_text": final_answer,
        "grade": enforced_grade,
        "status": status,
        "author": author,
        "created_at": ts
    }


def list_gap_answers(status: Optional[str] = None) -> List[Dict[str, Any]]:
    """List all stored gap answers, optionally filtered by status ('answered', 'unknown', 'skipped')."""
    with _db() as con:
        _ensure_schema(con)
        if status:
            rows = con.execute(
                """SELECT id, gap_id, question_text, answer_text, grade, status, author, created_at
                   FROM gap_answers WHERE status = ? ORDER BY created_at ASC""",
                (status,)
            ).fetchall()
        else:
            rows = con.execute(
                """SELECT id, gap_id, question_text, answer_text, grade, status, author, created_at
                   FROM gap_answers ORDER BY created_at ASC"""
            ).fetchall()
        return [dict(r) for r in rows]


def gap_progress(total_gaps: Optional[int] = None) -> Dict[str, Any]:
    """Calculate progress of answered gaps.
    
    Returns a dict with:
    - answered: total answered (base pre-answered + interview answered)
    - interview_answered: answered in gap_answers table
    - base_answered: answered in existing employee_gap_answers
    - unknown: count of unknown answers
    - skipped: count of skipped answers
    - total: total number of gaps
    - summary: e.g. '3 of 8 gaps answered'
    """
    with _db() as con:
        _ensure_schema(con)
        row = con.execute("SELECT COUNT(*) FROM gap_answers WHERE status = 'answered'").fetchone()
        interview_answered = row[0] if row else 0

        row_unk = con.execute("SELECT COUNT(*) FROM gap_answers WHERE status = 'unknown'").fetchone()
        unknown_count = row_unk[0] if row_unk else 0

        row_skip = con.execute("SELECT COUNT(*) FROM gap_answers WHERE status = 'skipped'").fetchone()
        skipped_count = row_skip[0] if row_skip else 0

        base_answered = 0
        kv_row = con.execute("SELECT value FROM kv WHERE key = 'employee_gap_answers'").fetchone()
        if kv_row and kv_row[0]:
            try:
                base_data = json.loads(kv_row[0])
                if isinstance(base_data, dict):
                    base_answered = sum(1 for v in base_data.values() if isinstance(v, str) and v.strip())
            except Exception:
                pass

        if total_gaps is not None and total_gaps > 0:
            total = total_gaps
        else:
            open_count = 5
            kp_row = con.execute("SELECT value FROM kv WHERE key = 'knowledge_profile'").fetchone()
            if kp_row and kp_row[0]:
                try:
                    kp = json.loads(kp_row[0])
                    unres = kp.get("unresolved", [])
                    if isinstance(unres, list) and unres:
                        open_count = len(unres)
                except Exception:
                    pass
            total = max(base_answered + open_count, 8)

        total_answered = min(base_answered + interview_answered, total)
        return {
            "answered": total_answered,
            "interview_answered": interview_answered,
            "base_answered": base_answered,
            "unknown": unknown_count,
            "skipped": skipped_count,
            "total": total,
            "summary": f"{total_answered} of {total} gaps answered"
        }


def get_open_gaps() -> List[Dict[str, Any]]:
    """Read open gap items dynamically from existing gap data.
    
    Reads from baton_mock_data.json and knowledge_profile['unresolved'].
    Does NOT hardcode any IDs.
    Excludes gaps that have already been answered (status == 'answered').
    Gaps with status 'unknown' or 'skipped' remain open.
    """
    answered_ids = set()
    answered_questions = set()
    try:
        with _db() as con:
            _ensure_schema(con)
            rows = con.execute("SELECT gap_id, question_text FROM gap_answers WHERE status = 'answered'").fetchall()
            for r in rows:
                if r[0]:
                    answered_ids.add(r[0])
                if r[1]:
                    answered_questions.add(r[1])
            kv_row = con.execute("SELECT value FROM kv WHERE key = 'employee_gap_answers'").fetchone()
            if kv_row and kv_row[0]:
                eg_ans = json.loads(kv_row[0])
                if isinstance(eg_ans, dict):
                    for qk, qv in eg_ans.items():
                        if isinstance(qv, str) and qv.strip():
                            answered_questions.add(qk)
    except Exception:
        pass

    open_gaps = []
    mock_file = BASE_DIR / "seed_data" / "harborline" / "baton_mock_data.json"
    if mock_file.exists():
        try:
            with open(mock_file, "r", encoding="utf-8") as f:
                d = json.load(f)
            questions = d.get("questions", [])
            for q in questions:
                q_id = q.get("id", f"Q-{len(open_gaps)+1:03d}")
                q_text = q.get("question", "")
                if q.get("status") == "open":
                    if q_id not in answered_ids and q_text not in answered_questions:
                        open_gaps.append({
                            "id": q_id,
                            "question": q_text,
                            "source": q.get("source", ""),
                            "why_unknown": "Identified as documentation gap in source materials."
                        })
        except Exception:
            pass

    if not open_gaps:
        try:
            with _db() as con:
                row = con.execute("SELECT value FROM kv WHERE key = 'knowledge_profile'").fetchone()
                if row and row[0]:
                    kp = json.loads(row[0])
                    for i, u in enumerate(kp.get("unresolved", [])):
                        q_text = u.get("question", "")
                        u_id = u.get("id") or u.get("gap_id") or f"GAP-{i+1:03d}"
                        if u_id not in answered_ids and q_text not in answered_questions:
                            open_gaps.append({
                                "id": u_id,
                                "question": q_text,
                                "why_unknown": u.get("why_unknown", "")
                            })
        except Exception:
            pass

    return open_gaps
