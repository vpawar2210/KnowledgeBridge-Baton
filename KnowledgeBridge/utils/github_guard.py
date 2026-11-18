"""utils/github_guard.py

Safety, validation, error mapping, and caching layer for GitHub repository connections.
Protects Baton from invalid URLs, credential leaks, rate limits, and network hangs.
"""

import os
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import requests

# Friendly messages required by specification
MESSAGES = {
    "invalid_link": "That doesn't look like a GitHub repository link. Try owner/repo, for example octocat/Hello-World.",
    "not_found": "We couldn't find that repository. It may not exist, or it may be private. For a private repository, add a token.",
    "bad_token": "GitHub did not accept that token. Check it has read access to the repository.",
    "rate_limit": "GitHub's request limit was reached. Please try again in a few minutes.",
    "empty_repo": "This repository has no content yet. You can continue with files and notes.",
    "no_readme": "No README found. We'll use commits and issues instead.",
    "network_error": "Couldn't reach GitHub. Check your connection and try again.",
    "unexpected": "Something went wrong while reading the repository. You can continue with files and notes.",
}

# In-memory cache for PUBLIC fetches only: keyed by "owner/repo" -> (timestamp, data)
# NEVER cache private fetches made with user tokens.
_PUBLIC_CACHE: Dict[str, Tuple[float, List[Dict[str, Any]]]] = {}
CACHE_TTL_SECONDS = 600  # 10 minutes


@dataclass
class GitHubFetchResult:
    """Typed result from safe_fetch."""
    ok: bool
    data: Optional[List[Dict[str, Any]]] = None
    error_code: Optional[str] = None
    message: str = ""
    warning: bool = False


def clear_public_cache() -> None:
    """Clear in-memory public cache (useful for testing and refresh)."""
    _PUBLIC_CACHE.clear()


def parse_repo_ref(text: Optional[str]) -> Tuple[bool, Optional[Tuple[str, str]], str]:
    """Parse and validate a GitHub repository reference.

    Accepts:
      - "owner/repo"
      - "https://github.com/owner/repo"
      - with or without trailing slash or ".git"
      - with extra path parts such as "/tree/main" or "/issues" (ignored)

    Rejects:
      - empty or whitespace text
      - hosts other than github.com
      - URLs with embedded credentials
      - values with spaces, "..", slashes or shell characters
      - anything exceeding GitHub length limits

    Returns:
      (ok: bool, (owner, repo) or None, error_message: str)
    """
    if text is None:
        return False, None, MESSAGES["invalid_link"]

    raw = text.strip()
    if not raw:
        return False, None, MESSAGES["invalid_link"]

    # Reject whitespace within the URL or reference
    if any(c.isspace() for c in raw):
        return False, None, MESSAGES["invalid_link"]

    # Reject URLs with embedded credentials (e.g. https://user:pass@github.com/...)
    if "@" in raw:
        return False, None, MESSAGES["invalid_link"]

    # Reject path traversal and shell injection characters
    disallowed_chars = [";", "&", "|", "`", "$", "<", ">", "\\"]
    if any(ch in raw for ch in disallowed_chars) or ".." in raw:
        return False, None, MESSAGES["invalid_link"]

    # Normalize protocol and path
    if raw.startswith(("http://", "https://")):
        try:
            parsed = urlparse(raw)
        except Exception:
            return False, None, MESSAGES["invalid_link"]

        # Only allow github.com (and www.github.com)
        host = (parsed.hostname or "").lower()
        if host not in ("github.com", "www.github.com"):
            return False, None, MESSAGES["invalid_link"]

        path = parsed.path
    else:
        # Might be "github.com/owner/repo" or "owner/repo"
        path = raw
        if path.lower().startswith("github.com/"):
            path = path[len("github.com/"):]
        elif path.lower().startswith("github.com:"):
            path = path[len("github.com:"):]

    path = path.strip("/")
    if path.endswith(".git"):
        path = path[:-4]

    segments = [s for s in path.split("/") if s]
    if len(segments) < 2:
        return False, None, MESSAGES["invalid_link"]

    owner, repo = segments[0], segments[1]

    # Validate owner and repo syntax per GitHub specs:
    # Owner: 1-39 chars, alphanumeric, hyphen, underscore, dot (no start/end hyphen)
    # Repo: 1-100 chars, alphanumeric, hyphen, underscore, dot
    owner_pattern = r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,38}$"
    repo_pattern = r"^[a-zA-Z0-9._-]{1,100}$"

    if not re.match(owner_pattern, owner) or not re.match(repo_pattern, repo):
        return False, None, MESSAGES["invalid_link"]

    if repo in (".", "..") or owner in (".", ".."):
        return False, None, MESSAGES["invalid_link"]

    return True, (owner, repo), ""


def get_server_token() -> Optional[str]:
    """Retrieve server-side GitHub token from Streamlit secrets or environment.

    Never displayed, logged or cached across users.
    """
    try:
        import streamlit as st
        token = st.secrets.get("GITHUB_TOKEN")
        if token and str(token).strip():
            return str(token).strip()
    except Exception:
        pass

    env_token = os.environ.get("GITHUB_TOKEN")
    if env_token and env_token.strip():
        return env_token.strip()

    return None


def safe_fetch(
    repo_text: str,
    user_token: Optional[str] = None,
    server_token: Optional[str] = None,
    timeout: int = 10,
    refresh: bool = False,
) -> GitHubFetchResult:
    """Safely fetch repository knowledge without raising exceptions or hanging.

    Wraps github_connector.fetch_repo_knowledge and enforces:
    - URL validation
    - Non-technical friendly messages
    - 10-second timeout per HTTP call
    - Memory caching for public fetches only (no user token)
    - Zero token leakage in error messages or logs
    """
    ok, parsed, err_msg = parse_repo_ref(repo_text)
    if not ok or not parsed:
        return GitHubFetchResult(
            ok=False,
            error_code="invalid_link",
            message=err_msg or MESSAGES["invalid_link"]
        )

    owner, repo = parsed
    cache_key = f"{owner.lower()}/{repo.lower()}"
    canonical_repo = f"{owner}/{repo}"

    # Determine token to use: user token takes priority
    u_token = user_token.strip() if (user_token and user_token.strip()) else None
    s_token = server_token.strip() if (server_token and server_token.strip()) else get_server_token()

    effective_token = u_token or s_token
    has_user_token = bool(u_token)

    # Cache lookup: ONLY for public fetches without a user token
    if not has_user_token and not refresh:
        cached = _PUBLIC_CACHE.get(cache_key)
        if cached:
            cached_time, cached_data = cached
            if time.time() - cached_time < CACHE_TTL_SECONDS:
                return GitHubFetchResult(
                    ok=True,
                    data=cached_data,
                    message=""
                )

    # Perform the fetch via github_connector
    try:
        from utils.github_connector import fetch_repo_knowledge

        # Up to 2 attempts on transient 5xx/network errors, with short delay
        last_exc: Optional[Exception] = None
        data = None

        for attempt in range(2):
            try:
                data = fetch_repo_knowledge(
                    canonical_repo,
                    token=effective_token,
                    timeout=timeout,
                )
                break
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as net_err:
                last_exc = net_err
                time.sleep(0.5)
            except Exception as e:
                last_exc = e
                # Don't retry auth or 404 errors
                err_s = str(e).lower()
                if any(x in err_s for x in ("401", "403", "404", "access denied", "not found")):
                    break
                time.sleep(0.5)

        if data is None and last_exc:
            raise last_exc

        if not data:
            return GitHubFetchResult(
                ok=False,
                error_code="empty_repo",
                message=MESSAGES["empty_repo"]
            )

        # Inspect fetched items to detect empty repo vs no-README
        has_real_content = False
        has_readme = False

        for item in data:
            content = item.get("content", "")
            source = item.get("source", "")
            if "README" in source:
                if content and not content.startswith("[README not available"):
                    has_readme = True
                    has_real_content = True
            elif "commits" in source:
                if content and not content.startswith("[Commits not available"):
                    has_real_content = True
            elif "issues" in source or "pull-requests" in source:
                if content:
                    has_real_content = True

        if not has_real_content:
            return GitHubFetchResult(
                ok=False,
                error_code="empty_repo",
                message=MESSAGES["empty_repo"]
            )

        # Cache ONLY if public (no user token)
        if not has_user_token:
            _PUBLIC_CACHE[cache_key] = (time.time(), data)

        if not has_readme:
            return GitHubFetchResult(
                ok=True,
                data=data,
                warning=True,
                message=MESSAGES["no_readme"]
            )

        return GitHubFetchResult(
            ok=True,
            data=data,
            message=""
        )

    except PermissionError as pe:
        # If user supplied a token, 403 or 401 means bad token
        if has_user_token:
            return GitHubFetchResult(
                ok=False,
                error_code="bad_token",
                message=MESSAGES["bad_token"]
            )
        return GitHubFetchResult(
            ok=False,
            error_code="not_found",
            message=MESSAGES["not_found"]
        )

    except requests.exceptions.HTTPError as he:
        status = getattr(getattr(he, "response", None), "status_code", None)
        if status == 401:
            return GitHubFetchResult(ok=False, error_code="bad_token", message=MESSAGES["bad_token"])
        if status == 404:
            return GitHubFetchResult(ok=False, error_code="not_found", message=MESSAGES["not_found"])
        if status in (403, 429):
            resp = getattr(he, "response", None)
            rem = resp.headers.get("X-RateLimit-Remaining") if resp else None
            if status == 429 or rem == "0":
                return GitHubFetchResult(ok=False, error_code="rate_limit", message=MESSAGES["rate_limit"])
            if has_user_token:
                return GitHubFetchResult(ok=False, error_code="bad_token", message=MESSAGES["bad_token"])
            return GitHubFetchResult(ok=False, error_code="not_found", message=MESSAGES["not_found"])
        if status and status >= 500:
            return GitHubFetchResult(ok=False, error_code="unexpected", message=MESSAGES["unexpected"])

        return GitHubFetchResult(ok=False, error_code="unexpected", message=MESSAGES["unexpected"])

    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
        return GitHubFetchResult(
            ok=False,
            error_code="network_error",
            message=MESSAGES["network_error"]
        )

    except Exception as exc:
        exc_str = str(exc).lower()
        if "401" in exc_str or "bad credentials" in exc_str:
            return GitHubFetchResult(ok=False, error_code="bad_token", message=MESSAGES["bad_token"])
        if "404" in exc_str or "not found" in exc_str:
            return GitHubFetchResult(ok=False, error_code="not_found", message=MESSAGES["not_found"])
        if "rate limit" in exc_str or "429" in exc_str:
            return GitHubFetchResult(ok=False, error_code="rate_limit", message=MESSAGES["rate_limit"])
        if "could not fetch any content" in exc_str or "empty" in exc_str:
            return GitHubFetchResult(ok=False, error_code="empty_repo", message=MESSAGES["empty_repo"])
        if "timeout" in exc_str or "timed out" in exc_str or "connection" in exc_str:
            return GitHubFetchResult(ok=False, error_code="network_error", message=MESSAGES["network_error"])

        return GitHubFetchResult(
            ok=False,
            error_code="unexpected",
            message=MESSAGES["unexpected"]
        )


def build_commit_link(owner: str, repo: str, sha: str) -> Optional[str]:
    """Build a validated GitHub commit link from validated owner/repo and hex SHA."""
    ok, parsed, _ = parse_repo_ref(f"{owner}/{repo}")
    if not ok or not parsed:
        return None
    o, r = parsed
    clean_sha = sha.strip()
    if not re.match(r"^[0-9a-fA-F]{7,40}$", clean_sha):
        return None
    return f"https://github.com/{o}/{r}/commit/{clean_sha}"


def build_pr_link(owner: str, repo: str, pr_number: Any) -> Optional[str]:
    """Build a validated GitHub PR link from validated owner/repo and numeric ID."""
    ok, parsed, _ = parse_repo_ref(f"{owner}/{repo}")
    if not ok or not parsed:
        return None
    o, r = parsed
    clean_num = str(pr_number).strip()
    if not re.match(r"^[1-9][0-9]{0,8}$", clean_num):
        return None
    return f"https://github.com/{o}/{r}/pull/{clean_num}"
