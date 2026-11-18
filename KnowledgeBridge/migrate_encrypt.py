#!/usr/bin/env python3
"""Migration script to encrypt confidential text at rest in Baton SQLite database.

Requirements:
- Refuses to run without explicit --yes flag.
- Creates a timestamped backup of the database (and WAL/SHM files) outside the repo.
- Encrypts confidential plaintext in files.extracted_text and kv.
- Idempotent: values starting with 'enc:v1:' are skipped.
- Never deletes rows.
- Executes PRAGMA wal_checkpoint(TRUNCATE) and VACUUM.
- Prints count of encrypted values.
"""

import argparse
import datetime
import json
import os
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from utils.crypto import encrypt_text, is_encrypted

CONFIDENTIAL_DOC_IDS = {
    "DOC-TRB-008",
    "DOC-FIN-009",
    "DOC-BCP-010",
    "DOC-MON-011",
}
CONFIDENTIAL_NOTE_IDS = {
    "NOTE-004",
}
CONFIDENTIAL_SOURCES = CONFIDENTIAL_DOC_IDS | CONFIDENTIAL_NOTE_IDS


def run_migration(db_path: Path, perform_backup: bool = True) -> int:
    """Migrate the database at db_path, encrypting confidential text.
    
    Returns the count of newly encrypted values.
    """
    if not db_path.exists():
        print(f"Database file not found: {db_path}")
        return 0

    # 1. Create timestamped backup OUTSIDE the repo
    if perform_backup:
        ts_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = Path(tempfile.gettempdir()) / f"baton_db_backup_{ts_str}"
        backup_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(db_path, backup_dir / db_path.name)
        wal_file = db_path.parent / (db_path.name + "-wal")
        if wal_file.exists():
            shutil.copy2(wal_file, backup_dir / wal_file.name)
        shm_file = db_path.parent / (db_path.name + "-shm")
        if shm_file.exists():
            shutil.copy2(shm_file, backup_dir / shm_file.name)
        print(f"Created backup outside repo at: {backup_dir}")

    encrypted_count = 0

    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    try:
        # Check / add schema columns
        try:
            con.execute("ALTER TABLE files ADD COLUMN sensitivity TEXT NOT NULL DEFAULT 'normal'")
        except Exception:
            pass
        try:
            con.execute("ALTER TABLE grants ADD COLUMN file_id TEXT DEFAULT NULL")
        except Exception:
            pass
        try:
            con.execute("ALTER TABLE access_requests ADD COLUMN file_id TEXT DEFAULT NULL")
        except Exception:
            pass

        # Backfill sensitivity in files table
        con.execute("""
            UPDATE files SET sensitivity = 'confidential'
            WHERE id IN ('DOC-TRB-008', 'DOC-FIN-009', 'DOC-BCP-010', 'DOC-MON-011')
               OR classification = 'confidential'
        """)

        # 2. Encrypt files.extracted_text for confidential files
        cursor = con.execute("SELECT id, classification, sensitivity, extracted_text FROM files")
        file_rows = cursor.fetchall()
        for r in file_rows:
            fid = r["id"]
            sens = r["sensitivity"] or r["classification"]
            text = r["extracted_text"]
            is_conf = (sens == "confidential" or fid in CONFIDENTIAL_SOURCES)
            if is_conf and text and not is_encrypted(text):
                enc = encrypt_text(text)
                con.execute("UPDATE files SET extracted_text = ?, sensitivity = 'confidential' WHERE id = ?", (enc, fid))
                encrypted_count += 1

        # 3. Encrypt confidential values inside kv table
        kv_rows = con.execute("SELECT key, value FROM kv").fetchall()
        for r in kv_rows:
            key = r["key"]
            raw_val = r["value"]
            if not raw_val or raw_val == "null":
                continue
            try:
                data = json.loads(raw_val)
            except Exception:
                continue

            changed = False

            if key == "knowledge_profile" and isinstance(data, dict):
                for section in ("decisions", "risks"):
                    for claim in data.get(section, []):
                        src = claim.get("source") or claim.get("source_document_id") or claim.get("source_note_id") or ""
                        if src in CONFIDENTIAL_SOURCES:
                            claim["sensitivity"] = "confidential"
                            for qk in ("excerpt", "source_quote"):
                                if qk in claim and claim[qk] and not is_encrypted(claim[qk]):
                                    claim[qk] = encrypt_text(claim[qk])
                                    encrypted_count += 1
                                    changed = True

            elif key == "employee_tribal_knowledge" and isinstance(data, list):
                for note in data:
                    is_conf = (note.get("category") == "Warning" or 
                               note.get("classification") == "confidential" or 
                               "noisy alert" in note.get("title", "").lower())
                    if is_conf and "content" in note and note["content"] and not is_encrypted(note["content"]):
                        note["content"] = encrypt_text(note["content"])
                        encrypted_count += 1
                        changed = True

            elif key == "all_sources" and isinstance(data, list):
                for src_item in data:
                    src_path = src_item.get("source", "")
                    if src_path in CONFIDENTIAL_SOURCES or any(cid in str(src_path) for cid in CONFIDENTIAL_DOC_IDS):
                        if "content" in src_item and src_item["content"] and not is_encrypted(src_item["content"]):
                            src_item["content"] = encrypt_text(src_item["content"])
                            encrypted_count += 1
                            changed = True

            if changed:
                con.execute("UPDATE kv SET value = ? WHERE key = ?", (json.dumps(data, default=str), key))

        con.commit()

        # 4. Checkpoint WAL and VACUUM to remove free-page plaintext
        con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        con.execute("VACUUM")
        con.commit()

    finally:
        con.close()

    return encrypted_count


def main():
    parser = argparse.ArgumentParser(description="Migrate and encrypt confidential text at rest.")
    parser.add_argument("--yes", action="store_true", help="Explicit confirmation required to run.")
    parser.add_argument("--db", type=str, default=None, help="Custom database path (for testing).")
    args = parser.parse_args()

    if not args.yes:
        print("ERROR: migrate_encrypt.py will NOT run without the --yes flag.")
        print("Usage: python migrate_encrypt.py --yes [--db /path/to/baton.db]")
        sys.exit(1)

    if args.db:
        target_db = Path(args.db).resolve()
    else:
        target_db = BASE_DIR / "data" / "baton.db"

    print(f"Starting encryption migration on: {target_db}")
    count = run_migration(target_db, perform_backup=True)
    print(f"Migration completed successfully. Encrypted {count} confidential value(s).")


if __name__ == "__main__":
    main()
