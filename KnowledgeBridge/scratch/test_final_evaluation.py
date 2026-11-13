"""
Final evaluation test for Baton demo seeding.
Checks all 5 required criteria.
Run from workspace root: python KnowledgeBridge/scratch/test_final_evaluation.py
"""
import sys, os
from pathlib import Path

# Insert project root so imports resolve
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.chdir(str(Path(__file__).resolve().parent.parent))

# ── Remove old DB for a clean start ──────────────────────────────────────────
db_path = Path("data/baton.db")
if db_path.exists():
    db_path.unlink()
    print("Old DB removed — starting fresh")

from utils.demo_seed import ensure_demo_database_seeded, load_completed_handover, reset_demo_data
from utils.store import load_project_state

results = {}

# ─────────────────────────────────────────────────────────────────────────────
# CHECK 1: First start seeds correctly
# ─────────────────────────────────────────────────────────────────────────────
try:
    ensure_demo_database_seeded()
    state, notice = load_project_state()

    assert state.get("knowledge_profile") is not None, "no knowledge_profile"
    assert state.get("employee_name") in ("Sarah Chen", "sarah"), f"wrong employee_name: {state.get('employee_name')}"
    assert state.get("approvals", None) is not None, "approvals key missing"
    assert len(state.get("approvals", {"_": 1})) == 0, f"start approvals not empty: {state.get('approvals')}"
    assert state.get("manager_handover") is None, f"start state should have no handover, got: {state.get('manager_handover')!r:.40}"
    members = state.get("members", [])
    assert len(members) == 3, f"expected 3 members, got {len(members)}"
    notifs = state.get("notifications", [])
    assert len(notifs) >= 1, f"expected notifications, got {len(notifs)}"
    reqs = state.get("access_requests", [])
    assert len(reqs) >= 1, "no access_requests seeded"
    marcus_req = next((r for r in reqs if r.get("requester_id") == "marcus"), None)
    assert marcus_req is not None, "no access request from marcus"
    assert marcus_req.get("type") == "normal_write", f"wrong request type: {marcus_req.get('type')}"

    results["CHECK 1"] = "PASS — first start seeds correctly"
except AssertionError as e:
    results["CHECK 1"] = f"FAIL — {e}"
except Exception as e:
    results["CHECK 1"] = f"ERROR — {e}"

# ─────────────────────────────────────────────────────────────────────────────
# CHECK 2: Seeding twice gives no duplicates
# ─────────────────────────────────────────────────────────────────────────────
try:
    ensure_demo_database_seeded()   # second call — must be idempotent
    state2, _ = load_project_state()

    members2 = state2.get("members", [])
    assert len(members2) == 3, f"duplicate members after 2nd seed: {len(members2)}"

    notifs2 = state2.get("notifications", [])
    notifs1 = state.get("notifications", [])
    assert len(notifs2) == len(notifs1), f"duplicate notifications: {len(notifs2)} vs {len(notifs1)}"

    reqs2 = state2.get("access_requests", [])
    assert len(reqs2) == 1, f"duplicate access_requests: {len(reqs2)}"

    results["CHECK 2"] = "PASS — seeding twice gives no duplicates"
except AssertionError as e:
    results["CHECK 2"] = f"FAIL — {e}"
except Exception as e:
    results["CHECK 2"] = f"ERROR — {e}"

# ─────────────────────────────────────────────────────────────────────────────
# CHECK 3: Reset restores start state
# ─────────────────────────────────────────────────────────────────────────────
try:
    load_completed_handover()
    state_c, _ = load_project_state()
    n_true = sum(1 for v in state_c.get("approvals", {}).values() if v is True)
    assert n_true >= 5, f"completed state should have 5 true approvals, got {n_true}"

    reset_demo_data()
    state_r, _ = load_project_state()
    assert len(state_r.get("approvals", {"_": 1})) == 0, f"reset did not clear approvals: {state_r.get('approvals')}"
    assert state_r.get("manager_handover") is None, "reset did not clear manager_handover"
    assert state_r.get("newhire_handover") is None, "reset did not clear newhire_handover"

    results["CHECK 3"] = "PASS — reset restores start state"
except AssertionError as e:
    results["CHECK 3"] = f"FAIL — {e}"
except Exception as e:
    results["CHECK 3"] = f"ERROR — {e}"

# ─────────────────────────────────────────────────────────────────────────────
# CHECK 4: Load completed handover lets Marcus view dossier
# ─────────────────────────────────────────────────────────────────────────────
try:
    load_completed_handover()
    state_lc, _ = load_project_state()

    approvals = state_lc.get("approvals", {})
    all_approved = sum(1 for v in approvals.values() if v is True) >= 5
    mh = state_lc.get("manager_handover")
    nh = state_lc.get("newhire_handover")
    has_handover = bool(mh and nh)

    assert all_approved, f"not all approved: {approvals}"
    assert has_handover, f"missing handover: manager_handover={bool(mh)} newhire_handover={bool(nh)}"

    eh = state_lc.get("employee_handover")
    assert eh, "employee_handover missing (Sarah's notes page would be empty)"

    results["CHECK 4"] = "PASS — load completed handover lets Marcus acknowledge"
except AssertionError as e:
    results["CHECK 4"] = f"FAIL — {e}"
except Exception as e:
    results["CHECK 4"] = f"ERROR — {e}"

# ─────────────────────────────────────────────────────────────────────────────
# CHECK 5: Joinee sees no confidential file names
# ─────────────────────────────────────────────────────────────────────────────
try:
    grants = state_lc.get("grants", {})
    marcus_grants = grants.get("marcus", [])
    assert "confidential_read" not in marcus_grants, f"marcus has confidential_read: {marcus_grants}"
    assert "confidential_write" not in marcus_grants, f"marcus has confidential_write: {marcus_grants}"

    # Verify files were materialised in uploads/
    uploads_dir = Path("data/uploads")
    if uploads_dir.exists():
        uploaded_files = list(uploads_dir.iterdir())
        n_files = len(uploaded_files)
    else:
        n_files = 0
    # We expect at least 9 internal files + 2 versions + (4 conf files don't go to uploads necessarily)
    assert n_files >= 9, f"expected >=9 files in data/uploads, got {n_files}"

    results["CHECK 5"] = f"PASS — joinee sees no confidential file names ({n_files} files materialised)"
except AssertionError as e:
    results["CHECK 5"] = f"FAIL — {e}"
except Exception as e:
    results["CHECK 5"] = f"ERROR — {e}"

# ─────────────────────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────────────────────
print()
print("=" * 65)
print("BATON DEMO SEED — FINAL EVALUATION RESULTS")
print("=" * 65)
all_pass = True
for check, result in results.items():
    print(f"  {check}: {result}")
    if not result.startswith("PASS"):
        all_pass = False
print("=" * 65)
print("OVERALL:", "ALL PASS" if all_pass else "SOME FAILURES — see above")
print()

