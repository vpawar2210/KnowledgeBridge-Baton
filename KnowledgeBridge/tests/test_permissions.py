"""Tests for permissions, grants, and exports in Baton.

Verifies:
5. Marcus gets a confidential claim quote as redacted
6. Grant for file A does not unlock file B
7. Approved grant unlocks file A for marcus
8. Revoked or rejected grant locks it again
9. Journal export and dossier export contain no confidential text for marcus without grant
14. Sources passed to model for unauthorized role contain no confidential text
"""

import copy
import json
import sqlite3
import pytest

import utils.store as store
import utils.access as access
import utils.demo_seed as demo_seed
from utils.crypto import REDACTION_PLACEHOLDER
from utils.gemini_engine import analyze_sources


def test_5_marcus_gets_confidential_claim_quote_as_redacted():
    """(5) Marcus gets a confidential claim quote as redacted."""
    demo_seed.ensure_demo_database_seeded(force_reset=True, completed=True)

    marcus_user = {"id": "marcus", "username": "marcus", "role": "Successor", "name": "Marcus Vance"}
    state, _ = store.load_project_state(user=marcus_user)
    kp = state.get("knowledge_profile") or {}
    risks = kp.get("risks", [])

    # Finding F-015 cites NOTE-004 which is confidential
    conf_claims = [r for r in risks if r.get("source") == "NOTE-004"]
    assert len(conf_claims) > 0
    for claim in conf_claims:
        assert claim.get("sensitivity") == "confidential"
        assert claim.get("excerpt") == REDACTION_PLACEHOLDER


def test_6_and_7_grant_for_file_a_unlocks_file_a_not_file_b():
    """(6) A grant for file A does not unlock file B.
    (7) An approved grant unlocks file A for marcus.
    """
    demo_seed.ensure_demo_database_seeded(force_reset=True, completed=True)

    marcus_user = {"id": "marcus", "username": "marcus", "role": "Successor", "name": "Marcus Vance"}
    manager_user = {"id": "manager", "username": "manager", "role": "Manager", "name": "Manager"}

    # Initially, both DOC-TRB-008 and DOC-FIN-009 are locked for Marcus
    assert store.get_file_text("DOC-TRB-008", user=marcus_user) == REDACTION_PLACEHOLDER
    assert store.get_file_text("DOC-FIN-009", user=marcus_user) == REDACTION_PLACEHOLDER

    # Manager approves grant for DOC-TRB-008 ONLY
    state, _ = store.load_project_state()
    req = access.create_request(state, marcus_user, "confidential_read", "Need tribal knowledge", file_id="DOC-TRB-008")

    # Approve request
    access.decide_request(state, manager_user, req["id"], approve=True, comment="Approved for DOC-TRB-008 only")

    # (7) Approved grant unlocks file A (DOC-TRB-008)
    unlocked_text = store.get_file_text("DOC-TRB-008", user=marcus_user)
    assert unlocked_text != REDACTION_PLACEHOLDER
    assert "reconciliation" in unlocked_text.lower()

    # (6) Grant for file A does NOT unlock file B (DOC-FIN-009)
    locked_text = store.get_file_text("DOC-FIN-009", user=marcus_user)
    assert locked_text == REDACTION_PLACEHOLDER


def test_8_revoked_grant_locks_it_again():
    """(8) A revoked or rejected grant locks it again."""
    demo_seed.ensure_demo_database_seeded(force_reset=True, completed=True)

    marcus_user = {"id": "marcus", "username": "marcus", "role": "Successor", "name": "Marcus Vance"}
    manager_user = {"id": "manager", "username": "manager", "role": "Manager", "name": "Manager"}

    # Give grant then revoke
    state, _ = store.load_project_state()
    access.set_grants(state, manager_user, "marcus", ["confidential_read:DOC-TRB-008"])
    assert store.get_file_text("DOC-TRB-008", user=marcus_user) != REDACTION_PLACEHOLDER

    # Revoke grant
    access.set_grants(state, manager_user, "marcus", [])
    assert store.get_file_text("DOC-TRB-008", user=marcus_user) == REDACTION_PLACEHOLDER


def test_9_journal_and_dossier_contain_no_confidential_text_for_marcus():
    """(9) The journal export and dossier export contain no confidential text for marcus without a grant."""
    demo_seed.ensure_demo_database_seeded(force_reset=True, completed=True)

    marcus_user = {"id": "marcus", "username": "marcus", "role": "Successor", "name": "Marcus Vance"}
    state, _ = store.load_project_state(user=marcus_user)

    dossier = state.get("newhire_handover") or ""
    notes = state.get("successor_notes") or []
    journal_export = "\n".join(n.get("content", "") for n in notes)

    conf_phrases = [
        "upstream ledger closes at 18:00 IST",
        "REF-001,Goodwill refund",
        "When the alert is noisy but customer impact is unclear",
    ]
    for p in conf_phrases:
        assert p not in dossier
        assert p not in journal_export


def test_14_sources_passed_to_model_contain_no_confidential_text(monkeypatch):
    """(14) The sources passed to the model for an unauthorized role contain no confidential text."""
    recorded_prompts = []

    def mock_call_gemini(prompt, api_key, **kwargs):
        recorded_prompts.append(prompt)
        return '{"decisions": [], "risks": [], "unresolved": []}'

    import utils.gemini_engine as gemini_mod
    monkeypatch.setattr(gemini_mod, "_call_gemini", mock_call_gemini)

    conf_source = {
        "content": "Secret reconciliation policy: upstream ledger closes at 18:00 IST and password: secret_db_pw.",
        "source": "DOC-TRB-008",
        "source_type": "file",
        "classification": "confidential",
    }
    normal_source = {
        "content": "Public API rate limits are 50 req/s.",
        "source": "DOC-API-003",
        "source_type": "file",
        "classification": "normal",
    }

    marcus_user = {"id": "marcus", "username": "marcus", "role": "Successor"}
    analyze_sources([conf_source, normal_source], api_key="dummy_key", user=marcus_user)

    assert len(recorded_prompts) == 1
    prompt_text = recorded_prompts[0]

    # Confidential text must be redacted before sending to model
    assert "upstream ledger closes at 18:00 IST" not in prompt_text
    assert "secret_db_pw" not in prompt_text
    assert REDACTION_PLACEHOLDER in prompt_text
    assert "Public API rate limits" in prompt_text
