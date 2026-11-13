"""Access control, permission rules, access requests, and notifications for Baton."""

import time
import uuid
from typing import Dict, Any, List, Optional
import streamlit as st
from utils.store import save_project_state, log_audit_entry, modify_project_state

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


def get_role_label(role: str) -> str:
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


def can_read(member: Dict[str, Any], is_confidential: bool = False, state: Optional[Dict[str, Any]] = None) -> bool:
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
    return "confidential_read" in grants or "confidential_write" in grants


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


def create_request(state: Dict[str, Any], member: Dict[str, Any], req_type: str, reason: str) -> Dict[str, Any]:
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
        readable_type = REQUEST_LABELS.get(req_type, req_type)

        if approve:
            if "grants" not in d:
                d["grants"] = {}
            cur_grants = set(d["grants"].get(requester_id, []))
            cur_grants.add(req_type)
            if req_type == "confidential_write":
                cur_grants.add("confidential_read")
            d["grants"][requester_id] = list(cur_grants)

            notif_msg = f"Your request for {readable_type} was approved by the manager."
            action_msg = f"approved request for {readable_type}"
        else:
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
