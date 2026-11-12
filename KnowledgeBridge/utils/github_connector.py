"""
GitHub connector for Baton (Knowledge Handover Platform).
Fetches README, commits, issues, and PRs from a public or private GitHub repo.
Works without a token for public repos.
"""

import re
import requests


def parse_repo_url(repo_url: str) -> tuple[str, str]:
    """Extract owner and repo name from a GitHub URL."""
    repo_url = repo_url.strip().rstrip("/")
    # Support formats:
    # https://github.com/owner/repo
    # https://github.com/owner/repo.git
    # github.com/owner/repo
    # owner/repo
    patterns = [
        r"github\.com[/:]([^/]+)/([^/\.]+?)(?:\.git)?$",
        r"^([^/]+)/([^/]+)$",
    ]
    for pattern in patterns:
        match = re.search(pattern, repo_url)
        if match:
            return match.group(1), match.group(2)
    raise ValueError(f"Could not parse GitHub URL: {repo_url}")


def fetch_repo_knowledge(repo_url: str, token: str = None) -> list[dict]:
    """
    Fetch knowledge from a GitHub repository.
    
    Args:
        repo_url: GitHub repository URL
        token: Optional personal access token (for private repos)
    
    Returns:
        List of dicts with keys: content, source, source_type
    """
    owner, repo = parse_repo_url(repo_url)
    
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "Baton/1.0"
    }
    if token:
        headers["Authorization"] = f"token {token}"

    base_url = f"https://api.github.com/repos/{owner}/{repo}"
    results = []

    def safe_get(url, params=None):
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=15)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.HTTPError as e:
            if resp.status_code == 403:
                raise PermissionError(f"Access denied to {url}. For private repos, provide a GitHub token.")
            elif resp.status_code == 404:
                return None
            raise RuntimeError(f"GitHub API error for {url}: {e}")
        except Exception as e:
            raise RuntimeError(f"Failed to fetch {url}: {e}")

    # 1. Fetch README
    try:
        readme_data = safe_get(f"{base_url}/readme")
        if readme_data and "download_url" in readme_data:
            readme_resp = requests.get(readme_data["download_url"], timeout=15)
            readme_content = readme_resp.text
            results.append({
                "content": f"# README\n\n{readme_content}",
                "source": f"{owner}/{repo}/README",
                "source_type": "github"
            })
    except Exception as e:
        results.append({
            "content": f"[README not available: {e}]",
            "source": f"{owner}/{repo}/README",
            "source_type": "github"
        })

    # 2. Fetch recent commits (last 50)
    try:
        commits = safe_get(f"{base_url}/commits", params={"per_page": 50})
        if commits:
            commit_lines = []
            for c in commits:
                msg = c.get("commit", {}).get("message", "").split("\n")[0]
                author = c.get("commit", {}).get("author", {}).get("name", "unknown")
                date = c.get("commit", {}).get("author", {}).get("date", "")[:10]
                sha = c.get("sha", "")[:7]
                commit_lines.append(f"- [{sha}] {date} {author}: {msg}")
            results.append({
                "content": "# Recent Commits (last 50)\n\n" + "\n".join(commit_lines),
                "source": f"{owner}/{repo}/commits",
                "source_type": "github"
            })
    except Exception as e:
        results.append({
            "content": f"[Commits not available: {e}]",
            "source": f"{owner}/{repo}/commits",
            "source_type": "github"
        })

    # 3. Fetch open issues (last 20)
    try:
        open_issues = safe_get(f"{base_url}/issues", params={"state": "open", "per_page": 20})
        if open_issues:
            issue_lines = []
            for issue in open_issues:
                if "pull_request" in issue:
                    continue  # Skip PRs from issues endpoint
                num = issue.get("number")
                title = issue.get("title", "")
                body = (issue.get("body") or "")[:300]
                labels = ", ".join(l["name"] for l in issue.get("labels", []))
                issue_lines.append(f"### Issue #{num}: {title}\nLabels: {labels}\n{body}\n")
            if issue_lines:
                results.append({
                    "content": "# Open Issues\n\n" + "\n".join(issue_lines),
                    "source": f"{owner}/{repo}/open-issues",
                    "source_type": "github"
                })
    except Exception as e:
        pass  # Issues are optional

    # 4. Fetch closed issues (last 20)
    try:
        closed_issues = safe_get(f"{base_url}/issues", params={"state": "closed", "per_page": 20})
        if closed_issues:
            issue_lines = []
            for issue in closed_issues:
                if "pull_request" in issue:
                    continue
                num = issue.get("number")
                title = issue.get("title", "")
                body = (issue.get("body") or "")[:200]
                issue_lines.append(f"### Issue #{num}: {title}\n{body}\n")
            if issue_lines:
                results.append({
                    "content": "# Closed Issues\n\n" + "\n".join(issue_lines),
                    "source": f"{owner}/{repo}/closed-issues",
                    "source_type": "github"
                })
    except Exception as e:
        pass

    # 5. Fetch recent PRs (last 20)
    try:
        prs = safe_get(f"{base_url}/pulls", params={"state": "all", "per_page": 20, "sort": "updated"})
        if prs:
            pr_lines = []
            for pr in prs:
                num = pr.get("number")
                title = pr.get("title", "")
                body = (pr.get("body") or "")[:300]
                state = pr.get("state", "")
                pr_lines.append(f"### PR #{num} [{state.upper()}]: {title}\n{body}\n")
            if pr_lines:
                results.append({
                    "content": "# Pull Requests\n\n" + "\n".join(pr_lines),
                    "source": f"{owner}/{repo}/pull-requests",
                    "source_type": "github"
                })
    except Exception as e:
        pass

    if not results:
        raise RuntimeError(f"Could not fetch any content from {repo_url}. Check the URL and try again.")

    return results
