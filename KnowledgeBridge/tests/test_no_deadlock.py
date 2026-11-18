"""tests/test_no_deadlock.py

Regression tests for the self-deadlock fix in utils/store.py.

Design requirements:
- Tests 1–5 use the FULL demo seed (same as test_permissions.py) so that
  _assemble_state processes knowledge_profile claims whose source IDs are NOT
  in the hardcoded CONFIDENTIAL_SOURCES fast-path set (e.g. DOC-INC-001,
  DOC-REF-004, DOC-REL-006, DOC-SEC-002, DOC-API-003).  Those sources trigger
  the real DB-lookup branch of get_file_sensitivity, which is exactly the code
  path that caused the deadlock on old code.
- Every connection is capped at a 1-second timeout via _low_timeout() so a
  deadlock surfaces in < 2 s instead of hanging for 30 s.
- Temporary databases only: DB_FILE is monkeypatched in both store and
  demo_seed via the autouse fixture in conftest.py AND locally in every test.

Sources NOT in CONFIDENTIAL_SOURCES (force real DB lookup):
  DOC-INC-001, DOC-SEC-002, DOC-API-003, DOC-REF-004, DOC-REL-006
"""

import sqlite3
import time
import threading
from pathlib import Path

import pytest

import utils.store as store
import utils.demo_seed as demo_seed
import utils.access as access


# ---------------------------------------------------------------------------
# Shared user objects
# ---------------------------------------------------------------------------

MARCUS = {"id": "marcus", "username": "marcus", "role": "Successor",
          "name": "Marcus Vance"}
MANAGER = {"id": "manager", "username": "manager", "role": "Manager",
           "name": "Manager Demo"}


# ---------------------------------------------------------------------------
# Helper: patch _db to 1-second timeout so deadlocks surface fast.
# ---------------------------------------------------------------------------

def _low_timeout(monkeypatch) -> None:
    """Monkeypatch store._db to use 1-second timeout."""
    from contextlib import contextmanager

    @contextmanager
    def fast_db(timeout: float = 1.0):
        store.ensure_data_dir()
        con = sqlite3.connect(str(store.DB_FILE), timeout=timeout,
                              check_same_thread=False)
        con.row_factory = sqlite3.Row
        try:
            con.execute("PRAGMA journal_mode=WAL")
            con.execute("PRAGMA busy_timeout = 1000")
            con.execute("PRAGMA foreign_keys=ON")
            yield con
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

    monkeypatch.setattr(store, "_db", fast_db)


# ---------------------------------------------------------------------------
# Helper: seed the full demo database (same as test_permissions.py).
# _DB_INITIALIZED must be reset first so _init_db() runs against the tmp db.
# ---------------------------------------------------------------------------

def _full_seed(monkeypatch) -> None:
    """Reset _DB_INITIALIZED and run ensure_demo_database_seeded(force_reset=True)."""
    monkeypatch.setattr(store, "_DB_INITIALIZED", False)
    demo_seed.ensure_demo_database_seeded(force_reset=True, completed=True)


# ---------------------------------------------------------------------------
# Test 1: create_request reaches the deadlocking path and completes quickly.
#
# Path exercised:
#   create_request -> modify_project_state (holds write tx)
#     -> _assemble_state(con) -> get_file_sensitivity(src, con=con)
#   For sources like DOC-INC-001 / DOC-REF-004 that are NOT in
#   CONFIDENTIAL_SOURCES, the fixed code passes `con` through (no second
#   connection).  Old code opened a second _db() + _ensure_schema() while the
#   first connection held the write lock → deadlock.
# ---------------------------------------------------------------------------

def test_1_create_request_no_deadlock(monkeypatch):
    """create_request for a confidential file as the successor must not deadlock."""
    _low_timeout(monkeypatch)
    _full_seed(monkeypatch)

    state, _ = store.load_project_state()

    t0 = time.time()
    req = access.create_request(
        state, MARCUS, "confidential_read",
        "Need tribal knowledge", file_id="DOC-TRB-008"
    )
    elapsed = time.time() - t0

    assert req["id"], "create_request must return a request dict with an id"
    assert elapsed < 5.0, (
        f"create_request took {elapsed:.1f}s — deadlock (expected < 5 s)"
    )


# ---------------------------------------------------------------------------
# Test 2: decide_request (approve) completes quickly.
#
# Path exercised:
#   decide_request -> modify_project_state (holds write tx)
#     -> _assemble_state(con) -> get_file_sensitivity(non-CONF src, con=con)
# ---------------------------------------------------------------------------

def test_2_decide_request_approve_no_deadlock(monkeypatch):
    """decide_request(approve=True) must not deadlock."""
    _low_timeout(monkeypatch)
    _full_seed(monkeypatch)

    state, _ = store.load_project_state()
    req = access.create_request(
        state, MARCUS, "confidential_read",
        "Need access", file_id="DOC-TRB-008"
    )

    t0 = time.time()
    access.decide_request(state, MANAGER, req["id"], approve=True, comment="OK")
    elapsed = time.time() - t0

    assert elapsed < 5.0, (
        f"decide_request(approve) took {elapsed:.1f}s — deadlock"
    )


# ---------------------------------------------------------------------------
# Test 3: decide_request (reject) completes quickly.
#
# Path exercised: same as test 2 but approve=False branch.
# ---------------------------------------------------------------------------

def test_3_decide_request_reject_no_deadlock(monkeypatch):
    """decide_request(approve=False) must not deadlock."""
    _low_timeout(monkeypatch)
    _full_seed(monkeypatch)

    state, _ = store.load_project_state()
    req = access.create_request(
        state, MARCUS, "confidential_read",
        "Need access", file_id="DOC-TRB-008"
    )

    t0 = time.time()
    access.decide_request(state, MANAGER, req["id"], approve=False, comment="Denied")
    elapsed = time.time() - t0

    assert elapsed < 5.0, (
        f"decide_request(reject) took {elapsed:.1f}s — deadlock"
    )


# ---------------------------------------------------------------------------
# Test 4: modify_project_state with the full seeded knowledge_profile.
#
# Path exercised:
#   modify_project_state (holds write tx)
#     -> _assemble_state(con)
#     -> for each claim in decisions/risks:
#          get_file_sensitivity(src, con=con)   # non-CONF srcs: real DB query
#          can_user_read_file(user, src, con=con)
# ---------------------------------------------------------------------------

def test_4_modify_project_state_no_deadlock(monkeypatch):
    """modify_project_state with full seeded knowledge_profile must not deadlock."""
    _low_timeout(monkeypatch)
    _full_seed(monkeypatch)

    t0 = time.time()
    store.modify_project_state(lambda d: d.setdefault("project_role", "test"))
    elapsed = time.time() - t0

    assert elapsed < 5.0, (
        f"modify_project_state took {elapsed:.1f}s — deadlock"
    )


# ---------------------------------------------------------------------------
# Test 5: load_project_state as marcus with the full seeded knowledge_profile.
#
# Path exercised:
#   load_project_state(user=marcus)
#     -> _db() (read tx) -> _assemble_state(con, user=marcus)
#     -> for each non-CONF source: get_file_sensitivity(src, con=con) [DB hit]
#        and can_user_read_file(marcus, src, con=con) [grants check]
# ---------------------------------------------------------------------------

def test_5_load_project_state_no_deadlock(monkeypatch):
    """load_project_state as marcus with full seed must not deadlock."""
    _low_timeout(monkeypatch)
    _full_seed(monkeypatch)

    t0 = time.time()
    state, _ = store.load_project_state(user=MARCUS)
    elapsed = time.time() - t0

    assert elapsed < 5.0, (
        f"load_project_state took {elapsed:.1f}s — deadlock"
    )
    assert isinstance(state, dict)
    # Sanity: knowledge_profile is populated from the full seed
    kp = state.get("knowledge_profile") or {}
    all_claims = kp.get("decisions", []) + kp.get("risks", [])
    assert len(all_claims) > 0, (
        "Full seed should produce at least one knowledge_profile claim"
    )


# ---------------------------------------------------------------------------
# Test (structural): at most ONE connection open at a time per modify_project_state
#                    call, even when knowledge_profile has non-CONF sources.
#
# How it works: wrap sqlite3.connect with a counter of simultaneously open
# connections to the temp DB.  Run create_request (which calls
# modify_project_state internally).  Assert the peak concurrent count is 1.
#
# On old code with the full seed, _assemble_state would call
# get_file_sensitivity(non-CONF-src) → open a 2nd sqlite3.connect → peak = 2.
# ---------------------------------------------------------------------------

def test_structural_max_one_connection_in_modify_project_state(monkeypatch):
    """modify_project_state must never open more than one connection at a time."""
    _low_timeout(monkeypatch)
    _full_seed(monkeypatch)

    # --- intercept sqlite3.connect for the temp DB only ---
    real_connect = sqlite3.connect
    open_count = [0]
    peak_count = [0]
    tmp_db_str = str(store.DB_FILE)
    lock = threading.Lock()

    class _TrackedCon:
        """Thin proxy that counts simultaneous open connections.

        Must transparently forward ALL attribute access — including
        `row_factory` (which sqlite3.Row requires to be set on the connection
        object) — to the inner sqlite3.Connection.
        """
        def __init__(self, inner):
            # Use object.__setattr__ to avoid our own __setattr__ loop.
            object.__setattr__(self, "_inner", inner)

        def __getattr__(self, name):
            return getattr(object.__getattribute__(self, "_inner"), name)

        def __setattr__(self, name, value):
            if name == "_inner":
                object.__setattr__(self, name, value)
            else:
                setattr(object.__getattribute__(self, "_inner"), name, value)

        def close(self):
            with lock:
                open_count[0] -= 1
            object.__getattribute__(self, "_inner").close()

        # context manager — _db() yields the connection directly, so these
        # won't be called by store code, but keep them correct anyway.
        def __enter__(self):
            return object.__getattribute__(self, "_inner").__enter__()

        def __exit__(self, *a):
            with lock:
                open_count[0] -= 1
            return object.__getattribute__(self, "_inner").__exit__(*a)

    def patched_connect(database, *args, **kwargs):
        con = real_connect(database, *args, **kwargs)
        if str(database) == tmp_db_str:
            with lock:
                open_count[0] += 1
                if open_count[0] > peak_count[0]:
                    peak_count[0] = open_count[0]
            return _TrackedCon(con)
        return con

    monkeypatch.setattr(sqlite3, "connect", patched_connect)

    state, _ = store.load_project_state()
    req = access.create_request(
        state, MARCUS, "confidential_read",
        "Need tribal knowledge", file_id="DOC-TRB-008"
    )

    assert req["id"]
    assert peak_count[0] == 1, (
        f"Peak simultaneous connections to the DB was {peak_count[0]}; "
        f"expected exactly 1 (old deadlocking code would give >= 2)"
    )


# ---------------------------------------------------------------------------
# Test 6a: get_file_sensitivity with con=None returns "confidential"
#          (tests the read-only standalone path, independent of the con= param)
# ---------------------------------------------------------------------------

def test_6a_get_file_sensitivity_no_con_returns_confidential(monkeypatch):
    """get_file_sensitivity(file_id) with no con returns correct sensitivity."""
    monkeypatch.setattr(store, "_DB_INITIALIZED", False)
    # Use conftest's isolate_test_db fixture — just seed a minimal row directly
    with store._db() as con:
        store._ensure_schema(con)
        con.execute(
            "INSERT OR IGNORE INTO files"
            " (id, original_name, stored_name, classification, owner_id,"
            "  owner_name, size_bytes, sha256, created_at, sensitivity)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("DOC-REF-004", "ref.pdf", "ref.pdf", "confidential",
             "sarah", "Sarah Chen", 100, "sha", "2026-01-01 00:00:00",
             "confidential"),
        )

    # con=None path — read-only, no _ensure_schema
    sens = store.get_file_sensitivity("DOC-REF-004")
    assert sens == "confidential", f"Expected 'confidential', got {sens!r}"

    # Non-existent file → "normal"
    assert store.get_file_sensitivity("DOC-DOES-NOT-EXIST") == "normal"


# ---------------------------------------------------------------------------
# Test 6b: get_file_sensitivity with con= passed returns the same value
# ---------------------------------------------------------------------------

def test_6b_get_file_sensitivity_with_con_matches_no_con(monkeypatch):
    """get_file_sensitivity(file_id, con=con) matches the no-con result."""
    monkeypatch.setattr(store, "_DB_INITIALIZED", False)
    with store._db() as con:
        store._ensure_schema(con)
        con.execute(
            "INSERT OR IGNORE INTO files"
            " (id, original_name, stored_name, classification, owner_id,"
            "  owner_name, size_bytes, sha256, created_at, sensitivity)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("DOC-REF-004", "ref.pdf", "ref.pdf", "confidential",
             "sarah", "Sarah Chen", 100, "sha", "2026-01-01 00:00:00",
             "confidential"),
        )

    sens_no_con = store.get_file_sensitivity("DOC-REF-004")

    with store._db() as con:
        sens_with_con = store.get_file_sensitivity("DOC-REF-004", con=con)

    assert sens_no_con == "confidential"
    assert sens_with_con == "confidential"
    assert sens_no_con == sens_with_con, (
        f"con=None → {sens_no_con!r}, con=con → {sens_with_con!r}: must match"
    )


# ---------------------------------------------------------------------------
# Test 7: get_file_sensitivity(con=None) must NOT block on a write lock.
#
# Proves the read-only path (PRAGMA query_only=ON) does not perform writes
# or acquire an exclusive lock, so it succeeds even when another thread
# holds BEGIN IMMEDIATE.
# ---------------------------------------------------------------------------

def test_7_get_file_sensitivity_no_write_under_lock(monkeypatch):
    """get_file_sensitivity(con=None) must complete < 2 s even under a write lock."""
    monkeypatch.setattr(store, "_DB_INITIALIZED", False)

    # Seed a confidential row for DOC-TRB-008 directly
    with store._db() as con:
        store._ensure_schema(con)
        con.execute(
            "INSERT OR IGNORE INTO files"
            " (id, original_name, stored_name, classification, owner_id,"
            "  owner_name, size_bytes, sha256, created_at, sensitivity)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("DOC-TRB-008", "tribal.pdf", "tribal.pdf", "confidential",
             "sarah", "Sarah Chen", 1000, "abc", "2026-01-01 00:00:00",
             "confidential"),
        )
    # Remove DOC-TRB-008 from CONFIDENTIAL_SOURCES momentarily so the DB path
    # is taken (instead of the O(1) fast-path set lookup).
    orig_sources = store.CONFIDENTIAL_SOURCES
    monkeypatch.setattr(store, "CONFIDENTIAL_SOURCES", frozenset())

    result = {}
    errors = []

    # Thread A: hold a write lock for 2 seconds
    lock_acquired = threading.Event()
    lock_released = threading.Event()

    def hold_write_lock():
        blocker = sqlite3.connect(str(store.DB_FILE), timeout=5.0)
        blocker.execute("PRAGMA journal_mode=WAL")
        try:
            blocker.execute("BEGIN IMMEDIATE")
            lock_acquired.set()
            lock_released.wait(timeout=3.0)
        finally:
            blocker.rollback()
            blocker.close()

    t_lock = threading.Thread(target=hold_write_lock, daemon=True)
    t_lock.start()
    lock_acquired.wait(timeout=3.0)

    # Main thread: get_file_sensitivity(con=None) must use PRAGMA query_only
    # and NOT block on the write lock.
    t0 = time.time()
    try:
        sens = store.get_file_sensitivity("DOC-TRB-008")
        result["sens"] = sens
    except Exception as e:
        errors.append(str(e))
    elapsed = time.time() - t0

    lock_released.set()
    t_lock.join(timeout=5.0)

    assert not errors, f"Unexpected error: {errors}"
    assert result.get("sens") == "confidential"
    assert elapsed < 2.0, (
        f"get_file_sensitivity took {elapsed:.2f}s under write lock — "
        f"it is performing writes or acquiring an exclusive lock"
    )
