"""Smoke tests using streamlit.testing.v1.AppTest.
Verifies role-based access gating and page loading without unhandled exceptions across all role x org_type combinations.
"""

import pytest
import sqlite3
from pathlib import Path
from streamlit.testing.v1 import AppTest

import utils.store as store
import utils.demo_seed as demo_seed
from utils.access import get_allowed_pages


@pytest.fixture
def isolated_smoke_db(tmp_path, monkeypatch):
    """Isolate database to a fresh temporary file and seed initial demo state."""
    db_file = tmp_path / "smoke_baton.db"
    monkeypatch.setattr(store, "DB_FILE", db_file)
    monkeypatch.setattr(store, "_DB_INITIALIZED", False)
    store._init_db()
    demo_seed.ensure_demo_database_seeded(force_reset=True, completed=False)
    return db_file


ROLE_ORG_CONFIGS = [
    ("Manager", "company", "audit", "connect"),
    ("Manager", "student_team", "audit", "connect"),
    ("Employee", "company", "connect", "access_management"),
    ("Employee", "student_team", "connect", "access_management"),
    ("Successor", "company", "successor_notes", "access_management"),
    ("Successor", "student_team", "successor_notes", "access_management"),
]


@pytest.mark.parametrize("role,org_type,allowed_page,forbidden_page", ROLE_ORG_CONFIGS)
def test_role_page_access_and_rejection(isolated_smoke_db, role, org_type, allowed_page, forbidden_page):
    """Test allowed page renders without unhandled exceptions, and forbidden page is rejected with access denied."""
    app_path = str(Path(__file__).resolve().parent.parent / "app.py")

    # 1. Allowed page test
    at_allowed = AppTest.from_file(app_path, default_timeout=10)
    at_allowed.session_state["authenticated"] = True
    at_allowed.session_state["auth_username"] = f"test_{role.lower()}"
    at_allowed.session_state["auth_name"] = f"Test {role}"
    at_allowed.session_state["auth_role"] = role
    at_allowed.session_state["auth_org_id"] = "test_org"
    at_allowed.session_state["auth_org_type"] = org_type
    at_allowed.session_state["page"] = allowed_page

    at_allowed.run()
    assert len(at_allowed.exception) == 0, f"Exception on allowed page {allowed_page} for {role}: {at_allowed.exception}"

    # 2. Forbidden page test
    at_forbidden = AppTest.from_file(app_path, default_timeout=10)
    at_forbidden.session_state["authenticated"] = True
    at_forbidden.session_state["auth_username"] = f"test_{role.lower()}"
    at_forbidden.session_state["auth_name"] = f"Test {role}"
    at_forbidden.session_state["auth_role"] = role
    at_forbidden.session_state["auth_org_id"] = "test_org"
    at_forbidden.session_state["auth_org_type"] = org_type
    at_forbidden.session_state["page"] = forbidden_page

    at_forbidden.run()
    # Check that access was denied
    has_denied_error = any("Access denied for your role" in str(err.value) for err in at_forbidden.error)
    assert has_denied_error, f"Expected access denied error on forbidden page {forbidden_page} for {role}"
