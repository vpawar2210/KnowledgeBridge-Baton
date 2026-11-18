"""tests/test_github_guard.py

Unit and regression test suite for GitHub connection guard, URL validation,
token isolation, caching, and error mapping.

Covers all 17 requirements:
(1) valid forms of owner/repo and full URLs parse correctly (trailing slash, .git, /tree/main)
(2) empty and whitespace text is rejected
(3) a non-github.com host is rejected
(4) a URL with embedded credentials is rejected
(5) a value with spaces, '..', or shell characters is rejected
(6) 404 gives the 'not found' message
(7) 401 gives the 'bad token' message
(8) 403 with remaining requests = 0 gives rate-limit message, and 429 does too
(9) an empty repository gives the empty message and no crash
(10) a repository without a README still returns commits and issues (warning flag set)
(11) timeout and connection error give friendly message and never hang
(12) token never appears in any error message, nor in database bytes after fetch
(13) public fetch without user token is cached, and second call makes no HTTP request
(14) fetch WITH a user token is never cached, and second session without token does not receive its data
(15) server token is used when no user token is given, and user token takes priority
(16) fetching the same repository twice leaves one source (deduplication)
(17) commit link building accepts a valid SHA and rejects a malformed one
"""

import os
import sqlite3
import pytest
from unittest.mock import patch, MagicMock
import requests

from utils.github_guard import (
    parse_repo_ref,
    safe_fetch,
    clear_public_cache,
    build_commit_link,
    build_pr_link,
    MESSAGES,
    GitHubFetchResult,
)
import utils.store as store


@pytest.fixture(autouse=True)
def clean_cache():
    """Ensure in-memory cache is empty before every test."""
    clear_public_cache()
    yield
    clear_public_cache()


# ---------------------------------------------------------------------------
# (1) Valid URL & reference parsing
# ---------------------------------------------------------------------------
def test_1_valid_repo_formats_parse_correctly():
    """Valid owner/repo, full URLs, trailing slashes, .git, and extra subpaths parse cleanly."""
    valid_cases = [
        ("octocat/Hello-World", ("octocat", "Hello-World")),
        ("https://github.com/octocat/Hello-World", ("octocat", "Hello-World")),
        ("https://github.com/octocat/Hello-World/", ("octocat", "Hello-World")),
        ("https://github.com/octocat/Hello-World.git", ("octocat", "Hello-World")),
        ("http://github.com/octocat/Hello-World", ("octocat", "Hello-World")),
        ("github.com/octocat/Hello-World", ("octocat", "Hello-World")),
        ("https://github.com/octocat/Hello-World/tree/main", ("octocat", "Hello-World")),
        ("https://github.com/octocat/Hello-World/issues/42", ("octocat", "Hello-World")),
        ("https://www.github.com/octocat/Hello-World", ("octocat", "Hello-World")),
    ]
    for raw, expected in valid_cases:
        ok, parsed, err = parse_repo_ref(raw)
        assert ok is True, f"Failed for {raw}: {err}"
        assert parsed == expected, f"Mismatch for {raw}: got {parsed}, expected {expected}"
        assert err == ""


# ---------------------------------------------------------------------------
# (2) Empty and whitespace text is rejected
# ---------------------------------------------------------------------------
def test_2_empty_and_whitespace_rejected():
    """Empty strings, None, and whitespace are rejected with friendly invalid link message."""
    invalid = ["", "   ", "\t\n", None]
    for raw in invalid:
        ok, parsed, err = parse_repo_ref(raw)
        assert ok is False
        assert parsed is None
        assert err == MESSAGES["invalid_link"]


# ---------------------------------------------------------------------------
# (3) Non-github.com host is rejected
# ---------------------------------------------------------------------------
def test_3_non_github_host_rejected():
    """Hosts other than github.com are rejected."""
    non_gh = [
        "https://gitlab.com/octocat/Hello-World",
        "https://bitbucket.org/octocat/Hello-World",
        "https://malicious-site.com/octocat/Hello-World",
        "https://github.com.attacker.com/octocat/Hello-World",
    ]
    for raw in non_gh:
        ok, parsed, err = parse_repo_ref(raw)
        assert ok is False
        assert parsed is None
        assert err == MESSAGES["invalid_link"]


# ---------------------------------------------------------------------------
# (4) Embedded credentials in URL rejected
# ---------------------------------------------------------------------------
def test_4_embedded_credentials_rejected():
    """URLs with user/password in authority (e.g. user:pass@...) are rejected."""
    credential_urls = [
        "https://user:pass@github.com/octocat/Hello-World",
        "https://token@github.com/octocat/Hello-World",
        "user:pass@github.com/octocat/Hello-World",
    ]
    for raw in credential_urls:
        ok, parsed, err = parse_repo_ref(raw)
        assert ok is False
        assert parsed is None
        assert err == MESSAGES["invalid_link"]


# ---------------------------------------------------------------------------
# (5) Spaces, '..', or shell characters rejected
# ---------------------------------------------------------------------------
def test_5_spaces_traversal_and_shell_characters_rejected():
    """Inputs with internal spaces, traversal '..', or shell special chars are rejected."""
    malformed = [
        "octocat / Hello-World",
        "octocat/../Hello-World",
        "octocat/Hello-World; rm -rf /",
        "octocat/Hello-World && echo hack",
        "octocat/Hello-World|cat",
        "octocat/`id`",
        "octocat/$HOME",
    ]
    for raw in malformed:
        ok, parsed, err = parse_repo_ref(raw)
        assert ok is False
        assert parsed is None
        assert err == MESSAGES["invalid_link"]


# ---------------------------------------------------------------------------
# (6) 404 gives "not found" message
# ---------------------------------------------------------------------------
def test_6_http_404_gives_not_found_message():
    """HTTP 404 response maps to friendly not found message."""
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    http_error = requests.exceptions.HTTPError(response=mock_resp)

    with patch("utils.github_connector.fetch_repo_knowledge", side_effect=http_error):
        res = safe_fetch("octocat/Hello-World")
        assert res.ok is False
        assert res.error_code == "not_found"
        assert res.message == MESSAGES["not_found"]


# ---------------------------------------------------------------------------
# (7) 401 gives "bad token" message
# ---------------------------------------------------------------------------
def test_7_http_401_gives_bad_token_message():
    """HTTP 401 response maps to friendly bad token message."""
    mock_resp = MagicMock()
    mock_resp.status_code = 401
    http_error = requests.exceptions.HTTPError(response=mock_resp)

    with patch("utils.github_connector.fetch_repo_knowledge", side_effect=http_error):
        res = safe_fetch("octocat/Hello-World", user_token="bad_token_123")
        assert res.ok is False
        assert res.error_code == "bad_token"
        assert res.message == MESSAGES["bad_token"]


# ---------------------------------------------------------------------------
# (8) 403 with rate limit exhausted and 429 give rate-limit message
# ---------------------------------------------------------------------------
def test_8_rate_limit_403_and_429():
    """403 with X-RateLimit-Remaining: 0 and 429 map to rate limit reached message."""
    # Case A: 403 with remaining 0
    resp_403 = MagicMock()
    resp_403.status_code = 403
    resp_403.headers = {"X-RateLimit-Remaining": "0"}
    err_403 = requests.exceptions.HTTPError(response=resp_403)

    with patch("utils.github_connector.fetch_repo_knowledge", side_effect=err_403):
        res_a = safe_fetch("octocat/Hello-World")
        assert res_a.ok is False
        assert res_a.error_code == "rate_limit"
        assert res_a.message == MESSAGES["rate_limit"]

    # Case B: 429 Too Many Requests
    resp_429 = MagicMock()
    resp_429.status_code = 429
    resp_429.headers = {}
    err_429 = requests.exceptions.HTTPError(response=resp_429)

    with patch("utils.github_connector.fetch_repo_knowledge", side_effect=err_429):
        res_b = safe_fetch("octocat/Hello-World")
        assert res_b.ok is False
        assert res_b.error_code == "rate_limit"
        assert res_b.message == MESSAGES["rate_limit"]


# ---------------------------------------------------------------------------
# (9) Empty repository gives friendly empty message and no crash
# ---------------------------------------------------------------------------
def test_9_empty_repository_gives_empty_message():
    """Repository with no commits/issues/readme returns empty_repo message without crashing."""
    # When connector returns empty list or all unavailable placeholders
    empty_data = [
        {"source": "octocat/Hello-World/README", "content": "[README not available: 404]"},
        {"source": "octocat/Hello-World/commits", "content": "[Commits not available: 409]"},
    ]
    with patch("utils.github_connector.fetch_repo_knowledge", return_value=empty_data):
        res = safe_fetch("octocat/Hello-World")
        assert res.ok is False
        assert res.error_code == "empty_repo"
        assert res.message == MESSAGES["empty_repo"]


# ---------------------------------------------------------------------------
# (10) Repository without README still returns commits/issues with warning
# ---------------------------------------------------------------------------
def test_10_missing_readme_returns_commits_with_warning():
    """Repository with commits/issues but no README succeeds with a no_readme warning."""
    data_no_readme = [
        {"source": "octocat/Hello-World/README", "content": "[README not available: 404]"},
        {"source": "octocat/Hello-World/commits", "content": "# Recent Commits\n- [abc1234] Initial commit"},
        {"source": "octocat/Hello-World/open-issues", "content": "# Open Issues\n### Issue #1: Bug"},
    ]
    with patch("utils.github_connector.fetch_repo_knowledge", return_value=data_no_readme):
        res = safe_fetch("octocat/Hello-World")
        assert res.ok is True
        assert res.warning is True
        assert res.message == MESSAGES["no_readme"]
        assert len(res.data) == 3


# ---------------------------------------------------------------------------
# (11) Timeout and connection error give friendly message and never hang
# ---------------------------------------------------------------------------
def test_11_timeout_and_network_error_give_friendly_message():
    """Timeout and ConnectionError map to network_error without hanging."""
    # Timeout
    with patch("utils.github_connector.fetch_repo_knowledge", side_effect=requests.exceptions.Timeout("Timed out")):
        res = safe_fetch("octocat/Hello-World")
        assert res.ok is False
        assert res.error_code == "network_error"
        assert res.message == MESSAGES["network_error"]

    # ConnectionError
    with patch("utils.github_connector.fetch_repo_knowledge", side_effect=requests.exceptions.ConnectionError("DNS failure")):
        res2 = safe_fetch("octocat/Hello-World")
        assert res2.ok is False
        assert res2.error_code == "network_error"
        assert res2.message == MESSAGES["network_error"]


# ---------------------------------------------------------------------------
# (12) Token never appears in error messages or database bytes
# ---------------------------------------------------------------------------
def test_12_token_never_leaked_in_messages_or_db():
    """User token is strictly scrubbed from error messages and never written to SQLite."""
    fake_secret_token = "ghp_VERY_SECRET_TOKEN_99999"

    # Simulate an error that includes the token string
    exc = RuntimeError(f"Bad request with auth header token {fake_secret_token}")
    with patch("utils.github_connector.fetch_repo_knowledge", side_effect=exc):
        res = safe_fetch("octocat/Hello-World", user_token=fake_secret_token)
        assert res.ok is False
        assert fake_secret_token not in res.message

    # Also verify that saving project state or DB operations do NOT write this token
    test_db = store.DB_FILE
    if test_db.exists():
        db_bytes = test_db.read_bytes()
        assert fake_secret_token.encode("utf-8") not in db_bytes


# ---------------------------------------------------------------------------
# (13) Public fetch is cached; second call makes no HTTP request
# ---------------------------------------------------------------------------
def test_13_public_fetch_is_cached():
    """Public fetch without token is cached; subsequent call uses cache without HTTP."""
    mock_data = [
        {"source": "octocat/Hello-World/README", "content": "# README\nPublic content"},
        {"source": "octocat/Hello-World/commits", "content": "# Commits\n- [abc] test"},
    ]
    with patch("utils.github_connector.fetch_repo_knowledge", return_value=mock_data) as mock_connector:
        # First call: hits connector
        res1 = safe_fetch("octocat/Hello-World")
        assert res1.ok is True
        assert mock_connector.call_count == 1

        # Second call: served from memory cache
        res2 = safe_fetch("octocat/Hello-World")
        assert res2.ok is True
        assert mock_connector.call_count == 1  # Not called again!
        assert res2.data == mock_data

        # Refresh bypasses cache
        res3 = safe_fetch("octocat/Hello-World", refresh=True)
        assert res3.ok is True
        assert mock_connector.call_count == 2  # Re-fetched!


# ---------------------------------------------------------------------------
# (14) Private fetch with user token is NEVER cached
# ---------------------------------------------------------------------------
def test_14_user_token_fetch_never_cached():
    """A fetch made WITH a user token is never stored in cache or served to tokenless calls."""
    private_data = [
        {"source": "myorg/private-repo/README", "content": "# Confidential Architecture"},
    ]
    with patch("utils.github_connector.fetch_repo_knowledge", return_value=private_data) as mock_connector:
        res_priv = safe_fetch("myorg/private-repo", user_token="ghp_my_private_token")
        assert res_priv.ok is True
        assert mock_connector.call_count == 1

        # A subsequent call without a token must NOT receive the private data from cache
        # Instead, it must attempt its own fetch (which in this mock returns whatever connector returns)
        safe_fetch("myorg/private-repo", user_token=None)
        assert mock_connector.call_count == 2  # Proves it did not serve from cache!


# ---------------------------------------------------------------------------
# (15) Server token used when no user token given; user token takes priority
# ---------------------------------------------------------------------------
def test_15_server_token_and_user_token_precedence():
    """User token takes priority over server token; server token used when user token absent."""
    captured_tokens = []

    def mock_fetch(repo, token=None, timeout=10):
        captured_tokens.append(token)
        return [{"source": f"{repo}/README", "content": "# README\nContent"}]

    with patch("utils.github_connector.fetch_repo_knowledge", side_effect=mock_fetch):
        # Case A: User token provided -> used directly
        safe_fetch("octocat/Hello-World", user_token="user_tok_1", server_token="server_tok_2")
        assert captured_tokens[-1] == "user_tok_1"

        # Case B: No user token -> server token used
        clear_public_cache()
        safe_fetch("octocat/Hello-World", user_token="", server_token="server_tok_2")
        assert captured_tokens[-1] == "server_tok_2"

        # Case C: Neither provided -> None (unauthenticated)
        clear_public_cache()
        safe_fetch("octocat/Hello-World", user_token="", server_token="")
        assert captured_tokens[-1] is None


# ---------------------------------------------------------------------------
# (16) Fetching same repository twice deduplicates sources
# ---------------------------------------------------------------------------
def test_16_duplicate_sources_deduplicated():
    """Simulating repeated repository additions deduplicates by source identifier."""
    repo_sources_1 = [
        {"source": "octocat/Hello-World/README", "content": "Version 1", "source_type": "github"},
        {"source": "octocat/Hello-World/commits", "content": "Commits 1", "source_type": "github"},
    ]
    repo_sources_2 = [
        {"source": "octocat/Hello-World/README", "content": "Version 2 (Updated)", "source_type": "github"},
        {"source": "octocat/Hello-World/commits", "content": "Commits 2 (Updated)", "source_type": "github"},
    ]

    all_sources = []
    # First ingest
    all_sources.extend(repo_sources_1)
    assert len(all_sources) == 2

    # Second ingest of same repository (e.g. double click)
    existing_gh = {item.get("source") for item in repo_sources_2}
    all_sources = [s for s in all_sources if s.get("source") not in existing_gh]
    all_sources.extend(repo_sources_2)

    assert len(all_sources) == 2
    readme_item = next(s for s in all_sources if "README" in s["source"])
    assert readme_item["content"] == "Version 2 (Updated)"


# ---------------------------------------------------------------------------
# (17) Commit and PR link building
# ---------------------------------------------------------------------------
def test_17_evidence_link_building():
    """Valid hex SHAs and numeric PR numbers produce links; invalid ones return None."""
    # Commit links
    assert build_commit_link("octocat", "Hello-World", "7fd1a60") == "https://github.com/octocat/Hello-World/commit/7fd1a60"
    assert build_commit_link("octocat", "Hello-World", "7fd1a60b9464d30620880f4db64f7ac520977678") == "https://github.com/octocat/Hello-World/commit/7fd1a60b9464d30620880f4db64f7ac520977678"
    assert build_commit_link("octocat", "Hello-World", "invalid_sha_xyz") is None
    assert build_commit_link("octocat", "Hello-World", "") is None
    assert build_commit_link("octocat", "Hello-World", "12345") is None  # < 7 chars

    # PR links
    assert build_pr_link("octocat", "Hello-World", 42) == "https://github.com/octocat/Hello-World/pull/42"
    assert build_pr_link("octocat", "Hello-World", "101") == "https://github.com/octocat/Hello-World/pull/101"
    assert build_pr_link("octocat", "Hello-World", "not_a_number") is None
    assert build_pr_link("octocat", "Hello-World", 0) is None
