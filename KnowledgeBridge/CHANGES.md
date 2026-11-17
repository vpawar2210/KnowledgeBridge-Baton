# CHANGES — Gap Interview Engine Implementation

## Summary of Changes
Implemented the targeted conversational **Gap Interview Engine** in BATON (KnowledgeBridge) to prompt the departing engineer (Sarah Chen) for missing context from unresolved knowledge gaps. All submitted answers receive an explicit `[ATTESTED]` grade and are woven into the technical successor dossier and manager review screen.

## 1. Files Touched
- `KnowledgeBridge/utils/store.py`:
  - Added table `gap_answers` to SQLite schema (`_SCHEMA_SQL`).
  - Added unique index `idx_gap_answers_gap_id` preventing duplicate entries.
  - Implemented `add_gap_answer(gap_id, question_text, answer_text, status, author, grade)` enforcing strict `ATTESTED` grade, upsert on existing `gap_id`, 2000-character limit, control character stripping, and whitespace validation.
  - Implemented `list_gap_answers(status)`.
  - Implemented `gap_progress(total_gaps)` calculating cumulative answered gaps (base pre-answered + interview answered).
  - Implemented `get_open_gaps()` reading open gaps dynamically from data/profile without hardcoding.
- `KnowledgeBridge/utils/demo_seed.py`:
  - Added `gap_answers` schema definition to ensure demo resets preserve table structure.
  - Updated `_build_newhire_handover()` static builder to append the `## Leaver-attested answers (from memory, not source-verified)` section with `[ATTESTED]` badges.
- `KnowledgeBridge/utils/gemini_engine.py`:
  - Added `generate_followup(gap, related_claims, api_key)` generating one focused question with graceful fallback to plain gap text on API failure/timeout/empty response.
  - Updated `generate_newhire_handover()` to append the `## Leaver-attested answers (from memory, not source-verified)` section with `[ATTESTED]` badges, quoting leaver answers strictly as DATA.
- `KnowledgeBridge/app.py`:
  - Added the conversational **Gap Interview Assistant** panel in the leaver (`page == "employee"`) screen using `st.chat_message` and `st.chat_input`, showing one question at a time with `Answer`, `I don't know`, and `Skip` actions, immediate SQLite persistence, progress display, session limit (max 5 questions), empty state message, and audit logging via `log_audit_entry`.
  - Updated Manager Review section 3 (`unresolved`) to display leaver-attested answers read-only below existing content with distinct `[ATTESTED]` badges without altering existing text or gate logic.
- `KnowledgeBridge/tests/conftest.py`:
  - Pytest setup isolating every test to a temporary SQLite database in `tmp_path`, ensuring `data/baton.db` is never touched.
- `KnowledgeBridge/tests/test_gap_interview.py`:
  - Added comprehensive test suite with 8 tests covering all requirements.

## 2. Tables Added
- `gap_answers`:
  - `id` TEXT PRIMARY KEY
  - `gap_id` TEXT NOT NULL
  - `question_text` TEXT NOT NULL
  - `answer_text` TEXT NOT NULL
  - `grade` TEXT NOT NULL DEFAULT 'ATTESTED'
  - `status` TEXT NOT NULL ('answered', 'unknown', 'skipped')
  - `author` TEXT NOT NULL DEFAULT ''
  - `created_at` TEXT NOT NULL
  - Unique Index: `idx_gap_answers_gap_id ON gap_answers(gap_id)`

## 3. Verification Performed
- **Automated Test Suite**:
  - Ran `pytest tests/` in `KnowledgeBridge/` — 8 passed in 1.03s.
  - Verified 100% test coverage of all 8 core criteria:
    1. Answer stored as `ATTESTED`, never `VERIFIED`.
    2. "I don't know" leaves gap open.
    3. "Skip" leaves gap open.
    4. Empty or whitespace-only answers rejected.
    5. Saving same gap twice updates without duplicates (single row).
    6. Only open gaps are asked (pre-answered and resolved gaps excluded).
    7. Answers appear in successor dossier with `[ATTESTED]` badge.
    8. Gemini failure uses fallback question safely without crashing.
- **Safety Verification**:
  - SHA256 checksum and size of `KnowledgeBridge/data/baton.db` verified before and after test execution (completely untouched).
- **End-to-End System Integrity**:
  - Demo authentication tested and verified for `manager`, `sarah`, and `marcus`.
  - Harborline dataset verified intact (8 decisions, 8 risks, 5 unresolved questions).
  - 5-section manager approval gate verified: blocks generation at fewer than 5 approvals and unlocks at 5 of 5 approvals.

---

## Local Windows Workaround (Pyarrow Fix)
Local Windows workaround: tables fall back to Markdown when pandas/pyarrow is blocked. Hosted behavior unchanged. This commit is LOCAL ONLY and must be reviewed before deploy.
- Added `KnowledgeBridge/utils/safe_table.py` (`safe_table`, `format_table_markdown`).
- Replaced 3 call sites in `KnowledgeBridge/app.py` with `safe_table`.
- Added unit tests in `KnowledgeBridge/tests/test_safe_table.py` (9 tests passing).

