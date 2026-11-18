"""Access control, permission rules, access requests, and notifications for Baton."""

import time
import uuid
import re
from typing import Dict, Any, List, Optional
import streamlit as st
from utils.store import save_project_state, log_audit_entry, modify_project_state
from utils.crypto import REDACTION_PLACEHOLDER

CONFIDENTIAL_DOC_IDS = {
    "DOC-TRB-008",
    "DOC-FIN-009",
    "DOC-BCP-010",
    "DOC-MON-011",
}
CONFIDENTIAL_NOTE_IDS = {
    "NOTE-004",
}
CONFIDENTIAL_SOURCES = CONFIDENTIAL_DOC_IDS | CONFIDENTIAL_NOTE_IDS

# Request types and readable labels
REQUEST_LABELS = {
    "normal_write": "write access to project content",
    "confidential_read": "read access to confidential files",
    "confidential_write": "read and write access to confidential files",
}

ROLE_LABELS = {
    "Manager": "Manager",
    "Employee": "Departing employee",
    "Successor": "New joinee",
}

STUDENT_ROLE_LABELS = {
    "Manager": "Team Leader",
    "Employee": "Departing Team Member",
    "Successor": "New Team Member",
}


def get_role_label(role: str, org_type: str = "company") -> str:
    if org_type == "student_team":
        return STUDENT_ROLE_LABELS.get(role, role)
    return ROLE_LABELS.get(role, role)


def get_manager_id(state: Dict[str, Any]) -> str:
    """Find manager username from members list or fallback to 'manager'."""
    for m in state.get("members", []):
        if m.get("role") == "Manager":
            return m.get("id") or m.get("username", "manager")
    return "manager"


def get_employee_id(state: Dict[str, Any]) -> str:
    """Find employee username from members list or fallback to 'sarah'."""
    for m in state.get("members", []):
        if m.get("role") == "Employee":
            return m.get("id") or m.get("username", "sarah")
    return "sarah"


def get_successor_id(state: Dict[str, Any]) -> str:
    """Find successor username from members list or fallback to 'marcus'."""
    for m in state.get("members", []):
        if m.get("role") == "Successor":
            return m.get("id") or m.get("username", "marcus")
    return "marcus"


def ensure_member(state: Dict[str, Any], user: Dict[str, Any]) -> None:
    """Ensure user is registered in state['members']. If joining first time, notify manager."""
    uid = user.get("username")
    if not uid:
        return

    def _apply(d):
        if "members" not in d or not isinstance(d["members"], list):
            d["members"] = []

        existing = next((m for m in d["members"] if m.get("id") == uid or m.get("username") == uid), None)
        if not existing:
            member_record = {
                "id": uid,
                "username": uid,
                "name": user.get("name", uid),
                "role": user.get("role", "Successor"),
                "joined_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            d["members"].append(member_record)

            # Notify manager if joining member is not the manager
            if user.get("role") != "Manager":
                mgr_id = get_manager_id(d)
                role_label = get_role_label(user.get("role", "Successor"))
                d.setdefault("notifications", []).append({
                    "id": str(uuid.uuid4())[:8],
                    "to": mgr_id,
                    "kind": "member_joined",
                    "message": f"{user.get('name', uid)} joined the project as {role_label}.",
                    "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "read": False,
                })

    modify_project_state(_apply, session_state=state)


def get_member_grants(state: Dict[str, Any], member_id: str) -> List[str]:
    grants_dict = state.get("grants", {})
    return list(grants_dict.get(member_id, []))


def can_read(member: Dict[str, Any], is_confidential: bool = False, state: Optional[Dict[str, Any]] = None, file_id: Optional[str] = None) -> bool:
    """Check read permission."""
    role = member.get("role")
    if role == "Manager":
        return True
    if not is_confidential:
        return True
    if state is None and hasattr(st, "session_state"):
        state = st.session_state
    if state is None:
        return False
    uid = member.get("id") or member.get("username", "")
    grants = get_member_grants(state, uid)
    if "confidential_read" in grants or "confidential_write" in grants:
        return True
    if file_id and (file_id in grants or f"confidential_read:{file_id}" in grants):
        return True
    return False


def can_write(member: Dict[str, Any], is_confidential: bool = False, state: Optional[Dict[str, Any]] = None) -> bool:
    """Check write permission."""
    role = member.get("role")
    if role == "Manager":
        return True
    if state is None and hasattr(st, "session_state"):
        state = st.session_state
    uid = member.get("id") or member.get("username", "")
    grants = get_member_grants(state, uid) if state else []

    if not is_confidential:
        if role == "Employee":
            return True
        return "normal_write" in grants
    else:
        return "confidential_write" in grants


def can_read_file(member: Optional[Dict[str, Any]], file_id: str, file_sensitivity: str = "normal", state: Optional[Dict[str, Any]] = None) -> bool:
    """Check if member can read a specific file.
    
    Rules:
    - None user -> False (fail-closed).
    - Manager and Sarah (Employee) -> True.
    - Non-confidential file -> True.
    - Confidential file -> True only if member has broad grant or per-file grant for file_id.
    """
    if not member:
        return False
    role = member.get("role")
    uid = member.get("id") or member.get("username", "")
    if role in ("Manager", "Employee") or uid in ("manager", "sarah"):
        return True

    is_conf = (file_sensitivity == "confidential" or file_id in CONFIDENTIAL_SOURCES)
    if not is_conf:
        return True

    if state is None and hasattr(st, "session_state"):
        state = st.session_state

    if state is not None:
        grants = get_member_grants(state, uid)
        if "confidential_read" in grants or "confidential_write" in grants:
            return True
        if file_id in grants or f"confidential_read:{file_id}" in grants:
            return True

    return False


def redact_secrets(s: str) -> str:
    """Redact keys, tokens, and passwords from text."""
    if not s:
        return ""
    # 1. api_key=..., password: ..., token: ...
    s = re.sub(r'(?i)\b(api[_-]?key)\s*[:=]\s*([\'"][^\'"\r\n]+[\'"]|[^\s,;]+)', r'\1=' + REDACTION_PLACEHOLDER, s)
    s = re.sub(r'(?i)\b(password|token)\s*[:=]\s*([\'"][^\'"\r\n]+[\'"]|[^\s,;]+)', r'\1: ' + REDACTION_PLACEHOLDER, s)
    # 2. Known key prefixes
    s = re.sub(r'\b(AIza[0-9A-Za-z-_]{20,}|ghp_[0-9A-Za-z]{20,}|sk-[0-9A-Za-z-_]{20,}|AQ\.[0-9A-Za-z-_]{10,})\b', REDACTION_PLACEHOLDER, s)
    # 3. Long tokens (40+ characters alphanumeric/symbols without whitespace)
    s = re.sub(r'(?<![A-Za-z0-9+/=_-])[A-Za-z0-9+/=_-]{40,}(?![A-Za-z0-9+/=_-])', REDACTION_PLACEHOLDER, s)
    return s


def redact_confidential_fields(s: str) -> str:
    """Redact emails, phone numbers, and currency amounts in Harborline style."""
    if not s:
        return ""
    # Emails
    s = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b', REDACTION_PLACEHOLDER, s)
    # Phone numbers
    phone_pattern = r'(\+\d{1,3}[-.\s]?(?:\(?\d{2,5}\)?[-.\s]?)?\d{3,5}[-.\s]?\d{3,5}\b|\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b|\b\d{5}[-.\s]\d{5}\b)'
    s = re.sub(phone_pattern, REDACTION_PLACEHOLDER, s)
    # Currency / amounts in Harborline style (e.g. INR 500,000, 500000.01, $50,000)
    money_pattern = r'(?:INR\s*|Rs\.?\s*|\$)\s*[\d,]+(?:\.\d{1,2})?|\b[\d,]+\.\d{2}\s*(?:INR|USD)?\b'
    s = re.sub(money_pattern, REDACTION_PLACEHOLDER, s)
    return s


def redact(
    text: str,
    user_role: Optional[str] = None,
    user: Optional[Dict[str, Any]] = None,
    grants: Optional[Any] = None,
    file_sensitivity: str = "normal",
    file_id: Optional[str] = None,
) -> str:
    """Redact text based on role, sensitivity, and grants.
    
    Rules:
    - Manager and Sarah: full text, as before.
    - Marcus / Successor WITHOUT an approved grant for that specific file:
      the confidential document body, confidential claim quotes and confidential excerpts
      are replaced by REDACTION_PLACEHOLDER.
    - Marcus / Successor WITH an approved grant for that specific file:
      full text for that file ONLY (secrets still redacted).
    - Field-level patterns for secrets (keys, tokens, passwords) apply to ALL text
      returned to the successor, even normal text.
    - All other field patterns (email, phone, amounts) apply ONLY to confidential-labelled text.
    - If no user is passed, default to MOST RESTRICTED behavior (successor view without grant).
    """
    if text is None:
        return ""
    if not isinstance(text, str):
        text = str(text)

    # Resolve role and user id
    role = user_role
    uid = None
    if user is not None:
        if not role:
            role = user.get("role")
        uid = user.get("id") or user.get("username")

    if not role:
        role = "Successor"  # Default to most restricted

    # Manager and Sarah get full text
    if role in ("Manager", "Employee") or uid in ("manager", "sarah"):
        return text

    # Successor / Joinee logic:
    is_conf = (
        file_sensitivity == "confidential"
        or (file_id and file_id in CONFIDENTIAL_SOURCES)
    )

    # Check grant for this file
    has_grant = False
    if uid:
        user_grants = []
        if isinstance(grants, list):
            user_grants = grants
        elif isinstance(grants, dict):
            user_grants = grants.get(uid, [])
        elif hasattr(st, "session_state") and hasattr(st.session_state, "get"):
            user_grants = st.session_state.get("grants", {}).get(uid, [])

        if user_grants:
            if "confidential_read" in user_grants or "confidential_write" in user_grants:
                has_grant = True
            elif file_id and (file_id in user_grants or f"confidential_read:{file_id}" in user_grants):
                has_grant = True
        else:
            try:
                from utils.store import can_user_read_file
                has_grant = can_user_read_file(user, file_id)
            except Exception:
                has_grant = False

    if is_conf:
        if not has_grant:
            return REDACTION_PLACEHOLDER
        # Has grant for this file: full text for this file, but secret patterns still apply
        return redact_secrets(text)
    else:
        # Normal text: field-level patterns for secrets apply to ALL text returned to successor
        return redact_secrets(text)



def get_effective_access(member: Dict[str, Any], state: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
    """Return effective access summary for a member."""
    role = member.get("role")
    if role == "Manager":
        return {
            "name": member.get("name", ""),
            "role": "Manager",
            "project_content": "Full (manager)",
            "confidential_files": "Full (manager)",
        }

    w_normal = can_write(member, is_confidential=False, state=state)
    r_conf = can_read(member, is_confidential=True, state=state)
    w_conf = can_write(member, is_confidential=True, state=state)

    proj_text = "Read and write" if w_normal else "Read only"
    if w_conf:
        conf_text = "Read and write"
    elif r_conf:
        conf_text = "Read only"
    else:
        conf_text = "None"

    return {
        "name": member.get("name", ""),
        "role": get_role_label(role),
        "project_content": proj_text,
        "confidential_files": conf_text,
    }


def get_allowed_pages(state: Dict[str, Any], member: Dict[str, Any]) -> List[str]:
    """Compute allowed page ids based on role and active grants."""
    role = member.get("role")
    pages = []

    if role == "Manager":
        pages = ["review", "handover", "audit", "access_management", "notifications", "confidential"]
    elif role == "Employee":
        pages = ["connect", "reconstruct", "employee", "employee_notes", "my_access", "notifications"]
        if can_read(member, is_confidential=True, state=state):
            pages.append("confidential")
    else:  # Successor / Joinee
        pages = []
        if can_write(member, is_confidential=False, state=state):
            pages.extend(["connect", "employee", "employee_notes"])
        pages.extend(["successor_handover", "successor_notes", "my_access", "notifications"])
        if can_read(member, is_confidential=True, state=state):
            pages.append("confidential")

    return pages


def require_page_access(page_id: str) -> None:
    """Enforce access on a page controller. Stop if denied."""
    current_user = {
        "id": st.session_state.get("auth_username", ""),
        "username": st.session_state.get("auth_username", ""),
        "name": st.session_state.get("auth_name", ""),
        "role": st.session_state.get("auth_role", ""),
    }
    allowed = get_allowed_pages(st.session_state, current_user)
    if page_id not in allowed:
        log_audit_entry(
            st.session_state,
            current_user["id"] or "unknown",
            "access denied",
            reason=f"Attempted to access {page_id}"
        )
        st.error("Access denied for your role")
        st.stop()


def add_notification(state: Dict[str, Any], to_id: str, kind: str, message: str) -> Dict[str, Any]:
    """Append a notification to state['notifications'] using atomic read-modify-write."""
    notif = {
        "id": str(uuid.uuid4())[:8],
        "to": to_id,
        "kind": kind,
        "message": message,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "read": False,
    }

    def _apply(d):
        d.setdefault("notifications", []).append(notif)

    modify_project_state(_apply, session_state=state)
    return notif


def create_request(state: Dict[str, Any], member: Dict[str, Any], req_type: str, reason: str, file_id: Optional[str] = None) -> Dict[str, Any]:
    """Member creates an access request using atomic read-modify-write."""
    req = {
        "id": str(uuid.uuid4())[:8],
        "requester_id": member.get("id") or member.get("username"),
        "requester_name": member.get("name"),
        "requester_role": member.get("role"),
        "type": req_type,
        "reason": reason.strip(),
        "status": "pending",
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "decided_at": None,
        "decided_by": None,
        "decision_comment": "",
        "file_id": file_id,
    }
    readable_type = REQUEST_LABELS.get(req_type, req_type)
    reason_text = reason.strip() if reason.strip() else "none given"
    notif_msg = f"{member.get('name')} requested {readable_type}. Reason: {reason_text}."

    def _apply(d):
        d.setdefault("access_requests", []).append(req)
        # Notify Manager
        mgr_id = get_manager_id(d)
        d.setdefault("notifications", []).append({
            "id": str(uuid.uuid4())[:8],
            "to": mgr_id,
            "kind": "access_request",
            "message": notif_msg,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "read": False,
        })
        # Audit log
        d.setdefault("action_history", []).append({
            "who": member.get("id") or member.get("username"),
            "action": "requested access",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "reason": f"{readable_type} (Reason: {reason_text})",
        })

    modify_project_state(_apply, session_state=state)
    return req


def decide_request(state: Dict[str, Any], manager: Dict[str, Any], request_id: str, approve: bool, comment: str) -> None:
    """Manager approves or denies an access request using atomic read-modify-write."""
    if manager.get("role") != "Manager":
        raise PermissionError("Only the Manager can decide access requests.")

    def _apply(d):
        req = next((r for r in d.get("access_requests", []) if r.get("id") == request_id), None)
        if not req:
            raise ValueError(f"Request {request_id} not found.")

        req["status"] = "approved" if approve else "denied"
        req["decided_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        req["decided_by"] = manager.get("id") or manager.get("username")
        req["decision_comment"] = comment.strip()

        requester_id = req["requester_id"]
        req_type = req["type"]
        file_id = req.get("file_id")
        readable_type = REQUEST_LABELS.get(req_type, req_type)
        if file_id:
            readable_type += f" for file {file_id}"

        if approve:
            if "grants" not in d:
                d["grants"] = {}
            cur_grants = set(d["grants"].get(requester_id, []))
            if file_id:
                cur_grants.add(f"confidential_read:{file_id}")
                cur_grants.add(file_id)
            else:
                cur_grants.add(req_type)
                if req_type == "confidential_write":
                    cur_grants.add("confidential_read")
            d["grants"][requester_id] = list(cur_grants)

            notif_msg = f"Your request for {readable_type} was approved by the manager."
            action_msg = f"approved request for {readable_type}"
        else:
            if "grants" in d and requester_id in d["grants"]:
                cur_grants = set(d["grants"][requester_id])
                cur_grants.discard(req_type)
                if file_id:
                    cur_grants.discard(f"confidential_read:{file_id}")
                    cur_grants.discard(file_id)
                d["grants"][requester_id] = list(cur_grants)
            comment_text = comment.strip() if comment.strip() else "none"
            notif_msg = f"Your request for {readable_type} was denied. Comment: {comment_text}."
            action_msg = f"denied request for {readable_type}"

        d.setdefault("notifications", []).append({
            "id": str(uuid.uuid4())[:8],
            "to": requester_id,
            "kind": "request_approved" if approve else "request_denied",
            "message": notif_msg,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "read": False,
        })
        d.setdefault("action_history", []).append({
            "who": manager.get("id") or manager.get("username"),
            "action": action_msg,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "reason": f"Target: {requester_id}, Comment: {comment.strip()}",
        })

    modify_project_state(_apply, session_state=state)


def set_grants(state: Dict[str, Any], manager: Dict[str, Any], member_id: str, new_grants: List[str]) -> None:
    """Manager explicitly sets grants for a member and notifies only what changed using atomic read-modify-write."""
    if manager.get("role") != "Manager":
        raise PermissionError("Only the Manager can set grants.")

    def _apply(d):
        if "grants" not in d:
            d["grants"] = {}

        clean_new = set(new_grants)
        if "confidential_write" in clean_new:
            clean_new.add("confidential_read")

        old_grants = set(d["grants"].get(member_id, []))
        d["grants"][member_id] = list(clean_new)

        added = clean_new - old_grants
        removed = old_grants - clean_new

        for grant_type in added:
            readable = REQUEST_LABELS.get(grant_type, grant_type)
            d.setdefault("notifications", []).append({
                "id": str(uuid.uuid4())[:8],
                "to": member_id,
                "kind": "grant_added",
                "message": f"The manager gave you {readable}.",
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "read": False,
            })
            d.setdefault("action_history", []).append({
                "who": manager.get("id") or manager.get("username"),
                "action": "granted permission",
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "reason": f"Target: {member_id}, Granted: {readable}",
            })

        for grant_type in removed:
            readable = REQUEST_LABELS.get(grant_type, grant_type)
            d.setdefault("notifications", []).append({
                "id": str(uuid.uuid4())[:8],
                "to": member_id,
                "kind": "grant_removed",
                "message": f"The manager removed your {readable}.",
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "read": False,
            })
            d.setdefault("action_history", []).append({
                "who": manager.get("id") or manager.get("username"),
                "action": "revoked permission",
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "reason": f"Target: {member_id}, Revoked: {readable}",
            })

    modify_project_state(_apply, session_state=state)


def record_write(state: Dict[str, Any], section_id: str) -> None:
    """Used by normal-content write handlers: if section was approved, set back to pending and notify manager."""
    def _apply(d):
        approvals = d.get("approvals", {})
        if approvals.get(section_id) is True:
            approvals[section_id] = False
            who = state.get("auth_username", "user") if hasattr(state, "get") else "user"
            d.setdefault("action_history", []).append({
                "who": who,
                "action": "changed after approval",
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "reason": f"Section {section_id}",
            })
            mgr_id = get_manager_id(d)
            d.setdefault("notifications", []).append({
                "id": str(uuid.uuid4())[:8],
                "to": mgr_id,
                "kind": "re_review",
                "message": "A section changed after approval and needs review again.",
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "read": False,
            })

    modify_project_state(_apply, session_state=state)
