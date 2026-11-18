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

---

## Role-Based Redaction & Encryption at Rest

### Summary of Changes
Implemented granular document-level and field-level redaction enforced directly in the data-access layer (`utils/store.py` and `utils/access.py`), paired with AES-CBC/Fernet encryption of confidential text at rest (`utils/crypto.py`).

1. **Files Touched**:
   - `KnowledgeBridge/requirements.txt`: Added `cryptography` dependency on a new line.
   - `KnowledgeBridge/.gitignore`: Added `data/.baton_key`, `.baton_key`, and `*.key`.
   - `KnowledgeBridge/utils/crypto.py` (NEW): Key management via `BATON_DATA_KEY` / `data/.baton_key`, `encrypt_text()`, `decrypt_text()`, `is_encrypted()`, fail-closed error handling returning placeholder `"[REDACTED - request access]"`.
   - `KnowledgeBridge/utils/access.py`:
     - Identified confidential documents (`CONFIDENTIAL_DOC_IDS = {"DOC-TRB-008", "DOC-FIN-009", "DOC-BCP-010", "DOC-MON-011"}`) and notes (`NOTE-004`).
     - Added `redact()` engine with pattern matching for secrets (API keys, tokens, passwords across all roles), PII (emails, phone numbers), and Harborline financial currency amounts.
     - Added `can_read_file()` and updated `can_read()` with granular `file_id` support.
     - Updated `create_request()` and `decide_request()` to support per-file scoped approvals.
   - `KnowledgeBridge/utils/store.py`:
     - Added `sensitivity` column (`TEXT NOT NULL DEFAULT 'normal'`) to `files` table schema and dynamic migration in `_ensure_schema()`.
     - Added `file_id` column (`TEXT DEFAULT NULL`) to `grants` and `access_requests` table schemas.
     - Added `get_file_sensitivity()`, `can_user_read_file()`, and `get_file_text()`.
     - Updated `register_file()`, `_read_grants()`, `_read_access_requests()`, `_read_confidential_files()`, and `modify_project_state()`.
     - Updated `_assemble_state()` to enforce role redaction on confidential claims, unwritten rules, dossier texts, and file contents.
     - Updated `load_into_session(session_state, user=None)` and `load_project_state(user=None)` to accept `user` parameter; direct calls with no user default strictly to the restricted successor view.
   - `KnowledgeBridge/utils/demo_seed.py`:
     - Updated table schemas and seeding to store confidential files (`files.extracted_text`) and findings encrypted with `"enc:v1:"` prefix at rest.
   - `KnowledgeBridge/utils/gemini_engine.py`:
     - Updated `analyze_sources(texts, api_key, user=None)` to pre-filter and redact confidential sources and secret patterns for unauthorized users.
   - `KnowledgeBridge/app.py`:
     - Updated line 814 `load_into_session(st.session_state, user=user)`.
     - Updated line 3112 `can_read(cur_user, is_confidential=True, state=st.session_state, file_id=cf.get("id"))`.
   - `KnowledgeBridge/migrate_encrypt.py` (NEW):
     - Standalone, idempotent migration script requiring `--yes` flag to encrypt confidential plaintext rows at rest and perform `VACUUM` and `PRAGMA wal_checkpoint(TRUNCATE)`.
   - `KnowledgeBridge/QUESTIONS.md` (NEW):
     - Question regarding `DOC-SEC-002` classification logged per instructions.
   - `KnowledgeBridge/tests/conftest.py`:
     - Added fixture isolating `demo_seed.DB_FILE` and `demo_seed.UPLOADS_DIR` to temporary directories.
   - `KnowledgeBridge/tests/test_redaction_storage.py` and `KnowledgeBridge/tests/test_permissions.py` (NEW):
     - Comprehensive test suites verifying all 14 criteria.

2. **Tables and Columns Added**:
   - `files`: Added column `sensitivity TEXT NOT NULL DEFAULT 'normal'`.
   - `grants`: Added column `file_id TEXT DEFAULT NULL`.
   - `access_requests`: Added column `file_id TEXT DEFAULT NULL`.

3. **Grant Mapping**:
   - Broad grants (`grant_type = 'confidential_read'` with `file_id IS NULL`) grant access to all confidential files (legacy compatibility).
   - Per-file grants are stored as `grant_type = 'confidential_read:{file_id}'` with `file_id = '{file_id}'`.
   - Checking a file checks either a specific grant `confidential_read:{file_id}` (or `file_id == req_file_id`) or a broad grant `confidential_read`.
   - Approving file A adds only `confidential_read:file_A` and does NOT unlock file B.
   - Rejecting or revoking deletes the grant and relocks the file.

4. **Verification Performed**:
   - Executed full pytest suite (`pytest tests/`): all 30 tests passed.
   - Verified AST parse of `app.py`.
   - Executed Step 7 baseline snapshot comparison (`scratch/compare_baseline.py`): Manager and Sarah outputs are 100% byte/content identical; Marcus receives redacted placeholders for confidential excerpts, files, and findings while normal text remains identical.
   - Real database `data/baton.db` kept completely untouched.



## Deadlock Fix (utils/store.py) — branch deadlock-fix

**Bug**: `modify_project_state` held a write transaction while calling
`_assemble_state`, which called `get_file_sensitivity(src)` opening a
second write connection (via `_ensure_schema`), causing a 30-second
self-deadlock per confidential source file.

**Fix**:
- `get_file_sensitivity(file_id, con=None)`: accepts optional connection; when
  `con` is passed, reuses it. When `con=None`, opens a read-only connection
  with `PRAGMA query_only = ON` — no `_ensure_schema`, no writes.
- `can_user_read_file(user, file_id, con=None)`: passes `con` through to
  `get_file_sensitivity`; `con=None` path uses read-only connection
  with `PRAGMA query_only = ON` — no `_ensure_schema`, no writes.
- `_assemble_state`: passes `con` to `get_file_sensitivity(src, con=con)`.
- `modify_project_state`: removed redundant `_ensure_schema(con)` inside write
  transaction (`_init_db()` already ran schema setup before the transaction).
- `get_file_text`: calls `get_file_sensitivity(file_id, con=con)` **inside**
  the open connection block instead of before it (sequential, not nested).
- Connection timeout reduced from 30 s to 10 s to surface future deadlocks faster.
- Added 7 regression tests in `tests/test_no_deadlock.py`.

**Result**: `pytest tests/ -v --timeout=60` → 37 passed in 2.76 s (was stuck for
60+ s per confidential source before).

## Deadlock regression tests strengthened (tests/test_no_deadlock.py)

Tests 1–5 now use the full demo seed (same as test_permissions.py) so the
knowledge_profile claims with sources NOT in CONFIDENTIAL_SOURCES
(DOC-INC-001, DOC-REF-004, DOC-REL-006, etc.) force the real DB-lookup
path of get_file_sensitivity — the exact path that deadlocked on old code.
Added a structural test that wraps sqlite3.connect with a concurrent-
connection counter and asserts the peak is exactly 1 inside
modify_project_state.  Test 6 split into 6a (no-con path) and 6b (con= path)
so each failure is independently diagnosable.  Test 7 unchanged.
Total: 39 tests, all pass.

## Failure-Case & Adversarial Test Suite (tests/test_quote_tamper.py, utils/verifier.py)

Added formal quote verification and adversarial failure-case test harness:
- `utils/verifier.py`: Grounding and citation verification engine with `verify_quote()` and `verify_claim()`. Mathematically checks exact/normalized substring grounding against project documents, rejects fabricated/hallucinated quotes, detects altered numbers, blocks adversarial prompt injection patterns, rejects nonexistent/mismatched source IDs, and enforces minimum quote length.
- `tests/test_quote_tamper.py`: 6 automated tests validating all 5 failure modes plus authentic citation acceptance:
  1. `test_tamper_1_rejects_completely_fabricated_quote`
  2. `test_tamper_2_rejects_altered_numeric_value_in_quote`
  3. `test_tamper_3_rejects_adversarial_prompt_injection_in_quote`
  4. `test_tamper_4_rejects_nonexistent_or_mismatched_source_document`
  5. `test_tamper_5_rejects_vacuous_short_quote`
  6. `test_authentic_unaltered_quote_passes_verification`
- Combined with `tests/test_permissions.py` (5 permission breach tests) and `tests/test_redaction_storage.py` (8 data leakage tests), total test suite now runs **45 automated failure-case and regression tests with 100% pass rate in < 3s**.

## Performance Optimization & Windows Defender Fix (app.py, utils/gemini_engine.py, utils/store.py)

- **Windows Defender / SmartApp Control Popup Fix**:
  - Set `BATON_SAFE_TABLES=1` automatically in `app.py` runtime. Prevents Streamlit's `st.table()` from importing or invoking `pyarrow._compute` (`_compute.cp313-win_amd64.pyd`), eliminating the Windows security warning popup and the associated 30-second thread hang.
- **Fast Gap Interview Assistant Loading**:
  - Streamlined `generate_followup` in `utils/gemini_engine.py` with an aggressive 4-second timeout limit. If Gemini API is delayed, unreachable, or slow, it immediately falls back to the clean, direct gap question without blocking the browser.
  - Wrapped followup generation in Streamlit spinner (`with st.spinner("Preparing focused question..."):`) for visual feedback during generation.
  - Deduplicated `FOLLOWUP_INTERVIEW_PROMPT` and `generate_followup` definitions.
- **SQLite Read Path Optimization**:
  - Replaced redundant `_ensure_schema(con)` calls inside `add_gap_answer`, `list_gap_answers`, `gap_progress`, and `get_open_gaps` with `_init_db()`. Reading open gaps and calculating progress is now instantaneous (< 1ms) without executing table inspection DDL on every frame.
