import os
import sys
from pathlib import Path
import pytest

# Ensure KnowledgeBridge root is on sys.path
KB_DIR = Path(__file__).resolve().parent.parent
if str(KB_DIR) not in sys.path:
    sys.path.insert(0, str(KB_DIR))

import utils.store as store
import utils.demo_seed as demo_seed

@pytest.fixture(autouse=True)
def isolate_test_db(tmp_path, monkeypatch):
    """Ensure every test uses a temporary, isolated SQLite database.
    
    CRITICAL: Never touch or modify data/baton.db.
    """
    tmp_db_file = tmp_path / "test_baton.db"
    monkeypatch.setattr(store, "DATA_DIR", tmp_path)
    monkeypatch.setattr(store, "DB_FILE", tmp_db_file)
    monkeypatch.setattr(store, "UPLOADS_DIR", tmp_path / "uploads")
    monkeypatch.setattr(demo_seed, "DB_FILE", tmp_db_file)
    monkeypatch.setattr(demo_seed, "UPLOADS_DIR", tmp_path / "uploads")

    # Initialize schema in the temporary database
    with store._db() as con:
        store._ensure_schema(con)

    yield tmp_db_file
