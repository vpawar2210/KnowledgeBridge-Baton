"""Demo data seeding for the Baton Harborline synthetic dataset.

Public API
----------
ensure_demo_database_seeded(force_reset=False, completed=False)
    Write the Harborline demo state into SQLite.
    - force_reset=True  : wipe all tables and re-seed from scratch.
    - completed=True    : load the completed-handover state (all 5 sections
                          approved, manager/newhire/employee handovers generated).
    - completed=False   : default start state (Sarah active, manager pending).
    Idempotent: calling twice without force_reset never creates duplicates.

hydrate_demo_session_state(session_state, user)
    Legacy helper kept for backward compat — calls ensure_demo_database_seeded
    then is a no-op (session hydration happens via load_into_session).

load_completed_handover()
    Force-seed the completed state. Called from app.py audit page.

reset_demo_data()
    Force-seed the start state. Called from app.py audit page.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
DATASET_ROOT = ROOT / "seed_data" / "harborline"
DATASET_PATH = DATASET_ROOT / "baton_mock_data.json"
SEED_FILES_ROOT = DATASET_ROOT / "seed_files"
UPLOADS_DIR = ROOT / "data" / "uploads"
DB_FILE = ROOT / "data" / "baton.db"

# Sentinel KV key
_SEED_KEY = "__demo_seeded__"
_SEED_VAL_START = "harborline_v1_start"
_SEED_VAL_COMPLETE = "harborline_v1_complete"


# ============================================================
# FIXTURE LOADER
# ============================================================

def _load_dataset() -> Dict[str, Any]:
    if not DATASET_PATH.exists():
        raise FileNotFoundError(f"Demo dataset not found: {DATASET_PATH}")
    with DATASET_PATH.open("r", encoding="utf-8") as fh:
        return json.load(fh)


# ============================================================
# DB HELPERS
# ============================================================

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
"""


def _open_db(timeout: float = 10.0) -> sqlite3.Connection:
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(DB_FILE), timeout=timeout, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    return con


def _ensure_schema(con: sqlite3.Connection) -> None:
    con.executescript(_SCHEMA_SQL)
    con.commit()


def _kv_get(con: sqlite3.Connection, key: str) -> Any:
    row = con.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
    if row is None:
        return None
    try:
        return json.loads(row[0])
    except Exception:
        return None


def _kv_set(con: sqlite3.Connection, key: str, value: Any) -> None:
    con.execute(
        "INSERT OR REPLACE INTO kv(key,value) VALUES(?,?)",
        (key, json.dumps(value, default=str, ensure_ascii=False)),
    )


def _wipe_all_tables(con: sqlite3.Connection) -> None:
    for tbl in ("kv", "members", "grants", "notifications",
                "access_requests", "audit_log", "files", "confidential_meta"):
        con.execute(f"DELETE FROM {tbl}")
    con.commit()


# ============================================================
# CONTENT BUILDERS
# ============================================================

def _split_findings(findings: List[Dict[str, Any]]):
    decisions: List[Dict[str, Any]] = []
    risks: List[Dict[str, Any]] = []
    n = len(findings)
    for idx, finding in enumerate(findings):
        source = (finding.get("source_document_id")
                  or finding.get("source_note_id")
                  or "employee_note")
        item = {
            "text": finding.get("summary") or finding.get("title") or "Finding",
            "source": source,
            "source_type": "file" if finding.get("source_document_id") else "note",
            "confidence": (finding.get("confidence") or "medium").upper(),
            "excerpt": finding.get("source_quote") or "",
        }
        if idx < n // 2:
            decisions.append(item)
        else:
            risks.append(item)
    return decisions, risks


def _build_tribal_knowledge(dataset: Dict[str, Any]) -> List[Dict[str, str]]:
    items: List[Dict[str, str]] = []
    for note in dataset.get("employee_notes", []):
        title = note.get("title", "Employee note")
        content = note.get("content", "")
        if note.get("classification") == "confidential":
            category = "Warning"
        elif "reconciliation" in title.lower() or "handover" in title.lower():
            category = "Process"
        else:
            category = "Tip"
        items.append({"category": category, "title": title, "content": content})
    return items


def _build_verifications(decisions: List, risks: List) -> Dict[str, Dict]:
    verif: Dict[str, Dict] = {}
    for idx in range(len(decisions)):
        verif[f"decision_{idx}"] = {
            "status": "Confirmed accurate",
            "note": "Verified against the Harborline synthetic evidence set.",
        }
    for idx in range(len(risks)):
        verif[f"risk_{idx}"] = {
            "status": "Active risk",
            "note": "Pending manager review in the Harborline demo dataset.",
        }
    return verif


def _build_gap_answers(dataset: Dict[str, Any]) -> Dict[str, str]:
    return {
        q["question"]: q["answer"]
        for q in dataset.get("questions", [])
        if q.get("status") == "answered" and q.get("answer")
    }


def _build_unresolved(dataset: Dict[str, Any]) -> List[Dict[str, str]]:
    return [
        {
            "question": q["question"],
            "why_unknown": "This item remains unresolved in the Harborline demo dataset.",
        }
        for q in dataset.get("questions", [])
        if q.get("status") == "open"
    ]


def _build_contacts() -> List[Dict[str, str]]:
    return [
        {"name": "Sarah Chen", "role": "Departing employee", "source": "DOC-TRB-008"},
        {"name": "Manager Demo", "role": "Business approver", "source": "NOT-001"},
        {"name": "Marcus Vance", "role": "Successor / pending handover recipient", "source": "REQ-001"},
        {"name": "Customer Operations", "role": "Support and refund workflow owner", "source": "DOC-REF-004"},
    ]


def _build_dependencies(dataset: Dict[str, Any]) -> List[Dict[str, str]]:
    return [
        {
            "item": doc.get("title", "Document"),
            "description": doc.get("owner", "Owner"),
            "source": doc.get("id", "doc"),
        }
        for doc in dataset.get("files", [])
        if doc.get("classification") == "internal"
    ]


def _build_manager_handover(dataset: Dict[str, Any]) -> str:
    ws = dataset.get("workspace", {}).get("name", "Harborline Platform Operations Handover")
    bf = dataset.get("business_facts", {})
    lines = [
        f"# Manager Handover — {ws}",
        "",
        "## Executive summary",
        "",
        "Sarah Chen departs as platform and customer operations owner. This document summarises the approved handover for management records.",
        "",
        "## Business facts",
        "",
        f"- Access tokens expire after **{bf.get('access_token_lifetime_minutes', 15)} minutes** (sliding TTL).",
        f"- Incident of {bf.get('incident_date', '2026-03-14')}: outage lasted **{bf.get('incident_duration_minutes', 38)} minutes** (connection-pool exhaustion).",
        f"- Default public API rate limit: **{bf.get('default_public_api_limit_requests_per_second', 50)} req/s** per client key.",
        f"- Frontline refund authority ceiling: **INR {bf.get('frontline_goodwill_refund_limit_inr', 500000):,}**; above that, Finance Director approval required.",
        "",
        "## Reviewed and approved sections",
        "",
        "1. Incident and Reliability",
        "2. Security and Access",
        "3. API and Integrations",
        "4. Customer Operations",
        "5. Release and Service Operations",
        "6. Team Knowledge and Unwritten Rules",
        "",
        "## Action items",
        "",
        "- Assign a new primary on-call engineer for platform operations.",
        "- Confirm successor (Marcus Vance) has completed onboarding access review.",
        "- Schedule a 30-day check-in with the successor to validate knowledge transfer.",
        "",
        "## Open questions (unresolved at handover)",
        "",
    ]
    for q in dataset.get("questions", []):
        if q.get("status") == "open":
            lines.append(f"- {q['question']}")
    return "\n".join(lines)


def _build_newhire_handover(dataset: Dict[str, Any]) -> str:
    ws = dataset.get("workspace", {}).get("name", "Harborline Platform Operations Handover")
    bf = dataset.get("business_facts", {})
    lines = [
        f"# Technical Successor Handover — {ws}",
        "",
        "Welcome to Harborline. This document is your technical onboarding guide from Sarah Chen.",
        "",
        "## Critical operational rules",
        "",
    ]
    for rule in bf.get("unwritten_rules", []):
        lines.append(f"- {rule}")
    lines += [
        "",
        "## Key system facts",
        "",
        f"- Access tokens expire after {bf.get('access_token_lifetime_minutes', 15)} minutes; role-claims refresh on the next API call.",
        f"- Public API: {bf.get('default_public_api_limit_requests_per_second', 50)} req/s per client key; burst returns HTTP 429.",
        f"- Refunds up to INR {bf.get('frontline_goodwill_refund_limit_inr', 500000):,} can be approved by frontline agents; above that, Finance Director sign-off is required.",
        "",
        "## Incident of 14 March 2026",
        "",
        "The outage was caused by connection-pool exhaustion during a downstream timeout spike. Duration: 38 minutes. Resolution involved recycling the affected worker pool.",
        "",
        "## Release discipline",
        "",
        "- Severity 1 incidents impose an automatic deployment freeze.",
        "- A rollback must be backed by written evidence before closure.",
        "",
        "## Support escalation sequence",
        "",
        "1. Confirm customer, workspace and request identifier.",
        "2. Check service status before asking the customer to repeat any action.",
        "3. Attach case timeline and relevant evidence before escalating.",
        "",
        "## Answered questions from reconstruction",
        "",
    ]
    for q in dataset.get("questions", []):
        if q.get("status") == "answered" and q.get("answer"):
            lines.append(f"**Q: {q['question']}**")
            lines.append(f"A: {q['answer']}")
            lines.append("")
    return "\n".join(lines)


def _build_employee_handover(dataset: Dict[str, Any]) -> str:
    lines = [
        "# Employee Notes — Sarah Chen | Harborline Platform Operations Handover",
        "",
        "These are my first-person notes to accompany the technical handover.",
        "",
        "## My operational notes",
        "",
    ]
    for note in dataset.get("employee_notes", []):
        lines.append(f"### {note.get('title', 'Note')}")
        lines.append(note.get("content", ""))
        lines.append("")
    lines += [
        "## Questions I answered during reconstruction",
        "",
    ]
    for q in dataset.get("questions", []):
        if q.get("status") == "answered" and q.get("answer"):
            lines.append(f"**{q['question']}**")
            lines.append(f"My answer: {q['answer']}")
            lines.append("")
    lines += [
        "## Open questions I could not fully answer",
        "",
    ]
    for q in dataset.get("questions", []):
        if q.get("status") == "open":
            lines.append(f"- {q['question']}")
    return "\n".join(lines)


# ============================================================
# FILE MATERIALISATION
# ============================================================

def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _stored_name(doc_id: str, basename: str) -> str:
    return f"seed_{doc_id}_{basename}"


def _materialise_files(con: sqlite3.Connection, dataset: Dict[str, Any]) -> None:
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    created_at = "2026-10-20T09:00:00+05:30"

    # Main 13 files
    for doc in dataset.get("files", []):
        doc_id = doc["id"]
        raw_path = doc.get("path", "")
        classification = doc.get("classification", "internal")
        title = doc.get("title", "Document")
        owner = doc.get("owner", "")

        src = SEED_FILES_ROOT / raw_path
        if not src.exists():
            continue

        file_bytes = src.read_bytes()
        sha = _sha256_hex(file_bytes)
        stored = _stored_name(doc_id, src.name)
        dest = UPLOADS_DIR / stored
        if not dest.exists():
            shutil.copy2(src, dest)

        if classification == "confidential":
            if con.execute("SELECT id FROM confidential_meta WHERE id=?", (doc_id,)).fetchone() is None:
                con.execute(
                    "INSERT INTO confidential_meta(id,name,size_bytes,uploaded_by,uploaded_at) VALUES(?,?,?,?,?)",
                    (doc_id, title, len(file_bytes), "sarah", created_at),
                )
        else:
            if con.execute("SELECT id FROM files WHERE id=?", (doc_id,)).fetchone() is None:
                con.execute(
                    "INSERT INTO files(id,original_name,stored_name,classification,"
                    "owner_id,owner_name,size_bytes,sha256,extracted_text,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (doc_id, src.name, stored, "normal",
                     "sarah", owner, len(file_bytes), sha, None, created_at),
                )

    # 2 historical versions
    for version in dataset.get("version_history", []):
        parent_id = version.get("document_id", "")
        ver_label = version.get("version", "")
        raw_path = version.get("path", "")
        ver_id = f"{parent_id}_v{ver_label.replace('.', '_')}"

        src = SEED_FILES_ROOT / raw_path
        if not src.exists():
            continue

        file_bytes = src.read_bytes()
        sha = _sha256_hex(file_bytes)
        stored = _stored_name(ver_id, src.name)
        dest = UPLOADS_DIR / stored
        if not dest.exists():
            shutil.copy2(src, dest)

        if con.execute("SELECT id FROM files WHERE id=?", (ver_id,)).fetchone() is None:
            con.execute(
                "INSERT INTO files(id,original_name,stored_name,classification,"
                "owner_id,owner_name,size_bytes,sha256,extracted_text,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (ver_id, src.name, stored, "normal",
                 "sarah", f"Historical v{ver_label} of {parent_id}",
                 len(file_bytes), sha, None, created_at),
            )


# ============================================================
# SEED ALL TABLES
# ============================================================

def _seed_all(con: sqlite3.Connection, dataset: Dict[str, Any], completed: bool) -> None:
    findings = dataset.get("findings", [])
    decisions, risks = _split_findings(findings)
    unresolved = _build_unresolved(dataset)
    tribal = _build_tribal_knowledge(dataset)

    if completed:
        gap_answers = _build_gap_answers(dataset)
        verifications = _build_verifications(decisions, risks)
        approvals = {
            "decisions": True,
            "risks": True,
            "unresolved": True,
            "tribal": True,
            "contacts": True,
        }
        manager_handover = _build_manager_handover(dataset)
        newhire_handover = _build_newhire_handover(dataset)
        employee_handover = _build_employee_handover(dataset)
        handovers_run = 1
        successor_notes = [
            {
                "id": "NOTE-001",
                "title": "Local environment setup verification",
                "category": "Setup & Environment",
                "content": "Verified Docker Compose setup for payment gateway mock service. Port 8080 conflicts with local proxy - mapped to 8085 instead.",
                "created_at": "2026-10-22 10:15:00",
                "author": "Marcus Vance",
            },
            {
                "id": "NOTE-002",
                "title": "Vendor rate limit follow-up",
                "category": "Architecture Question",
                "content": "Need to confirm with Stripe account rep regarding tier-2 rate limits before Q4 traffic ramp.",
                "created_at": "2026-10-22 14:30:00",
                "author": "Marcus Vance",
            },
        ]
    else:
        gap_answers = {}
        verifications = {}
        approvals = {}
        manager_handover = None
        newhire_handover = None
        employee_handover = None
        handovers_run = 0
        successor_notes = []

    profile = {
        "decisions": decisions,
        "risks": risks,
        "unresolved": unresolved,
        "contacts": _build_contacts(),
        "dependencies": _build_dependencies(dataset),
        "summary": dataset.get("dataset_notice") or "Harborline Platform Operations Handover — synthetic demo dataset.",
    }

    all_sources = [
        {
            "content": f"{doc.get('title', 'Document')} — {doc.get('owner', 'owner')}",
            "source": doc.get("path", "seed_files"),
            "source_type": "file",
        }
        for doc in dataset.get("files", [])
    ]

    # KV rows
    kv_rows = {
        "knowledge_profile": profile,
        "employee_name": "Sarah Chen",
        "project_role": "Platform Operations and Customer Operations handover",
        "employee_verifications": verifications,
        "employee_gap_answers": gap_answers,
        "employee_tribal_knowledge": tribal,
        "approvals": approvals,
        "corrections": {},
        "manager_handover": manager_handover,
        "newhire_handover": newhire_handover,
        "employee_handover": employee_handover,
        "acknowledgement": None,
        "all_sources": all_sources,
        "analyses_run": 1,
        "handovers_run": handovers_run,
        "successor_notes": successor_notes,
    }
    for key, val in kv_rows.items():
        _kv_set(con, key, val)

    # members
    for mid, uname, name, role, joined in [
        ("manager", "manager", "Manager", "Manager", "2026-10-20T09:00:00+05:30"),
        ("sarah",   "sarah",   "Sarah Chen",   "Employee",  "2026-10-20T09:00:00+05:30"),
        ("marcus",  "marcus",  "Marcus Vance",  "Successor", "2026-10-20T09:00:00+05:30"),
    ]:
        con.execute(
            "INSERT OR IGNORE INTO members(id,username,name,role,joined_at) VALUES(?,?,?,?,?)",
            (mid, uname, name, role, joined),
        )

    # grants
    grants_map = {
        "manager": ["confidential_read", "confidential_write"],
        "sarah":   ["confidential_read"],
        "marcus":  [],
    }
    for member_id, grant_list in grants_map.items():
        con.execute("DELETE FROM grants WHERE member_id=?", (member_id,))
        for g in grant_list:
            con.execute(
                "INSERT OR IGNORE INTO grants(member_id,grant_type) VALUES(?,?)",
                (member_id, g),
            )

    # notifications
    for nid, to_id, kind, msg, cat in [
        ("NOT-001", "manager", "review_request",
         "Sarah Chen has submitted the current knowledge findings for review.",
         "2026-10-24T09:00:00+05:30"),
        ("NOT-002", "manager", "review_request",
         "One employee note is classified confidential and needs an explicit publication decision.",
         "2026-10-24T09:05:00+05:30"),
        ("NOT-003", "manager", "access_request",
         "Marcus Vance has one pending request for write access to the handover workspace.",
         "2026-10-24T09:12:00+05:30"),
    ]:
        con.execute(
            "INSERT OR IGNORE INTO notifications(id,to_id,kind,message,created_at,read) VALUES(?,?,?,?,?,?)",
            (nid, to_id, kind, msg, cat, 0),
        )

    # access_requests
    con.execute(
        """INSERT OR IGNORE INTO access_requests
           (id,requester_id,requester_name,requester_role,type,reason,
            status,created_at,decided_at,decided_by,decision_comment)
           VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
        (
            "REQ-001", "marcus", "Marcus Vance", "Successor",
            "normal_write",
            "Requested write access to the handover workspace to contribute context and updates.",
            "pending",
            "2026-10-24T09:12:00+05:30",
            None, None, "",
        ),
    )

    # audit_log
    for entry in dataset.get("audit_log", []):
        con.execute(
            "INSERT INTO audit_log(who,action,reason,created_at) VALUES(?,?,?,?)",
            (
                entry.get("actor_name", "system"),
                entry.get("event_type", "demo_event"),
                entry.get("summary", ""),
                entry.get("timestamp", time.strftime("%Y-%m-%d %H:%M:%S")),
            ),
        )

    # files + confidential_meta
    _materialise_files(con, dataset)


# ============================================================
# PUBLIC ENTRY POINTS
# ============================================================

def ensure_demo_database_seeded(
    force_reset: bool = False,
    completed: bool = True,
) -> None:
    """Write the Harborline demo state into SQLite. Idempotent."""
    dataset = _load_dataset()
    con = _open_db()
    try:
        _ensure_schema(con)

        current_sentinel = _kv_get(con, _SEED_KEY)
        target_sentinel = _SEED_VAL_COMPLETE if completed else _SEED_VAL_START

        if not force_reset and current_sentinel == target_sentinel:
            return  # already in the right state

        _wipe_all_tables(con)
        _seed_all(con, dataset, completed=completed)
        _kv_set(con, _SEED_KEY, target_sentinel)
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def load_completed_handover() -> None:
    """Force-seed the completed-handover state. Called by Manager on Audit page."""
    ensure_demo_database_seeded(force_reset=True, completed=True)


def reset_demo_data() -> None:
    """Force-seed the start state. Called by Manager on Audit page."""
    ensure_demo_database_seeded(force_reset=True, completed=False)


# ============================================================
# LEGACY BACKWARD COMPAT
# ============================================================

def hydrate_demo_session_state(session_state: Dict[str, Any], user: Dict[str, Any]) -> None:
    """Kept for backward compat — ensure DB is seeded; session is hydrated via load_into_session."""
    ensure_demo_database_seeded(force_reset=False, completed=False)


def load_harborline_demo_dataset() -> Dict[str, Any]:
    """Load the Harborline mock fixture from disk (kept for external callers)."""
    return _load_dataset()
