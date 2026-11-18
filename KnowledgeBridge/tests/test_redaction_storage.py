"""Tests for redaction and encryption at rest in Baton storage layer.

Verifies:
1. Raw DB bytes contain no confidential phrases
2. Direct store read as marcus returns placeholder
3. Direct store read with no user returns restricted result
4. Manager and Sarah get full text
10. Secret patterns are redacted in successor-visible text
11. Normal non-confidential text returned unchanged to marcus
12. Missing or wrong key fails closed, does not crash
13. Migration is idempotent and leaves no plaintext after VACUUM
"""

import os
import shutil
import sqlite3
import tempfile
from pathlib import Path
import pytest

import utils.store as store
import utils.demo_seed as demo_seed
from utils.crypto import (
    encrypt_text,
    decrypt_text,
    is_encrypted,
    REDACTION_PLACEHOLDER,
)
from utils.access import redact, redact_secrets

KNOWN_CONFIDENTIAL_PHRASES = [
    "upstream ledger closes at 18:00 IST",
    "REF-001,Goodwill refund",
    "HARBORLINE BUSINESS CONTINUITY CONTACT ROUTING",
    "When the alert is noisy but customer impact is unclear",
]


def test_1_raw_bytes_contain_no_confidential_phrase(tmp_path):
    """(1) The raw bytes of the .db file and its -wal file contain no known confidential phrase from a seeded confidential document."""
    demo_seed.ensure_demo_database_seeded(force_reset=True, completed=True)

    test_db = store.DB_FILE
    # Checkpoint WAL so all pages are committed
    with sqlite3.connect(str(test_db)) as con:
        con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        con.execute("VACUUM")

    db_bytes = test_db.read_bytes()
    wal_file = test_db.parent / (test_db.name + "-wal")
    wal_bytes = wal_file.read_bytes() if wal_file.exists() else b""

    combined = db_bytes + wal_bytes
    for phrase in KNOWN_CONFIDENTIAL_PHRASES:
        assert phrase.encode("utf-8") not in combined, f"Found confidential phrase in DB bytes: {phrase}"


def test_2_direct_store_read_as_marcus_returns_placeholder():
    """(2) A direct store read as marcus returns the placeholder, not the text."""
    demo_seed.ensure_demo_database_seeded(force_reset=True, completed=True)

    marcus_user = {"id": "marcus", "username": "marcus", "role": "Successor", "name": "Marcus Vance"}
    text = store.get_file_text("DOC-TRB-008", user=marcus_user)
    assert text == REDACTION_PLACEHOLDER
    assert "Reconciliation" not in text


def test_3_direct_store_read_with_no_user_returns_restricted():
    """(3) A direct store read with no user returns the restricted result."""
    text = store.get_file_text("DOC-TRB-008", user=None)
    assert text == REDACTION_PLACEHOLDER


def test_4_manager_and_sarah_get_full_text():
    """(4) Manager and sarah get the full text."""
    demo_seed.ensure_demo_database_seeded(force_reset=True, completed=True)

    mgr_user = {"id": "manager", "username": "manager", "role": "Manager", "name": "Manager"}
    sarah_user = {"id": "sarah", "username": "sarah", "role": "Employee", "name": "Sarah Chen"}

    mgr_text = store.get_file_text("DOC-TRB-008", user=mgr_user)
    sarah_text = store.get_file_text("DOC-TRB-008", user=sarah_user)

    assert REDACTION_PLACEHOLDER not in mgr_text
    assert REDACTION_PLACEHOLDER not in sarah_text
    assert "reconciliation" in mgr_text.lower()
    assert "reconciliation" in sarah_text.lower()


def test_10_secret_patterns_redacted_in_successor_text():
    """(10) Secret patterns (api_key=..., password: ...) are redacted in successor-visible text."""
    plain = "Config: api_key=super_secret_token_12345 and password: my_db_password_xyz."
    marcus_user = {"id": "marcus", "username": "marcus", "role": "Successor"}
    res = redact(plain, user=marcus_user, file_sensitivity="normal")
    assert "super_secret_token_12345" not in res
    assert "my_db_password_xyz" not in res
    assert REDACTION_PLACEHOLDER in res


def test_11_normal_non_confidential_text_returned_unchanged_to_marcus():
    """(11) Normal non-confidential text is returned unchanged to marcus."""
    demo_seed.ensure_demo_database_seeded(force_reset=True, completed=True)

    marcus_user = {"id": "marcus", "username": "marcus", "role": "Successor"}
    text = store.get_file_text("DOC-API-003", user=marcus_user)
    # DOC-API-003 is normal/internal, should be readable
    assert REDACTION_PLACEHOLDER not in text
    assert len(text) > 0


def test_12_missing_or_wrong_key_fails_closed():
    """(12) A missing or wrong key fails closed and does not crash."""
    from cryptography.fernet import Fernet
    different_key = Fernet.generate_key()
    f = Fernet(different_key)
    foreign_token = "enc:v1:" + f.encrypt(b"secret message").decode("ascii")

    # Decrypting with default key must fail closed to REDACTION_PLACEHOLDER without raising
    result = decrypt_text(foreign_token)
    assert result == REDACTION_PLACEHOLDER


def test_13_migration_idempotent_and_cleans_free_pages(tmp_path):
    """(13) Migration is idempotent and leaves no plaintext in a temporary copy of the database after VACUUM."""
    from migrate_encrypt import run_migration

    test_db = tmp_path / "migrate_test.db"
    with sqlite3.connect(str(test_db)) as con:
        con.execute("CREATE TABLE files (id TEXT PRIMARY KEY, classification TEXT, extracted_text TEXT)")
        con.execute("CREATE TABLE kv (key TEXT PRIMARY KEY, value TEXT)")
        con.execute(
            "INSERT INTO files VALUES ('DOC-TRB-008', 'confidential', 'The daily reconciliation export closes at 18:00 IST.')"
        )
        con.execute(
            "INSERT INTO kv VALUES ('employee_tribal_knowledge', '[{\"category\": \"Warning\", \"title\": \"Alert check\", \"content\": \"When the alert is noisy check queue\"}]')"
        )
        con.commit()

    # First migration run
    count1 = run_migration(test_db, perform_backup=False)
    assert count1 >= 2

    # Verify encrypted
    with sqlite3.connect(str(test_db)) as con:
        row = con.execute("SELECT extracted_text FROM files WHERE id='DOC-TRB-008'").fetchone()
        assert row[0].startswith("enc:v1:")
        kv_row = con.execute("SELECT value FROM kv WHERE key='employee_tribal_knowledge'").fetchone()
        assert "enc:v1:" in kv_row[0]

    # Verify no plaintext in DB bytes after VACUUM
    db_bytes = test_db.read_bytes()
    assert b"The daily reconciliation export" not in db_bytes
    assert b"When the alert is noisy" not in db_bytes

    # Second migration run (idempotent)
    count2 = run_migration(test_db, perform_backup=False)
    assert count2 == 0
