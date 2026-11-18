"""Automated regression and functional tests for Multi-Tenant Registration,
Dynamic Accounts, Team Leaders, Managers, and Scoped Roles in BATON.
"""

import pytest
import sqlite3
import time
from pathlib import Path

import utils.store as store
import utils.auth as auth
from utils.access import get_role_label


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """Isolate database to a fresh temporary file for every test."""
    db_file = tmp_path / "test_baton_auth.db"
    monkeypatch.setattr(store, "DB_FILE", db_file)
    monkeypatch.setattr(store, "_DB_INITIALIZED", False)
    # Reset lockout state
    auth._LOGIN_STATE["failed_attempts"] = 0
    auth._LOGIN_STATE["lockout_until"] = 0.0
    store._init_db()
    return db_file


def test_password_hashing_and_verification():
    """Verify random salt generation, pbkdf2_hmac sha256 hashing and constant-time verification."""
    salt1, hash1 = auth.hash_password("SuperSecret123")
    salt2, hash2 = auth.hash_password("SuperSecret123")

    # Unique salts per generation
    assert salt1 != salt2
    assert hash1 != hash2
    assert len(salt1) == 32  # 16 bytes in hex

    # Verification
    assert auth.verify_password(salt1, hash1, "SuperSecret123") is True
    assert auth.verify_password(salt1, hash1, "WrongPassword") is False
    assert auth.verify_password(salt1, hash1, "") is False


def test_register_student_team_and_leader(temp_db):
    """Verify registering a student team creates the org, project, and Team Leader user."""
    ok, msg, user = auth.register_organization_and_leader(
        org_name="CodePune Thinkers",
        org_type="student_team",
        username="alex_leader",
        password="Password@123",
        full_name="Alex Morgan",
        project_name="Autonomous Dispatch",
    )
    assert ok is True
    assert user is not None
    assert user["username"] == "alex_leader"
    assert user["name"] == "Alex Morgan"
    assert user["role"] == "Manager"  # Mapped to Manager capability tier
    assert user["org_type"] == "student_team"
    assert user["org_name"] == "CodePune Thinkers"
    assert user["project_id"].startswith("proj_")

    # Verify directly in SQLite
    with store._db() as con:
        u_row = con.execute("SELECT * FROM users WHERE username = ?", ("alex_leader",)).fetchone()
        assert u_row is not None
        assert u_row["name"] == "Alex Morgan"
        assert u_row["org_type"] == "student_team"

        o_row = con.execute("SELECT * FROM organizations WHERE id = ?", (user["org_id"],)).fetchone()
        assert o_row is not None
        assert o_row["name"] == "CodePune Thinkers"
        assert o_row["org_type"] == "student_team"

        p_row = con.execute("SELECT * FROM projects WHERE id = ?", (user["project_id"],)).fetchone()
        assert p_row is not None
        assert p_row["name"] == "Autonomous Dispatch"


def test_register_company_and_manager(temp_db):
    """Verify registering a company creates an enterprise org and Manager user."""
    ok, msg, user = auth.register_organization_and_leader(
        org_name="Apex Logistics Corp",
        org_type="company",
        username="jordan_mgr",
        password="Password@456",
        full_name="Jordan Vance",
        project_name="Reconciliation System",
    )
    assert ok is True
    assert user["username"] == "jordan_mgr"
    assert user["role"] == "Manager"
    assert user["org_type"] == "company"


def test_registration_validation_rules(temp_db):
    """Verify validation: rejected duplicate username, reserved names, invalid characters, short passwords."""
    # 1. Reserved demo names
    ok, msg, _ = auth.register_organization_and_leader(
        org_name="Team A", org_type="student_team", username="manager", password="Password1", full_name="A"
    )
    assert ok is False
    assert "reserved" in msg.lower()

    # 2. Short password (< 6 chars)
    ok, msg, _ = auth.register_organization_and_leader(
        org_name="Team B", org_type="student_team", username="validuser1", password="123", full_name="B"
    )
    assert ok is False
    assert "at least 6 characters" in msg.lower()

    # 3. Invalid characters in username
    ok, msg, _ = auth.register_organization_and_leader(
        org_name="Team C", org_type="student_team", username="user@invalid!", password="Password1", full_name="C"
    )
    assert ok is False
    assert "alphanumeric" in msg.lower()

    # 4. Duplicate username rejection
    ok1, _, _ = auth.register_organization_and_leader(
        org_name="Team D", org_type="student_team", username="sammy123", password="Password1", full_name="Sam"
    )
    assert ok1 is True
    ok2, msg2, _ = auth.register_organization_and_leader(
        org_name="Team E", org_type="student_team", username="sammy123", password="Password1", full_name="Sam Two"
    )
    assert ok2 is False
    assert "already taken" in msg2.lower()


def test_dynamic_user_authentication(temp_db):
    """Verify registered dynamic accounts can authenticate and wrong passwords fail."""
    auth.register_organization_and_leader(
        org_name="Nexus AI",
        org_type="student_team",
        username="nexus_lead",
        password="LeadSecret@99",
        full_name="Nexus Leader",
    )

    # Correct credentials
    ok, msg, user = auth.authenticate("nexus_lead", "LeadSecret@99")
    assert ok is True
    assert user["username"] == "nexus_lead"
    assert user["name"] == "Nexus Leader"
    assert user["role"] == "Manager"
    assert user["org_type"] == "student_team"

    # Incorrect credentials
    ok_bad, msg_bad, user_bad = auth.authenticate("nexus_lead", "WrongPassword")
    assert ok_bad is False
    assert "invalid" in msg_bad.lower()
    assert user_bad is None


def test_create_member_account_by_leader(temp_db):
    """Verify Team Leader can create Employee (Departing) and Successor (New) member accounts."""
    _, _, leader = auth.register_organization_and_leader(
        org_name="Robotics Club",
        org_type="student_team",
        username="lead_bot",
        password="Password@123",
        full_name="Club Lead",
    )

    # 1. Create Departing Member (Employee role)
    ok_emp, msg_emp, emp_user = auth.create_member_account(
        creator_user=leader,
        username="maya_dev",
        password="MayaPassword@1",
        full_name="Maya Dev",
        role="Employee",
    )
    assert ok_emp is True
    assert emp_user["username"] == "maya_dev"
    assert emp_user["role"] == "Employee"
    assert emp_user["org_id"] == leader["org_id"]

    # 2. Create New Member (Successor role)
    ok_succ, msg_succ, succ_user = auth.create_member_account(
        creator_user=leader,
        username="liam_new",
        password="LiamPassword@1",
        full_name="Liam New",
        role="Successor",
    )
    assert ok_succ is True
    assert succ_user["username"] == "liam_new"
    assert succ_user["role"] == "Successor"
    assert succ_user["org_id"] == leader["org_id"]

    # 3. New members can log in
    ok_login, _, logged_in_emp = auth.authenticate("maya_dev", "MayaPassword@1")
    assert ok_login is True
    assert logged_in_emp["role"] == "Employee"

    ok_login_s, _, logged_in_succ = auth.authenticate("liam_new", "LiamPassword@1")
    assert ok_login_s is True
    assert logged_in_succ["role"] == "Successor"


def test_non_manager_cannot_create_member_account(temp_db):
    """Verify employees or successors cannot create accounts."""
    _, _, leader = auth.register_organization_and_leader(
        org_name="Team A",
        org_type="student_team",
        username="lead_user",
        password="Password@123",
        full_name="Lead User",
    )
    _, _, emp_user = auth.create_member_account(
        creator_user=leader,
        username="worker_one",
        password="WorkerPass@1",
        full_name="Worker",
        role="Employee",
    )

    # Worker tries to create an account
    ok, msg, _ = auth.create_member_account(
        creator_user=emp_user,
        username="sneaky_user",
        password="Password@123",
        full_name="Sneaky",
        role="Successor",
    )
    assert ok is False
    assert "only team leaders and managers" in msg.lower()


def test_role_labels_by_org_type():
    """Verify get_role_label switches terminology between student teams and corporate orgs."""
    # Student team labels
    assert get_role_label("Manager", "student_team") == "Team Leader"
    assert get_role_label("Employee", "student_team") == "Departing Team Member"
    assert get_role_label("Successor", "student_team") == "New Team Member"

    # Corporate company labels
    assert get_role_label("Manager", "company") == "Manager"
    assert get_role_label("Employee", "company") == "Departing employee"
    assert get_role_label("Successor", "company") == "New joinee"

    # Default fallback (backward compatibility)
    assert get_role_label("Manager") == "Manager"
    assert get_role_label("Employee") == "Departing employee"
    assert get_role_label("Successor") == "New joinee"


def test_list_org_users_isolation(temp_db):
    """Verify list_org_users returns only users in that organization and isolates teams."""
    # Org A
    _, _, lead_a = auth.register_organization_and_leader(
        "Team A", "student_team", "lead_a", "Pass@123", "Leader A"
    )
    auth.create_member_account(lead_a, "member_a1", "Pass@123", "Member A1", "Employee")

    # Org B
    _, _, lead_b = auth.register_organization_and_leader(
        "Team B", "company", "lead_b", "Pass@123", "Leader B"
    )
    auth.create_member_account(lead_b, "member_b1", "Pass@123", "Member B1", "Successor")

    users_a = auth.list_org_users(lead_a["org_id"])
    users_b = auth.list_org_users(lead_b["org_id"])

    usernames_a = {u["username"] for u in users_a}
    usernames_b = {u["username"] for u in users_b}

    assert "lead_a" in usernames_a
    assert "member_a1" in usernames_a
    assert "lead_b" not in usernames_a
    assert "member_b1" not in usernames_a

    assert "lead_b" in usernames_b
    assert "member_b1" in usernames_b
    assert "lead_a" not in usernames_b
    assert "member_a1" not in usernames_b


def test_backward_compatibility_demo_accounts(temp_db):
    """Verify demo accounts manager, sarah, and marcus continue to work with passwords and 1-click."""
    # Passwords
    ok_m, _, u_m = auth.authenticate("manager", "Manager@123")
    assert ok_m is True
    assert u_m["role"] == "Manager"

    ok_s, _, u_s = auth.authenticate("sarah", "Sarah@123")
    assert ok_s is True
    assert u_s["role"] == "Employee"

    ok_v, _, u_v = auth.authenticate("marcus", "Marcus@123")
    assert ok_v is True
    assert u_v["role"] == "Successor"

    # 1-click quick demo authentication
    ok_q, _, u_q = auth.authenticate_demo("manager")
    assert ok_q is True
    assert u_q["username"] == "manager"
