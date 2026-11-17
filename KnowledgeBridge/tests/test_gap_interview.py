import pytest
from unittest.mock import patch
import utils.store as store
import utils.gemini_engine as gemini_engine
import utils.demo_seed as demo_seed


def test_answer_stored_as_attested_never_verified():
    """1. Answer is always stored with grade 'ATTESTED', never 'VERIFIED'."""
    # Attempt to save with grade='VERIFIED'
    res = store.add_gap_answer(
        gap_id="Q-004",
        question_text="Which dashboard should be used first?",
        answer_text="Use Grafana deployment dashboard.",
        status="answered",
        grade="VERIFIED"
    )

    assert res["grade"] == "ATTESTED"
    assert res["grade"] != "VERIFIED"

    # Verify directly from database
    stored = store.list_gap_answers()
    assert len(stored) == 1
    assert stored[0]["gap_id"] == "Q-004"
    assert stored[0]["grade"] == "ATTESTED"
    assert stored[0]["grade"] != "VERIFIED"


def test_idk_leaves_gap_open():
    """2. 'I don't know' stores status 'unknown' and the gap stays open."""
    initial_open = store.get_open_gaps()
    assert len(initial_open) > 0
    test_gap_id = initial_open[0]["id"]

    res = store.add_gap_answer(
        gap_id=test_gap_id,
        question_text="What exact command is used?",
        answer_text="I don't know",
        status="unknown"
    )

    assert res["status"] == "unknown"
    assert res["grade"] == "ATTESTED"

    # Verify gap remains in open gaps
    open_after = store.get_open_gaps()
    open_ids = [g["id"] for g in open_after]
    assert test_gap_id in open_ids


def test_skip_leaves_gap_open():
    """3. 'Skip' stores status 'skipped' and the gap stays open."""
    initial_open = store.get_open_gaps()
    assert len(initial_open) > 0
    test_gap_id = initial_open[0]["id"]

    res = store.add_gap_answer(
        gap_id=test_gap_id,
        question_text="What is the escalation contact?",
        answer_text="Skipped",
        status="skipped"
    )

    assert res["status"] == "skipped"
    assert res["grade"] == "ATTESTED"

    # Verify gap remains in open gaps
    open_after = store.get_open_gaps()
    open_ids = [g["id"] for g in open_after]
    assert test_gap_id in open_ids


def test_empty_or_whitespace_answer_rejected():
    """4. Empty or whitespace-only answers are rejected with ValueError."""
    with pytest.raises(ValueError, match="cannot be empty or whitespace-only"):
        store.add_gap_answer(
            gap_id="Q-004",
            question_text="Which dashboard?",
            answer_text="",
            status="answered"
        )

    with pytest.raises(ValueError, match="cannot be empty or whitespace-only"):
        store.add_gap_answer(
            gap_id="Q-004",
            question_text="Which dashboard?",
            answer_text="   \t   \n  ",
            status="answered"
        )


def test_saving_same_gap_twice_leaves_one_row():
    """5. Saving the same gap again updates it without duplicate rows."""
    store.add_gap_answer(
        gap_id="Q-004",
        question_text="Which dashboard?",
        answer_text="First answer: Grafana",
        status="answered"
    )

    rows_1 = store.list_gap_answers()
    assert len(rows_1) == 1
    assert rows_1[0]["answer_text"] == "First answer: Grafana"

    # Save again for the same gap_id
    store.add_gap_answer(
        gap_id="Q-004",
        question_text="Which dashboard?",
        answer_text="Second updated answer: Datadog",
        status="answered"
    )

    rows_2 = store.list_gap_answers()
    assert len(rows_2) == 1
    assert rows_2[0]["answer_text"] == "Second updated answer: Datadog"


def test_only_open_gaps_are_asked():
    """6. Only open gaps are returned and asked; answered gaps are excluded."""
    open_gaps = store.get_open_gaps()
    open_ids = [g["id"] for g in open_gaps]

    # Pre-answered questions in mock data (Q-001, Q-002, Q-003) must not be in open gaps
    assert "Q-001" not in open_ids
    assert "Q-002" not in open_ids
    assert "Q-003" not in open_ids

    # Answer one of the open gaps
    target_id = open_ids[0]
    store.add_gap_answer(
        gap_id=target_id,
        question_text="Operational question",
        answer_text="Detailed resolution instructions.",
        status="answered"
    )

    # After answering, it must be removed from open gaps
    remaining_open = store.get_open_gaps()
    remaining_ids = [g["id"] for g in remaining_open]
    assert target_id not in remaining_ids


def test_answers_appear_in_successor_dossier_with_label():
    """7. Attested answers appear in successor dossier with explicit [ATTESTED] label."""
    store.add_gap_answer(
        gap_id="Q-004",
        question_text="Which dashboard should be used first?",
        answer_text="Grafana deployment health dashboard on port 3000.",
        status="answered"
    )

    # 1. Test generate_newhire_handover with mocked Gemini call
    with patch("utils.gemini_engine._call_gemini", return_value="# Technical Successor Handover\n\nIntro text."):
        dossier = gemini_engine.generate_newhire_handover(
            knowledge_profile={"unresolved": []},
            employee_name="Sarah Chen",
            project_role="Platform Engineer",
            api_key="mock_key"
        )

    assert "## Leaver-attested answers (from memory, not source-verified)" in dossier
    assert "[ATTESTED]" in dossier
    assert "Grafana deployment health dashboard on port 3000." in dossier

    # 2. Test demo_seed._build_newhire_handover
    static_dossier = demo_seed._build_newhire_handover({"questions": []})
    assert "## Leaver-attested answers (from memory, not source-verified)" in static_dossier
    assert "[ATTESTED]" in static_dossier
    assert "Grafana deployment health dashboard on port 3000." in static_dossier


def test_gemini_failure_uses_fallback_question():
    """8. When Gemini fails, times out or returns empty, fallback question is used without crash."""
    gap_data = {
        "id": "Q-005",
        "question": "What exact command is used to recycle the affected worker pool?",
        "why_unknown": "Identified in postmortem."
    }

    # Case A: No API key provided -> returns fallback
    q_no_key = gemini_engine.generate_followup(gap_data, api_key="")
    assert q_no_key == gap_data["question"]

    # Case B: Gemini raises Exception/Timeout -> returns fallback without crash
    with patch("utils.gemini_engine._call_gemini", side_effect=Exception("API Timeout or TLS handshake failure")):
        q_err = gemini_engine.generate_followup(gap_data, api_key="some_key")
        assert q_err == gap_data["question"]

    # Case C: Gemini returns empty response -> returns fallback
    with patch("utils.gemini_engine._call_gemini", return_value="   "):
        q_empty = gemini_engine.generate_followup(gap_data, api_key="some_key")
        assert q_empty == gap_data["question"]
