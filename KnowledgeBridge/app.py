"""
Baton — Knowledge Handover Platform
Enterprise Presentation Layer Refactor
"""

import copy
import csv
import io
import json
import os
import re
import textwrap
import time
from pathlib import Path
import streamlit as st
from PIL import Image as _PILImage

from utils.auth import authenticate, logout, is_locked, get_lockout_remaining
from utils.store import (
    load_into_session,
    save_project_state,
    log_audit_entry,
    load_project_state,
    get_empty_state,
    modify_project_state,
    mark_notifications_read,
    register_confidential_meta,
)
from utils.file_processor import get_preview
from utils.access import (
    REQUEST_LABELS,
    ROLE_LABELS,
    get_role_label,
    get_manager_id,
    get_employee_id,
    get_successor_id,
    ensure_member,
    get_member_grants,
    can_read,
    can_write,
    get_effective_access,
    get_allowed_pages,
    require_page_access,
    add_notification,
    create_request,
    decide_request,
    set_grants,
    record_write,
)

# ─── Page config (must be first Streamlit call) ───────────────────────────────
_app_icon = _PILImage.open(Path(__file__).resolve().parent / "assets" / "icon.png")
st.set_page_config(
    page_title="Baton — Knowledge Handover Platform",
    page_icon=_app_icon,
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── PALETTE & THEME ──────────────────────────────────────────────────────────
THEMES = {
    "light": {
        "bg": "#F3F4F6",
        "sidebar": "#FFFFFF",
        "card": "#FFFFFF",
        "surface": "#FFFFFF",
        "subtle": "#F9FAFB",
        "input_bg": "#FFFFFF",
        "input_border": "#6B7280",
        "border": "#AEB6C2",
        "text": "#000000",
        "text2": "#000000",
        "placeholder": "#4B5563",
        "disabled": "#1F2937",
        "primary": "#5B21B6",
        "primary_hover": "#4C1D95",
        "on_primary": "#FFFFFF",
        "secondary_bg": "#FFFFFF",
        "secondary_border": "#6B7280",
        "secondary_text": "#000000",
        "sidebar_active_bg": "#E9DDFB",
        "sidebar_active_border": "#5B21B6",
        "sidebar_active_text": "#000000",
        "sidebar_hover_bg": "#F0E8FD",
        "sidebar_hover_text": "#000000",
        "toggle_bg": "#FFFFFF",
        "toggle_border": "#6B7280",
        "toggle_text": "#000000",
        "draft_bg": "#E29A2B",
        "draft_text": "#FFFFFF",
        "ready_bg": "#5B21B6",
        "ready_text": "#FFFFFF",
        "success": "#2E7D32",
        "danger": "#9B1C1C",
    },
    "dark": {
        "bg": "#0F1420",
        "sidebar": "#0B0F19",
        "card": "#171E2E",
        "surface": "#171E2E",
        "subtle": "#171E2E",
        "input_bg": "#171E2E",
        "input_border": "#5A6A85",
        "border": "#5A6A85",
        "text": "#F8FAFC",
        "text2": "#CBD5E1",
        "placeholder": "#64748B",
        "disabled": "#64748B",
        "primary": "#7C3AED",
        "primary_hover": "#6D28D9",
        "on_primary": "#FFFFFF",
        "secondary_bg": "#171E2E",
        "secondary_border": "#5A6A85",
        "secondary_text": "#F8FAFC",
        "sidebar_active_bg": "#3B2A73",
        "sidebar_active_border": "#7C3AED",
        "sidebar_active_text": "#F8FAFC",
        "sidebar_hover_bg": "#241E47",
        "sidebar_hover_text": "#F8FAFC",
        "toggle_bg": "#171E2E",
        "toggle_border": "#5A6A85",
        "toggle_text": "#F8FAFC",
        "draft_bg": "#F5DEB3",
        "draft_text": "#7A4B00",
        "ready_bg": "#3B2A73",
        "ready_text": "#F8FAFC",
        "success": "#6FBF73",
        "danger": "#E57373",
    },
}

THEME_ICONS = {
    "light": ":material/light_mode:",
    "dark": ":material/dark_mode:",
}


def get_theme_mode() -> str:
    if "theme_mode" in st.session_state and st.session_state.theme_mode in ("light", "dark"):
        return st.session_state.theme_mode
    mode = "light"
    if hasattr(st, "context") and hasattr(st.context, "theme"):
        ctx_theme = getattr(st.context.theme, "type", None)
        if ctx_theme and str(ctx_theme).lower() in ("light", "dark"):
            mode = str(ctx_theme).lower()
    st.session_state.theme_mode = mode
    return mode


_theme_mode = get_theme_mode()

# ─── SESSION STATE INIT (Early Initialization for Theme & Auth) ───────────────
def init_session_state():
    defaults = {
        "authenticated": False,
        "auth_username": "",
        "auth_role": "",
        "auth_name": "",
        "page": "connect",
        "api_key": "",
        "employee_name": "",
        "project_role": "",
        "uploaded_files": None,
        "github_url": "",
        "github_token": "",
        "pasted_text": "",
        "knowledge_profile": None,
        "approvals": {},
        "corrections": {},
        "manager_handover": None,
        "newhire_handover": None,
        "employee_handover": None,
        "employee_verifications": {},
        "employee_gap_answers": {},
        "employee_tribal_knowledge": [],
        "all_sources": [],
        "analyses_run": 0,
        "handovers_run": 0,
        "action_history": [],
        "acknowledgement": None,
        "state_notice": None,
        "input_truncated": False,
        "_last_logged_page": "",
        "notifications": [],
        "access_requests": [],
        "members": [],
        "grants": {},
        "confidential_files": [],
        "toasted_ids": set(),
        "theme_mode": _theme_mode,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val

init_session_state()
load_into_session(st.session_state)

# ── Resolve Gemini API key from st.secrets / environment (never displayed) ───
if not st.session_state.api_key:
    _resolved_key = ""
    try:
        _resolved_key = st.secrets["GEMINI_API_KEY"]
    except Exception:
        pass
    if not _resolved_key:
        _resolved_key = os.environ.get("GEMINI_API_KEY", "")
    if _resolved_key:
        st.session_state.api_key = _resolved_key


def _safe_err(e: Exception) -> str:
    """Return str(e) with the API key replaced by '[hidden]'."""
    msg = str(e)
    key = st.session_state.get("api_key", "")
    if key:
        msg = msg.replace(key, "[hidden]")
    return msg


def render_file_preview(file_name: str, data: bytes, key_prefix: str,
                        can_download: bool = True) -> None:
    """
    Render a file preview using get_preview() from utils/file_processor.
    Plain Streamlit components only. No raw bytes ever shown as text.
    If the stored bytes look wrong (empty or PDF bytes stored as decoded text),
    show a warning instead of garbage.
    """
    # Guard: empty or corrupt stored data
    if not data:
        st.warning("This file was stored incorrectly. Please upload it again.")
        return

    # Detect PDF bytes stored as a decoded string (old bug): if the data
    # starts with b'%PDF' it is real bytes; if it starts with the text literal
    # '%PDF' encoded as UTF-8 it was double-decoded.  Either way get_preview
    # handles it, but we surface the warning for files that were saved as plain
    # decoded text before this fix (they will have no pdfplumber-readable pages).
    result = get_preview(file_name, data)

    kind = result["kind"]
    text = result.get("text", "")
    pages = result.get("pages")
    truncated = result.get("truncated", False)
    note = result.get("note", "")

    if kind in ("text", "pdf_text"):
        if pages:
            st.caption(f"{pages} page(s)")
        st.text_area(
            label="File content",
            value=text,
            height=300,
            disabled=True,
            label_visibility="collapsed",
            key=f"{key_prefix}_preview",
        )
        if truncated:
            st.caption("Preview cut at 20,000 characters. Download the file for the full content.")
    elif kind in ("pdf_no_text", "unsupported"):
        # Check if data looks like it was stored as decoded text (old bug)
        try:
            decoded_check = data[:8].decode("ascii", errors="replace")
        except Exception:
            decoded_check = ""
        if decoded_check.startswith("%PDF") or b"%PDF" in data[:16]:
            # real PDF bytes but no text layer, or extraction failed
            st.info(note if note else "This PDF could not be read.")
        elif b"%PDF" not in data[:16] and file_name.lower().endswith(".pdf"):
            # bytes don't look like a PDF — probably stored as decoded text
            st.warning("This file was stored incorrectly. Please upload it again.")
        else:
            st.info(note if note else "Preview is not available for this file type. Use Download.")

    if can_download:
        st.download_button(
            "Download original file",
            data=data,
            file_name=file_name,
            key=f"{key_prefix}_dl",
        )


def redact_sensitive_info(text: str) -> str:
    """Redact sensitive credentials, emails, and phone numbers without modifying normal prose."""
    if not text:
        return ""

    # 1. Redact Emails
    text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b', '[REDACTED]', text)

    # 2. Redact Phone numbers
    phone_pattern = r'(\+\d{1,3}[-.\s]?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}\b|\(\d{3}\)\s*[-.]?\s*\d{3}[-.]\d{4}\b|\b\d{3}-\d{3}-\d{4}\b)'
    text = re.sub(phone_pattern, '[REDACTED]', text)

    # 3. Redact specific API keys starting with AIza, ghp_, sk-, or AQ.
    text = re.sub(r'\b(AIza[0-9A-Za-z-_]{20,}|ghp_[0-9A-Za-z]{20,}|sk-[0-9A-Za-z-_]{20,}|AQ\.[0-9A-Za-z-_]{10,})\b', '[REDACTED]', text)

    # 4. Redact tokens, passwords, secrets, api_keys ONLY when followed by : or = and a value
    text = re.sub(r'(?i)\b(api[_-]?key|password|token|secret)\s*[:=]\s*([\'"][^\'"\r\n]+[\'"]|[^\s,;]+)', r'\1: [REDACTED]', text)

    return text


# ─── THEME STYLING & TOGGLE ───────────────────────────────────────────────────
def inject_theme_css(mode: str) -> None:
    t = THEMES[mode]
    css = textwrap.dedent(f"""<style>
:root {{
--bg: {t['bg']};
--sidebar: {t['sidebar']};
--card: {t['card']};
--surface: {t['surface']};
--subtle: {t['subtle']};
--input-bg: {t['input_bg']};
--input-border: {t['input_border']};
--border: {t['border']};
--divider: {t['border']};
--text: {t['text']};
--text2: {t['text2']};
--text-2: {t['text2']};
--muted: {t['text2']};
--placeholder: {t['placeholder']};
--disabled: {t['disabled']};
--primary: {t['primary']};
--primary-hover: {t['primary_hover']};
--on-primary: {t['on_primary']};
--secondary-bg: {t['secondary_bg']};
--secondary-border: {t['secondary_border']};
--secondary-text: {t['secondary_text']};
--sidebar-active-bg: {t['sidebar_active_bg']};
--sidebar-active-border: {t['sidebar_active_border']};
--sidebar-active-text: {t['sidebar_active_text']};
--sidebar-hover-bg: {t['sidebar_hover_bg']};
--sidebar-hover-text: {t['sidebar_hover_text']};
--toggle-bg: {t['toggle_bg']};
--toggle-border: {t['toggle_border']};
--toggle-text: {t['toggle_text']};
--draft-bg: {t['draft_bg']};
--draft-text: {t['draft_text']};
--ready-bg: {t['ready_bg']};
--ready-text: {t['ready_text']};
--success: {t['success']};
--danger: {t['danger']};
--accent: {t['primary']};
--accent-hover: {t['primary_hover']};
--on-accent: {t['on_primary']};
--nav-active: {t['sidebar_active_bg']};
--nav-hover-text: {t['sidebar_hover_text']};
--link: {t['primary']};
}}
[data-testid="stToolbar"], [data-testid="stDeployButton"], .stDeployButton, [data-testid="stDecoration"], [data-testid="stStatusWidget"] {{ display: none !important; }}
header[data-testid="stHeader"], header[data-testid="stAppHeader"] {{ background: transparent !important; height: 0 !important; min-height: 0 !important; pointer-events: none !important; }}
[data-testid="stSidebarCollapseButton"] {{ pointer-events: auto !important; }}
.main .block-container {{ max-width: 1100px; padding-top: 4.5rem !important; padding-left: 24px; padding-right: 24px; padding-bottom: 48px; margin: 0 auto; }}
html, body, [data-testid="stAppViewContainer"], .main, .stApp {{ font-family: 'Inter', BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: var(--bg) !important; color: var(--text) !important; }}
body, p, span, div, li {{ font-size: 15px; color: var(--text); }}
h1, h2, h3, h4, h5, h6 {{ color: var(--text) !important; font-weight: 600; text-align: left; }}
h1 {{ font-size: 28px; }}
h2 {{ font-size: 20px; }}
h3 {{ font-size: 16px; }}
label, [data-testid="stWidgetLabel"] p, [data-testid="stWidgetLabel"] span {{ font-size: 14px !important; font-weight: 500; color: var(--text) !important; }}
small, .stCaption, caption, [data-testid="stCaptionContainer"] p {{ font-size: 13px !important; color: var(--text) !important; }}
input, textarea, select, [data-baseweb="input"], [data-baseweb="textarea"], [data-baseweb="select"] > div {{ background-color: var(--input-bg) !important; border: 1px solid var(--input-border) !important; color: var(--text) !important; border-radius: 6px; }}
input:focus, textarea:focus, [data-baseweb="input"]:focus-within, [data-baseweb="textarea"]:focus-within, [data-baseweb="select"]:focus-within {{ border-color: var(--primary) !important; }}
::placeholder, input::placeholder, textarea::placeholder {{ color: var(--placeholder) !important; opacity: 1 !important; }}
:disabled, [disabled], button:disabled, input:disabled, textarea:disabled, [aria-disabled="true"] {{ color: var(--disabled) !important; opacity: 1 !important; }}
button:disabled p, button:disabled span {{ color: var(--disabled) !important; }}
.stButton > button[kind="primary"], .stButton > button[data-testid="stBaseButton-primary"], button[data-testid="stFormSubmitButton"] > button {{ background-color: var(--primary) !important; border: 1px solid var(--primary) !important; color: var(--on-primary) !important; border-radius: 8px; }}
.stButton > button[kind="primary"] p, .stButton > button[kind="primary"] span, button[data-testid="stFormSubmitButton"] > button p, button[data-testid="stFormSubmitButton"] > button span {{ color: var(--on-primary) !important; }}
.stButton > button[kind="primary"]:hover, button[data-testid="stFormSubmitButton"] > button:hover {{ background-color: var(--primary-hover) !important; border-color: var(--primary-hover) !important; }}
.main .stButton > button:not([kind="primary"]):not([data-testid="stBaseButton-primary"]) {{ background-color: var(--secondary-bg) !important; border: 1px solid var(--secondary-border) !important; color: var(--secondary-text) !important; border-radius: 8px; }}
.main .stButton > button:not([kind="primary"]):not([data-testid="stBaseButton-primary"]) p, .main .stButton > button:not([kind="primary"]):not([data-testid="stBaseButton-primary"]) span {{ color: var(--secondary-text) !important; }}
.main .stButton > button:not([kind="primary"]):not([data-testid="stBaseButton-primary"]):hover {{ border-color: var(--primary) !important; }}
[data-testid="stSidebar"] {{ background-color: var(--sidebar) !important; border-right: 1px solid var(--border) !important; }}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p, [data-testid="stSidebar"] label, [data-testid="stSidebar"] span, [data-testid="stSidebar"] div {{ color: var(--text) !important; }}
[data-testid="stSidebar"] .stButton > button {{ background: transparent !important; border: 1px solid transparent !important; border-radius: 6px; justify-content: flex-start; text-align: left; width: 100%; }}
[data-testid="stSidebar"] .stButton > button p, [data-testid="stSidebar"] .stButton > button span {{ color: var(--text) !important; text-align: left; font-weight: 500; }}
[data-testid="stSidebar"] .stButton > button:hover {{ background-color: var(--sidebar-hover-bg) !important; }}
[data-testid="stSidebar"] .stButton > button:hover p, [data-testid="stSidebar"] .stButton > button:hover span {{ color: var(--sidebar-hover-text) !important; }}
[data-testid="stSidebar"] .stButton > button[kind="primary"], [data-testid="stSidebar"] .stButton > button[data-testid="stBaseButton-primary"] {{ background-color: var(--sidebar-active-bg) !important; border: 1px solid transparent !important; border-left: 3px solid var(--sidebar-active-border) !important; border-radius: 6px; }}
[data-testid="stSidebar"] .stButton > button[kind="primary"] p, [data-testid="stSidebar"] .stButton > button[data-testid="stBaseButton-primary"] p, [data-testid="stSidebar"] .stButton > button[kind="primary"] span, [data-testid="stSidebar"] .stButton > button[data-testid="stBaseButton-primary"] span {{ color: var(--sidebar-active-text) !important; font-weight: 700 !important; }}
[data-testid="stSidebar"] .kb-signout .stButton > button {{ background-color: var(--secondary-bg) !important; border: 1px solid var(--secondary-border) !important; justify-content: center; width: 100%; border-radius: 6px; }}
[data-testid="stSidebar"] .kb-signout .stButton > button p, [data-testid="stSidebar"] .kb-signout .stButton > button span {{ color: var(--secondary-text) !important; text-align: center; }}
[data-testid="stSidebar"] .kb-signout .stButton > button:hover {{ border-color: var(--primary) !important; }}
.kb-status-dot-green {{ width: 8px; height: 8px; border-radius: 50%; background: var(--success); display: inline-block; }}
.kb-sidebar-nav-label {{ font-size: 11px; font-weight: 600; color: var(--text) !important; letter-spacing: 0.06em; margin: 12px 0 6px 0; }}
.kb-sidebar-user-name {{ font-size: 14px; font-weight: 600; color: var(--text) !important; }}
.kb-sidebar-user-role {{ font-size: 12px; color: var(--text2) !important; }}
.kb-sidebar-status {{ display: flex; align-items: center; gap: 6px; font-size: 12px; color: var(--text2) !important; margin-bottom: 16px; }}
.kb-brand-box {{ width: 24px; height: 24px; border-radius: 4px; background: var(--subtle); display: flex; align-items: center; justify-content: center; color: var(--text); border: 1px solid var(--border); }}
.kb-brand-text-white {{ font-size: 16px; font-weight: 600; color: var(--text) !important; }}
[data-testid="stVerticalBlockBorderWrapper"], [data-testid="stExpander"], [data-testid="stContainer"][data-border="true"], [data-testid="stForm"] {{ background-color: var(--card) !important; border: 1px solid var(--border) !important; border-radius: 6px; }}
[data-testid="stExpander"] summary span {{ color: var(--text) !important; font-weight: 600 !important; }}
[data-testid="stFileUploader"] {{ border: 1px solid var(--input-border) !important; border-radius: 6px !important; background-color: var(--input-bg) !important; }}
[data-testid="stFileUploader"] * {{ color: var(--text) !important; }}
[data-testid="stAlert"] {{ border: 1px solid var(--border) !important; border-radius: 6px !important; background-color: var(--card) !important; color: var(--text) !important; }}
[data-testid="stAlert"] * {{ color: var(--text) !important; }}
[data-testid="stTabs"] [role="tablist"] {{ gap: 24px; border-bottom: 1px solid var(--border) !important; }}
button[data-baseweb="tab"] {{ padding-top: 8px; padding-bottom: 8px; color: var(--text) !important; }}
button[data-baseweb="tab"] p, button[data-baseweb="tab"] span {{ color: var(--text) !important; font-weight: 500; }}
button[data-baseweb="tab"][aria-selected="true"] {{ color: var(--primary) !important; border-bottom: 2px solid var(--primary) !important; }}
button[data-baseweb="tab"][aria-selected="true"] p, button[data-baseweb="tab"][aria-selected="true"] span {{ color: var(--primary) !important; font-weight: 600; }}
div[data-baseweb="tab-highlight"] {{ background-color: var(--primary) !important; }}
table, [data-testid="stTable"] table {{ width: 100%; border-collapse: collapse !important; border: 1px solid var(--border) !important; background-color: var(--card) !important; }}
th, td, [data-testid="stTable"] th, [data-testid="stTable"] td {{ border: 1px solid var(--border) !important; color: var(--text) !important; padding: 8px 12px; font-size: 14px; }}
th, [data-testid="stTable"] th {{ background-color: var(--subtle) !important; font-weight: 600 !important; }}
a {{ color: var(--primary) !important; }}
.st-key-theme_toggle_btn, div[data-testid="stElementContainer"].st-key-theme_toggle_btn, .st-key-theme_toggle, div[data-testid="stElementContainer"].st-key-theme_toggle {{ position: fixed !important; top: 0.6rem !important; right: 0.75rem !important; left: auto !important; bottom: auto !important; width: 40px !important; height: 40px !important; min-width: 40px !important; min-height: 40px !important; max-width: 40px !important; max-height: 40px !important; z-index: 1000000 !important; margin: 0 !important; padding: 0 !important; display: block !important; }}
.st-key-theme_toggle_btn .stButton, .st-key-theme_toggle .stButton {{ width: 40px !important; height: 40px !important; min-width: 40px !important; min-height: 40px !important; margin: 0 !important; padding: 0 !important; }}
.st-key-theme_toggle_btn button, .st-key-theme_toggle button, .main .stButton.st-key-theme_toggle_btn > button, div[data-testid="stButton"].st-key-theme_toggle_btn > button {{ background-color: var(--toggle-bg) !important; border: 1px solid var(--toggle-border) !important; border-radius: 8px !important; width: 40px !important; height: 40px !important; min-width: 40px !important; min-height: 40px !important; max-width: 40px !important; max-height: 40px !important; padding: 0 !important; margin: 0 !important; display: flex !important; align-items: center !important; justify-content: center !important; color: var(--toggle-text) !important; box-shadow: none !important; }}
.st-key-theme_toggle_btn button p, .st-key-theme_toggle_btn button span, .st-key-theme_toggle button p, .st-key-theme_toggle button span, .main .stButton.st-key-theme_toggle_btn > button p, .main .stButton.st-key-theme_toggle_btn > button span {{ color: var(--toggle-text) !important; font-size: 20px !important; line-height: 1 !important; margin: 0 !important; padding: 0 !important; }}
.st-key-theme_toggle_btn button:hover, .st-key-theme_toggle button:hover, .main .stButton.st-key-theme_toggle_btn > button:hover {{ border-color: var(--primary) !important; }}
.st-key-theme_toggle_btn button:hover p, .st-key-theme_toggle_btn button:hover span, .st-key-theme_toggle button:hover p, .st-key-theme_toggle button:hover span, .main .stButton.st-key-theme_toggle_btn > button:hover p, .main .stButton.st-key-theme_toggle_btn > button:hover span {{ color: var(--primary) !important; }}
.kb-receipt-card {{ background: var(--card); border: 1px solid var(--border); border-left: 3px solid var(--success); border-radius: 6px; padding: 14px 18px; margin: 14px 0; }}
.kb-notice-banner {{ background: var(--card); border: 1px solid var(--border); border-left: 3px solid var(--primary); border-radius: 6px; padding: 12px 16px; margin-bottom: 16px; font-size: 14px; color: var(--text); }}
.kb-pill {{ font-size: 12px; font-weight: 500; border-radius: 999px; padding: 2px 10px; display: inline-flex; align-items: center; gap: 6px; white-space: nowrap; }}
.kb-pill-draft {{ background: var(--draft-bg); color: var(--draft-text); }}
.kb-pill-ready {{ background: var(--ready-bg); color: var(--ready-text); }}
.kb-pill-info {{ background: var(--ready-bg); color: var(--ready-text); }}
.kb-pill-success {{ background: var(--card); color: var(--success); border: 1px solid var(--border); }}
.kb-pill-warning {{ background: var(--draft-bg); color: var(--draft-text); }}
.kb-dot-success {{ background: var(--success); width: 8px; height: 8px; border-radius: 50%; display: inline-block; }}
.kb-dot-warning {{ background: var(--draft-bg); width: 8px; height: 8px; border-radius: 50%; display: inline-block; }}
.kb-dot-info {{ background: var(--primary); width: 8px; height: 8px; border-radius: 50%; display: inline-block; }}
.kb-dot-muted {{ background: var(--text2); width: 8px; height: 8px; border-radius: 50%; display: inline-block; }}
.kb-top-navbar {{ display: flex; align-items: center; justify-content: space-between; padding: 10px 16px; border: 1px solid var(--border); border-radius: 6px; margin-bottom: 20px; gap: 12px; flex-wrap: wrap; background: var(--card); }}
.kb-nav-brand {{ display: flex; align-items: center; gap: 8px; }}
.kb-brand-logo {{ width: 24px; height: 24px; border-radius: 4px; background: var(--subtle); display: flex; align-items: center; justify-content: center; color: var(--text); border: 1px solid var(--border); }}
.kb-brand-title {{ font-size: 16px; font-weight: 600; color: var(--text); }}
.kb-brand-sub {{ font-size: 12px; color: var(--text2); margin-left: 4px; }}
.kb-nav-steps {{ display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }}
.kb-step-connector {{ width: 10px; height: 1px; background: var(--border); }}
.kb-nav-step-item {{ display: inline-flex; align-items: center; gap: 5px; font-size: 13px; font-weight: 500; color: var(--text2); padding: 3px 7px; border-radius: 4px; }}
.kb-nav-step-item.active {{ background: var(--sidebar-active-bg); color: var(--sidebar-active-text); font-weight: 600; border: 1px solid var(--border); }}
.kb-nav-step-item.done {{ color: var(--text); }}
.kb-step-num {{ display: inline-flex; align-items: center; justify-content: center; width: 16px; height: 16px; border-radius: 3px; font-size: 11px; font-weight: 600; background: var(--subtle); color: var(--text); }}
.kb-nav-persona {{ display: flex; align-items: center; gap: 6px; background: var(--subtle); border: 1px solid var(--border); padding: 3px 10px; border-radius: 4px; font-size: 13px; color: var(--text); }}
.kb-avatar-chip {{ width: 18px; height: 18px; border-radius: 3px; background: var(--border); color: var(--text); font-size: 10px; font-weight: 700; display: inline-flex; align-items: center; justify-content: center; }}
.kb-plain-table {{ width: 100%; border-collapse: collapse; margin: 10px 0 14px 0; border: 1px solid var(--border); border-radius: 6px; overflow: hidden; background: var(--card); }}
.kb-plain-table th {{ background: var(--subtle); color: var(--text); font-weight: 600; font-size: 12px; padding: 9px 13px; text-align: left; border-bottom: 1px solid var(--border); }}
.kb-plain-table td {{ padding: 9px 13px; border-bottom: 1px solid var(--border); color: var(--text); font-size: 13px; vertical-align: top; background: var(--card); }}
.kb-plain-table tr:last-child td {{ border-bottom: none; }}
</style>""").strip()
    st.markdown(css, unsafe_allow_html=True)


def render_theme_toggle() -> None:
    mode = get_theme_mode()
    icon = THEME_ICONS[mode]
    help_text = "Switch to dark mode" if mode == "light" else "Switch to light mode"
    if st.button(icon, key="theme_toggle_btn", help=help_text):
        st.session_state.theme_mode = "dark" if mode == "light" else "light"
        st.rerun()


inject_theme_css(_theme_mode)
render_theme_toggle()


# ─── INLINE SVG HELPERS ───────────────────────────────────────────────────────
def icon_svg(name: str, size: int = 14) -> str:
    """Enterprise inline SVG icons (replaces emojis)."""
    icons = {
        "baton": f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="display:inline-block;vertical-align:-2px;"><path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z"></path><path d="m12 15-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z"></path></svg>',
        "file": f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="display:inline-block;vertical-align:-2px;"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline></svg>',
        "repo": f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="display:inline-block;vertical-align:-2px;"><polyline points="16 18 22 12 16 6"></polyline><polyline points="8 6 2 12 8 18"></polyline></svg>',
        "text": f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="display:inline-block;vertical-align:-2px;"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path></svg>',
        "check": f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="display:inline-block;vertical-align:-2px;"><polyline points="20 6 9 17 4 12"></polyline></svg>',
        "shield": f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="display:inline-block;vertical-align:-2px;"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path></svg>',
        "user": f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="display:inline-block;vertical-align:-2px;"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>',
    }
    return icons.get(name, "")


# ─── COMPONENT RENDER HELPERS ─────────────────────────────────────────────────
def render_file_row(filename: str, size_bytes: int) -> str:
    """Clean file row with extension chip and formatted size."""
    ext = filename.rsplit(".", 1)[-1].upper() if "." in filename else "DOC"
    if size_bytes < 1024:
        size_str = f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        size_str = f"{size_bytes / 1024:.1f} KB"
    else:
        size_str = f"{size_bytes / (1024*1024):.1f} MB"
    return textwrap.dedent(f"""
    <div style="display:flex;align-items:center;justify-content:space-between;background:var(--subtle);border:1px solid var(--border);border-radius:6px;padding:8px 12px;margin-bottom:6px;font-size:13px;color:var(--text);">
        <div style="display:flex;align-items:center;gap:8px;">
            {icon_svg("file", 13)}
            <span style="font-family:monospace;font-size:11px;font-weight:600;background:var(--surface);color:var(--text);padding:1px 5px;border-radius:3px;border:1px solid var(--border);">{ext}</span>
            <span style="font-weight:500;">{filename}</span>
        </div>
        <span style="font-size:12px;color:var(--text-2);">{size_str}</span>
    </div>
    """).strip()


def render_citation(source: str, excerpt: str) -> str:
    """Structured citation block: thin left border, monospace 13px text, file name above as a small label."""
    if not excerpt:
        return ""
    clean_excerpt = redact_sensitive_info(excerpt)
    return textwrap.dedent(f"""
    <div style="border-left:2px solid var(--border);padding:3px 0 3px 10px;margin:6px 0;background:transparent;">
        <div style="font-size:11px;font-family:monospace;color:var(--text-2);margin-bottom:2px;">{source}</div>
        <div style="font-size:13px;font-family:monospace;color:var(--text);line-height:1.45;">"{clean_excerpt}"</div>
    </div>
    """).strip()


def render_audit_entry(entry: dict) -> str:
    """Structured audit log row with monospace timestamp."""
    status_color = "var(--text)"
    action_text = entry.get('action', '')
    return textwrap.dedent(f"""
    <div style="display:flex;gap:12px;padding:6px 0;border-bottom:1px solid var(--border);font-size:13px;">
        <span style="font-family:monospace;font-size:12px;color:var(--text-2);width:150px;">{entry.get('timestamp', '')}</span>
        <span style="font-weight:600;width:100px;">{entry.get('who', '')}</span>
        <span style="font-weight:500;width:180px;">{action_text}</span>
        <span style="color:var(--text-2);flex:1;">{entry.get('reason', '')}</span>
    </div>
    """).strip()


def render_receipt_card(name: str, timestamp: str, project: str, employee: str) -> str:
    """Post-acknowledgment signed receipt card."""
    return textwrap.dedent(f"""
    <div class="kb-receipt-card">
        <div style="display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid var(--border);padding-bottom:8px;margin-bottom:10px;">
            <span class="kb-pill kb-pill-success">Receipt acknowledged</span>
            <span style="font-family:monospace;font-size:12px;color:var(--text-2);">{timestamp}</span>
        </div>
        <div style="display:flex;flex-direction:column;gap:5px;">
            <div style="display:flex;justify-content:space-between;font-size:13px;">
                <span style="color:var(--text-2);">Successor</span>
                <span style="color:var(--text);font-weight:500;">{name}</span>
            </div>
            <div style="display:flex;justify-content:space-between;font-size:13px;">
                <span style="color:var(--text-2);">Knowledge holder</span>
                <span style="color:var(--text);font-weight:500;">{employee}</span>
            </div>
            <div style="display:flex;justify-content:space-between;font-size:13px;">
                <span style="color:var(--text-2);">Project scope</span>
                <span style="color:var(--text);font-weight:500;">{project}</span>
            </div>
            <div style="display:flex;justify-content:space-between;font-size:13px;">
                <span style="color:var(--text-2);">Status</span>
                <span style="font-weight:500;">Handover complete</span>
            </div>
        </div>
    </div>
    """).strip()



# ─── COMPONENT HELPERS ────────────────────────────────────────────────────────
def source_badge(source_type: str) -> str:
    st_type = str(source_type).lower()
    labels = {
        "file": "File",
        "github": "Repository",
        "text": "Notes",
    }
    label = labels.get(st_type, "Source")
    return f'<span class="kb-pill kb-pill-draft">{label}</span>'


def confidence_badge(confidence: str) -> str:
    c = str(confidence).upper()
    if c == "HIGH":
        return '<span class="kb-pill kb-pill-success">High confidence</span>'
    elif c == "LOW":
        return '<span class="kb-pill kb-pill-draft">Low confidence</span>'
    else:
        return '<span class="kb-pill kb-pill-warning">Medium confidence</span>'


def render_stat_card(label: str, number: str) -> str:
    """Clean flat metric card."""
    return textwrap.dedent(f"""
    <div style="background:var(--surface);border:1px solid var(--border);border-radius:6px;padding:12px 16px;margin-bottom:8px;">
        <div style="font-size:12px;color:var(--text-2);text-transform:uppercase;margin-bottom:4px;">{label}</div>
        <div style="font-size:20px;font-weight:600;color:var(--text);">{number}</div>
    </div>
    """).strip()


def step_indicator(current_page: str):
    """Authoritative top workflow navigation bar adapted by role."""
    role = st.session_state.get("auth_role", "Manager")
    if role == "Employee":
        pages = [
            ("connect",        "1", "Connect"),
            ("reconstruct",    "2", "Reconstruct"),
            ("employee",       "3", "Verify"),
            ("employee_notes", "4", "My notes"),
        ]
    elif role == "Successor":
        pages = [
            ("successor_handover", "1", "Technical handover"),
        ]
    else:  # Manager
        pages = [
            ("review",   "1", "Review"),
            ("handover", "2", "Handover"),
            ("audit",    "3", "Audit log"),
        ]

    page_order = [p[0] for p in pages]
    current_idx = page_order.index(current_page) if current_page in page_order else 0

    user_name = st.session_state.get("auth_name") or "User"
    initials = "".join([part[0] for part in user_name.split() if part])[:2].upper() if user_name else "HB"

    html = textwrap.dedent(f"""
    <div class="kb-top-navbar">
        <div class="kb-nav-brand">
            <div class="kb-brand-logo">{icon_svg("baton", 14)}</div>
            <span class="kb-brand-title">Baton</span>
            <span class="kb-brand-sub">{role} workspace</span>
        </div>
        <div class="kb-nav-steps">
    """).strip()
    for i, (pid, num, title) in enumerate(pages):
        if i < current_idx:
            cls = "done"
            badge = f'<span class="kb-step-num">{icon_svg("check", 10)}</span>'
        elif i == current_idx:
            cls = "active"
            badge = f'<span class="kb-step-num">{num}</span>'
        else:
            cls = "idle"
            badge = f'<span class="kb-step-num">{num}</span>'
        html += f'<div class="kb-nav-step-item {cls}">{badge}<span>{title}</span></div>'
        if i < len(pages) - 1:
            html += '<div class="kb-step-connector"></div>'
    html += '</div>'
    html += f'<div class="kb-nav-persona"><span class="kb-avatar-chip">{initials}</span> <span>{user_name}</span> <span style="opacity:0.6;">&rarr;</span> <span style="font-weight:600;">{role}</span></div>'
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)


def render_role_status_line(role: str):
    """Renders single prominent status line for the role's current progress."""
    profile = st.session_state.get("knowledge_profile")
    total_verifiable = len(profile.get("decisions", [])) + len(profile.get("risks", [])) if profile else 0
    verified = len(st.session_state.get("employee_verifications", {}))
    total_gaps = len(profile.get("unresolved", [])) if profile else 0
    answered = sum(
        1 for q in (profile.get("unresolved", []) if profile else [])
        if st.session_state.get("employee_gap_answers", {}).get(q.get("question", ""), "").strip()
    )
    approvals = st.session_state.get("approvals", {})
    all_approved = sum(1 for v in approvals.values() if v is True) >= 5
    has_handover = bool(st.session_state.get("manager_handover") and st.session_state.get("newhire_handover"))
    has_ack = bool(st.session_state.get("acknowledgement"))

    if role == "Manager":
        if not profile:
            st_text, dot_cls = "Waiting for employee to upload sources", "kb-dot-muted"
        elif verified < total_verifiable or answered < total_gaps:
            st_text, dot_cls = "Waiting for employee input", "kb-dot-warning"
        elif not all_approved:
            st_text, dot_cls = "Ready for manager review", "kb-dot-info"
        elif not has_handover:
            st_text, dot_cls = "Ready for handover generation", "kb-dot-info"
        else:
            st_text, dot_cls = "Handover available", "kb-dot-success"
    elif role == "Employee":
        if not profile:
            st_text, dot_cls = "Waiting for knowledge reconstruction", "kb-dot-muted"
        elif verified < total_verifiable or answered < total_gaps:
            st_text, dot_cls = "Action required: verify findings and answer gaps", "kb-dot-warning"
        elif not all_approved:
            st_text, dot_cls = "Ready for manager review", "kb-dot-info"
        else:
            st_text, dot_cls = "Handover package approved", "kb-dot-success"
    elif role == "Successor":
        if not has_handover or not all_approved:
            st_text, dot_cls = "Handover not approved yet", "kb-dot-warning"
        elif not has_ack:
            st_text, dot_cls = "Handover available — acknowledge receipt", "kb-dot-info"
        else:
            st_text, dot_cls = "Handover acknowledged", "kb-dot-success"
    else:
        st_text, dot_cls = "Active", "kb-dot-info"

    st.markdown(textwrap.dedent(f"""
    <div style="background:var(--subtle); border:1px solid var(--border); border-radius:6px; padding:8px 14px; margin-bottom:14px; display:flex; align-items:center; gap:8px;">
        <span class="kb-dot {dot_cls}" style="width:8px; height:8px; border-radius:50%; display:inline-block;"></span>
        <span style="font-size:13px; color:var(--text); font-weight:500;">Status: <b>{st_text}</b></span>
    </div>
    """).strip(), unsafe_allow_html=True)


def render_login_page():
    """Renders the login page."""
    col_pad1, col_center, col_pad2 = st.columns([1, 2, 1])
    with col_center:
        st.markdown(textwrap.dedent("""
            <div style="max-width:440px;margin:24px auto 16px auto;text-align:center;">
              <div style="font-size:28px;font-weight:600;color:var(--text);line-height:1.2;">Baton</div>
              <div style="font-size:14px;color:var(--text-2);margin-top:4px;">Institutional knowledge preservation and handover platform</div>
            </div>
        """).strip(), unsafe_allow_html=True)
        st.caption("Demo data: the names Sarah Chen, Marcus Vance and Manager are synthetic. No real people or company information is used.")

        with st.container(border=True):
            with st.form("login_form", clear_on_submit=False):
                st.markdown(textwrap.dedent("""
                    <div style="font-size:16px;font-weight:600;color:var(--text);margin-bottom:8px;">Sign in to your account</div>
                """).strip(), unsafe_allow_html=True)
                if is_locked():
                    sec = get_lockout_remaining()
                    st.error(f"Too many wrong attempts. Login locked for {sec} second(s).")
                username_input = st.text_input("Username", placeholder="e.g. manager, sarah, marcus")
                password_input = st.text_input("Password", type="password", placeholder="Enter password")
                submit_login = st.form_submit_button("Sign in", type="primary", use_container_width=True, disabled=is_locked())
                if submit_login:
                    ok, msg, user = authenticate(username_input, password_input)
                    if ok and user:
                        st.session_state.authenticated = True
                        st.session_state.auth_username = user["username"]
                        st.session_state.auth_role = user["role"]
                        st.session_state.auth_name = user["name"]
                        if user["role"] == "Employee":
                            st.session_state.employee_name = user["name"]
                        notice = load_into_session(st.session_state)
                        if notice:
                            st.session_state.state_notice = notice
                        ensure_member(st.session_state, user)
                        log_audit_entry(st.session_state, user["username"], "Login successful")
                        if user["role"] == "Manager":
                            st.session_state.page = "review"
                        elif user["role"] == "Employee":
                            st.session_state.page = "employee"
                        elif user["role"] == "Successor":
                            st.session_state.page = "successor_handover"
                        st.rerun()
                    else:
                        log_audit_entry(st.session_state, (username_input or "").strip() or "anonymous", "Failed login attempt", reason=msg)
                        st.error(msg)


# ─── SIDEBAR ──────────────────────────────────────────────────────────────────
with st.sidebar:
    # 1. Baton logo and name
    st.markdown(textwrap.dedent(f"""
        <div style="display:flex;align-items:center;gap:8px;padding:4px 0 12px 0;margin-bottom:12px;">
          <div class="kb-brand-box">
            {icon_svg("baton", 14)}
          </div>
          <span class="kb-brand-text-white">Baton</span>
        </div>
    """).strip(), unsafe_allow_html=True)

    if st.session_state.get("authenticated"):
        auth_name = st.session_state.get("auth_name") or ""
        auth_role = st.session_state.get("auth_role") or ""
        auth_user = st.session_state.get("auth_username") or ""

        # 2. User block
        if auth_name:
            st.markdown(textwrap.dedent(f"""
                <div style="padding:4px 0 8px 0;margin-bottom:8px;">
                  <div class="kb-sidebar-user-name">{auth_name}</div>
                  <div class="kb-sidebar-user-role">{auth_role}</div>
                </div>
            """).strip(), unsafe_allow_html=True)

        # 3. Status line: 8px green dot followed by Gemini API connected in plain text. No box.
        if st.session_state.get("api_key"):
            st.markdown(textwrap.dedent("""
                <div class="kb-sidebar-status">
                  <span class="kb-status-dot-green"></span>
                  <span>Gemini API connected</span>
                </div>
            """).strip(), unsafe_allow_html=True)

        # 4. Small uppercase section label NAVIGATION at 11px
        st.markdown(textwrap.dedent("""
            <div class="kb-sidebar-nav-label">NAVIGATION</div>
        """).strip(), unsafe_allow_html=True)

        # 5. Nav buttons
        PAGE_LABELS = {
            "connect": "Connect sources",
            "reconstruct": "Reconstruct",
            "employee": "Employee hub",
            "employee_notes": "My notes",
            "review": "Manager review",
            "handover": "Handover package",
            "successor_handover": "Technical handover",
            "audit": "Audit log",
            "my_access": "My access",
            "access_management": "Access management",
            "notifications": "Notifications",
            "confidential": "Confidential files",
        }

        current_member = {
            "id": auth_user,
            "username": auth_user,
            "name": auth_name,
            "role": auth_role,
        }
        allowed_page_ids = get_allowed_pages(st.session_state, current_member)
        unread_count = sum(1 for n in st.session_state.get("notifications", []) if n.get("to") == auth_user and not n.get("read"))

        nav_pages = []
        for pid in allowed_page_ids:
            if pid == "notifications":
                lbl = f"Notifications ({unread_count})" if unread_count > 0 else "Notifications"
            else:
                lbl = PAGE_LABELS.get(pid, pid.replace("_", " ").title())
            nav_pages.append((pid, lbl))

        for page_id, page_label in nav_pages:
            is_active = st.session_state.page == page_id
            disabled = False
            if auth_role == "Employee" and page_id in ("reconstruct", "employee", "employee_notes") and not st.session_state.knowledge_profile:
                disabled = True
            elif auth_role == "Employee" and page_id == "employee_notes" and not st.session_state.employee_handover:
                disabled = True
            elif auth_role == "Manager" and page_id in ("handover",) and not st.session_state.manager_handover:
                disabled = True
            if st.button(
                page_label,
                use_container_width=True,
                type="primary" if is_active else "secondary",
                disabled=disabled,
                key=f"nav_{page_id}"
            ):
                st.session_state.page = page_id
                st.rerun()

        # 6. Sign out button at bottom: 1px border, transparent background
        st.markdown('<div class="kb-signout" style="margin-top:24px;">', unsafe_allow_html=True)
        if st.button("Sign out", key="btn_sign_out_sidebar", use_container_width=True):
            log_audit_entry(st.session_state, auth_user, "Logged out")
            logout(st.session_state)
            st.session_state.page = "connect"
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)



# ─── AUTHENTICATION GATE ───────────────────────────────────────────────────────
if not st.session_state.get("authenticated"):
    render_login_page()
    st.stop()

# Toast notifications for unread items
_cur_uid = st.session_state.get("auth_username", "")
if "toasted_ids" not in st.session_state or not isinstance(st.session_state.toasted_ids, set):
    st.session_state.toasted_ids = set()
for notif in st.session_state.get("notifications", []):
    if notif.get("to") == _cur_uid and not notif.get("read") and notif.get("id") not in st.session_state.toasted_ids:
        st.toast(notif.get("message", ""))
        st.session_state.toasted_ids.add(notif.get("id"))

# ─── ROLE-BASED ACCESS CONTROL ────────────────────────────────────────────────
ROLE_PERMISSIONS = {
    "Manager":   ["review", "handover", "audit"],
    "Employee":  ["connect", "reconstruct", "employee", "employee_notes"],
    "Successor": ["successor_handover"],
}

_current_member = {
    "id": st.session_state.get("auth_username", ""),
    "username": st.session_state.get("auth_username", ""),
    "name": st.session_state.get("auth_name", ""),
    "role": st.session_state.get("auth_role", ""),
}
_allowed_pages = get_allowed_pages(st.session_state, _current_member)

if st.session_state.page not in _allowed_pages:
    log_audit_entry(
        st.session_state,
        _current_member["id"] or "unknown",
        "access denied",
        reason=f"Attempted to access {st.session_state.page}"
    )
    st.error("Access denied for your role")
    st.stop()

# Log page views once per navigation
_last_page = st.session_state.get("_last_logged_page", "")
if _last_page != st.session_state.page:
    log_audit_entry(st.session_state, st.session_state.get("auth_username", "user"), f"Viewed page: {st.session_state.page}")
    st.session_state["_last_logged_page"] = st.session_state.page

if st.session_state.get("state_notice"):
    st.info(st.session_state.state_notice)
    st.session_state.state_notice = None


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 1: CONNECT SOURCES
# ═══════════════════════════════════════════════════════════════════════════════
if st.session_state.page == "connect":
    require_page_access("connect")
    step_indicator("connect")



    st.markdown(textwrap.dedent("""
    <div class="kb-notice-banner">
      Connect documents, a repository, or transition notes. Baton extracts key decisions and risks for verification and review.
    </div>
    """).strip(), unsafe_allow_html=True)

    col_left, col_right = st.columns([7, 5], gap="large")

    with col_left:
        st.markdown('<div class="kb-section-title">1. Connect knowledge sources</div>', unsafe_allow_html=True)

        tab1, tab2, tab3 = st.tabs(["Upload files", "GitHub repository", "Paste content"])

        with tab1:
            uploaded_files = st.file_uploader(
                "Upload documents (PDF, TXT, MD, Markdown)",
                type=["pdf", "txt", "md", "markdown"],
                accept_multiple_files=True,
                help="Architecture specifications, design decisions, runbooks, or transition notes"
            )
            if uploaded_files:
                st.session_state.uploaded_files = uploaded_files
                for f in uploaded_files:
                    st.markdown(
                        render_file_row(f.name, f.size),
                        unsafe_allow_html=True
                    )

        with tab2:
            github_url = st.text_input(
                "GitHub repository URL",
                value=st.session_state.github_url,
                placeholder="https://github.com/organization/microservice",
                help="Public repositories work automatically without access tokens"
            )
            st.session_state.github_url = github_url

            github_token = st.text_input(
                "Personal access token (optional for private repositories)",
                type="password",
                value=st.session_state.github_token,
                placeholder="ghp_...",
                help="Only required if the repository is private"
            )
            st.session_state.github_token = github_token

            if github_url:
                st.info(f"Connector will extract README, recent commits, open issues, and pull requests from {github_url}")

        with tab3:
            pasted_text = st.text_area(
                "Paste notes, communication excerpts, or transition logs",
                value=st.session_state.pasted_text,
                height=180,
                placeholder="Paste informal transition notes, architecture rationale, or unwritten rules...\n\nExample:\n- Chose PostgreSQL for ACID transactional ledger guarantee\n- Stripe webhook signing secret rotates every 6 months\n- Known issue: Redis session keys lack explicit eviction runbook"
            )
            st.session_state.pasted_text = pasted_text

        st.markdown("<br>", unsafe_allow_html=True)

        st.markdown('<div class="kb-section-title">2. Scope and departing context</div>', unsafe_allow_html=True)

        col_p1, col_p2 = st.columns(2)
        _emp_readonly = st.session_state.get("auth_role") == "Employee"
        if _emp_readonly and st.session_state.get("auth_name"):
            st.session_state.employee_name = st.session_state.auth_name
        with col_p1:
            employee_name = st.text_input(
                "Departing employee name",
                value=st.session_state.employee_name,
                placeholder="e.g. Sarah Chen",
                disabled=_emp_readonly,
            )
            if not _emp_readonly:
                st.session_state.employee_name = employee_name

        with col_p2:
            project_role = st.text_input(
                "Role and project scope",
                value=st.session_state.project_role,
                placeholder="e.g. Senior Backend Engineer, PayFlow",
            )
            st.session_state.project_role = project_role

    with col_right:
        emp_raw = (st.session_state.get("employee_name") or "").strip()
        emp_display = emp_raw if emp_raw else '<span style="color:var(--text2);">Not provided</span>'

        role_raw = (st.session_state.get("project_role") or "").strip()
        role_display = role_raw if role_raw else '<span style="color:var(--text2);">Not provided</span>'

        file_count = len(st.session_state.uploaded_files) if st.session_state.uploaded_files else 0
        file_display = f"{file_count} uploaded" if file_count > 0 else '<span style="color:var(--text2);">Not provided</span>'

        has_gh = bool(st.session_state.github_url.strip())
        gh_display = st.session_state.github_url.strip() if has_gh else '<span style="color:var(--text2);">Not provided</span>'

        notes_raw = st.session_state.pasted_text.strip()
        notes_display = f"{len(notes_raw)} chars" if notes_raw else '<span style="color:var(--text2);">Not provided</span>'

        has_sources = bool(
            (st.session_state.uploaded_files) or
            (st.session_state.github_url.strip()) or
            (st.session_state.pasted_text.strip())
        )

        if st.session_state.get("knowledge_profile"):
            status_pill_html = '<span class="kb-pill kb-pill-success">Verified</span>'
        elif has_sources:
            status_pill_html = '<span class="kb-pill kb-pill-info">Ready for analysis</span>'
        else:
            status_pill_html = '<span class="kb-pill kb-pill-draft">Draft</span>'

        preview_html = textwrap.dedent(f"""
        <div style="background:var(--surface);border:1px solid var(--border);border-radius:6px;padding:16px;margin-bottom:16px;">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
            <span style="font-size:16px;font-weight:600;color:var(--text);">Staged handover dossier</span>
            {status_pill_html}
          </div>
          <table style="width:100%;border-collapse:collapse;font-size:13px;">
            <tbody>
              <tr style="border-bottom:1px solid var(--border);">
                <td style="padding:8px 0;color:var(--text2);width:40%;">Departing engineer</td>
                <td style="padding:8px 0;color:var(--text);font-weight:500;">{emp_display}</td>
              </tr>
              <tr style="border-bottom:1px solid var(--border);">
                <td style="padding:8px 0;color:var(--text2);">Project scope</td>
                <td style="padding:8px 0;color:var(--text);font-weight:500;">{role_display}</td>
              </tr>
              <tr style="border-bottom:1px solid var(--border);">
                <td style="padding:8px 0;color:var(--text2);">Source documents</td>
                <td style="padding:8px 0;color:var(--text);font-weight:500;">{file_display}</td>
              </tr>
              <tr style="border-bottom:1px solid var(--border);">
                <td style="padding:8px 0;color:var(--text2);">Code repository</td>
                <td style="padding:8px 0;color:var(--text);font-weight:500;">{gh_display}</td>
              </tr>
              <tr>
                <td style="padding:8px 0;color:var(--text2);">Notes</td>
                <td style="padding:8px 0;color:var(--text);font-weight:500;">{notes_display}</td>
              </tr>
            </tbody>
          </table>
        </div>
        """).strip()
        st.markdown(preview_html, unsafe_allow_html=True)

        has_sources = bool(
            (st.session_state.uploaded_files) or
            (st.session_state.github_url.strip()) or
            (st.session_state.pasted_text.strip())
        )

        def _reset_downstream():
            st.session_state.employee_verifications = {}
            st.session_state.employee_gap_answers = {}
            st.session_state.approvals = {}
            st.session_state.corrections = {}
            st.session_state.employee_tribal_knowledge = []
            st.session_state.manager_handover = None
            st.session_state.newhire_handover = None
            st.session_state.employee_handover = None
            st.session_state.action_history = []
            st.session_state.acknowledgement = None

        analyze_btn = st.button(
            "Analyze and reconstruct knowledge",
            type="primary",
            use_container_width=True,
            disabled=not (has_sources and bool(st.session_state.api_key)),
        )
        if analyze_btn:
            if st.session_state.analyses_run >= 3:
                st.warning("Session limit reached. Please refresh the page to start a new session.")
            else:
                st.session_state.analyses_run += 1
                _reset_downstream()
                all_sources = []
                errors = []

                with st.spinner("Ingesting and parsing sources..."):
                    if st.session_state.uploaded_files:
                        try:
                            from utils.file_processor import process_files
                            file_results = process_files(st.session_state.uploaded_files)
                            all_sources.extend(file_results)
                        except Exception as e:
                            errors.append(f"File parsing: {_safe_err(e)}")

                    if st.session_state.github_url.strip():
                        try:
                            from utils.github_connector import fetch_repo_knowledge
                            github_results = fetch_repo_knowledge(
                                st.session_state.github_url.strip(),
                                token=st.session_state.github_token.strip() or None
                            )
                            all_sources.extend(github_results)
                        except Exception as e:
                            errors.append(f"GitHub connector: {_safe_err(e)}")

                    if st.session_state.pasted_text.strip():
                        all_sources.append({
                            "content": st.session_state.pasted_text.strip(),
                            "source": "Pasted Notes",
                            "source_type": "text"
                        })

                if errors:
                    for err in errors:
                        st.warning(err)
                    if not all_sources:
                        st.error("No valid sources could be ingested.")
                        st.stop()

                if not all_sources:
                    st.error("Please add at least one file, repository, or note to proceed.")
                    st.stop()

                total_len = sum(len(s.get("content", "")) for s in all_sources)
                _was_truncated = False
                if total_len > 30000:
                    _was_truncated = True
                    running = 0
                    trimmed = []
                    for s in all_sources:
                        rem = 30000 - running
                        if rem <= 0:
                            break
                        c = s.get("content", "")
                        if len(c) > rem:
                            c = c[:rem] + "\n[Source truncated: only the first 30000 characters were analyzed]"
                        trimmed.append({**s, "content": c})
                        running += len(c)
                    all_sources = trimmed
                if _was_truncated:
                    st.warning("Input was cut at 30,000 characters. Only the first part was analyzed.")

                st.session_state.all_sources = all_sources

                with st.spinner(f"Reconstructing knowledge graph across {len(all_sources)} source(s)..."):
                    try:
                        from utils.gemini_engine import analyze_sources
                        profile = analyze_sources(all_sources, st.session_state.api_key)
                        def _rec(d):
                            d["knowledge_profile"] = profile
                            d["all_sources"] = all_sources
                            d["analyses_run"] = st.session_state.analyses_run
                        modify_project_state(_rec, session_state=st.session_state)
                        log_audit_entry(st.session_state, st.session_state.get("auth_username","user"), "Knowledge profile reconstructed")
                        st.session_state.page = "reconstruct"
                        st.rerun()
                    except Exception as e:
                        st.error(f"Gemini analysis error: {_safe_err(e)}")
                        st.info("Check your key at aistudio.google.com")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 2: RECONSTRUCT KNOWLEDGE PROFILE
# ═══════════════════════════════════════════════════════════════════════════════
elif st.session_state.page == "reconstruct":
    require_page_access("reconstruct")
    step_indicator("reconstruct")

    profile = st.session_state.knowledge_profile
    if not profile:
        st.error("No knowledge profile found. Please start by connecting sources.")
        st.stop()



    # Executive Hero Banner
    st.markdown(textwrap.dedent(f"""
    <div class="kb-panel-hero">
        <div style="display:flex; justify-content:space-between; align-items:flex-start; flex-wrap:wrap; gap:12px;">
            <div>
                <h2 style="font-size:18px; font-weight:600; color:var(--text); margin:0 0 4px 0;">Reconstructed knowledge profile</h2>
                <div style="color:var(--text-2); font-size:13px;">
                    <b>Departing:</b> {st.session_state.employee_name or 'Unknown'} &nbsp;|&nbsp;
                    <b>Project scope:</b> {st.session_state.project_role or 'Unknown'}
                </div>
            </div>
            <span class="kb-status-dot-item" style="color:var(--text-2);"><span class="kb-dot" style="background-color:var(--accent);"></span>Citation-linked</span>
        </div>
        <p style="font-size:14px; line-height:1.6; color:var(--text); margin-top:12px; margin-bottom:0;">
            {profile.get("summary", "")}
        </p>
    </div>
    """).strip(), unsafe_allow_html=True)

    # Compact Summary Row with Dividers
    dec_count = len(profile.get("decisions", []))
    risk_count = len(profile.get("risks", []))
    gap_count = len(profile.get("unresolved", []))
    contact_count = len(profile.get("contacts", []))
    dep_count = len(profile.get("dependencies", []))

    st.markdown(textwrap.dedent(f"""
    <div class="kb-summary-row">
        <div class="kb-summary-item">
            <span class="kb-summary-num">{dec_count}</span>
            <span class="kb-summary-label">Decisions</span>
        </div>
        <div class="kb-summary-divider"></div>
        <div class="kb-summary-item">
            <span class="kb-summary-num">{risk_count}</span>
            <span class="kb-summary-label">Risks</span>
        </div>
        <div class="kb-summary-divider"></div>
        <div class="kb-summary-item">
            <span class="kb-summary-num">{gap_count}</span>
            <span class="kb-summary-label">Knowledge gaps</span>
        </div>
        <div class="kb-summary-divider"></div>
        <div class="kb-summary-item">
            <span class="kb-summary-num">{contact_count}</span>
            <span class="kb-summary-label">Contacts</span>
        </div>
        <div class="kb-summary-divider"></div>
        <div class="kb-summary-item">
            <span class="kb-summary-num">{dep_count}</span>
            <span class="kb-summary-label">Dependencies</span>
        </div>
    </div>
    """).strip(), unsafe_allow_html=True)

    # Clean Solid Distribution Bar
    high_count = sum(1 for d in profile.get("decisions", []) if d.get("confidence") == "HIGH")
    med_count = sum(1 for d in profile.get("decisions", []) if d.get("confidence") == "MEDIUM")
    low_count = sum(1 for d in profile.get("decisions", []) if d.get("confidence") == "LOW")
    total_d = max(1, len(profile.get("decisions", [])))
    high_pct = int((high_count / total_d) * 100)
    med_pct = int((med_count / total_d) * 100)
    low_pct = 100 - high_pct - med_pct

    st.markdown(textwrap.dedent(f"""
    <div style="background:var(--surface-2); border:1px solid var(--border); border-radius:var(--radius); padding:12px 16px; margin-bottom:20px;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
            <span style="font-size:13px; font-weight:600; color:var(--text);">Evidence confidence breakdown</span>
            <span style="font-size:13px; color:var(--text-2);">{high_pct}% High • {med_pct}% Medium • {low_pct}% Low</span>
        </div>
        <div style="height:6px; border-radius:4px; display:flex; overflow:hidden; background:var(--border);">
            <div style="width:{high_pct}%; background:var(--success);" title="High confidence: {high_count}"></div>
            <div style="width:{med_pct}%; background:var(--warning);" title="Medium confidence: {med_count}"></div>
            <div style="width:{low_pct}%; background:var(--error);" title="Low confidence: {low_count}"></div>
        </div>
    </div>
    """).strip(), unsafe_allow_html=True)

    # Content Grid
    col_grid1, col_grid2 = st.columns([1, 1], gap="large")

    with col_grid1:
        st.markdown('<div class="kb-section-title">Architectural decisions</div>', unsafe_allow_html=True)
        dec_rows = []
        for decision in profile.get("decisions", []):
            conf = decision.get("confidence", "MEDIUM")
            excerpt = decision.get("excerpt", "")
            cite_html = render_citation(decision.get("source", ""), excerpt) if excerpt else ""
            dec_rows.append(textwrap.dedent(f"""
            <tr>
                <td>
                    <div style="font-weight:600; margin-bottom:4px; color:var(--text);">{decision.get('text', '')}</div>
                    {cite_html}
                </td>
                <td style="white-space:nowrap;">{confidence_badge(conf)}</td>
                <td style="font-size:13px; color:var(--text-2); font-family:monospace;">{decision.get('source', '')}</td>
            </tr>
            """).strip())
        dec_table_html = textwrap.dedent(f"""
        <table class="kb-plain-table">
            <thead>
                <tr>
                    <th style="width:55%;">Decision</th>
                    <th style="width:25%;">Confidence</th>
                    <th style="width:20%;">Source</th>
                </tr>
            </thead>
            <tbody>
                {''.join(dec_rows) if dec_rows else '<tr><td colspan="3" style="color:var(--text-2);">No decisions recorded.</td></tr>'}
            </tbody>
        </table>
        """).strip()
        st.markdown(dec_table_html, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<div class="kb-section-title">Key dependencies</div>', unsafe_allow_html=True)
        for dep in profile.get("dependencies", []):
            st.markdown(textwrap.dedent(f"""
            <div class="kb-card">
                <b>{dep.get('item', '')}</b> — {dep.get('description', '')}
                <br/><small style="color:var(--text-2);">Source: {dep.get('source', '')}</small>
            </div>
            """).strip(), unsafe_allow_html=True)

    with col_grid2:
        st.markdown('<div class="kb-section-title">Critical risks</div>', unsafe_allow_html=True)
        risk_rows = []
        for risk in profile.get("risks", []):
            conf = risk.get("confidence", "MEDIUM")
            excerpt = risk.get("excerpt", "")
            cite_html = render_citation(risk.get("source", ""), excerpt) if excerpt else ""
            risk_rows.append(textwrap.dedent(f"""
            <tr>
                <td>
                    <div style="font-weight:600; margin-bottom:4px; color:var(--text);">{risk.get('text', '')}</div>
                    {cite_html}
                </td>
                <td style="white-space:nowrap;">{confidence_badge(conf)}</td>
                <td style="font-size:13px; color:var(--text-2); font-family:monospace;">{risk.get('source', '')}</td>
            </tr>
            """).strip())
        risk_table_html = textwrap.dedent(f"""
        <table class="kb-plain-table">
            <thead>
                <tr>
                    <th style="width:55%;">Risk</th>
                    <th style="width:25%;">Confidence</th>
                    <th style="width:20%;">Source</th>
                </tr>
            </thead>
            <tbody>
                {''.join(risk_rows) if risk_rows else '<tr><td colspan="3" style="color:var(--text-2);">No risks recorded.</td></tr>'}
            </tbody>
        </table>
        """).strip()
        st.markdown(risk_table_html, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<div class="kb-section-title">Unresolved knowledge gaps</div>', unsafe_allow_html=True)
        for q in profile.get("unresolved", []):
            st.markdown(textwrap.dedent(f"""
            <div class="kb-card" style="background:var(--warning-bg); border:1px solid var(--border);">
                <p style="font-weight:600; color:var(--warning); margin-bottom:4px;">{q.get('question', '')}</p>
                <p style="color:var(--text-2); font-size:13px; margin-bottom:0;">
                    <i>Detection note: {q.get('why_unknown', '')}</i>
                </p>
            </div>
            """).strip(), unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<div class="kb-section-title">Stakeholders and key contacts</div>', unsafe_allow_html=True)
        for contact in profile.get("contacts", []):
            st.markdown(textwrap.dedent(f"""
            <div class="kb-card" style="background:var(--surface-2); border:1px solid var(--border);">
                <div style="font-weight:600; color:var(--text);">{contact.get('name', '')}</div>
                <div style="font-size:13px; color:var(--text-2);">{contact.get('role', '')}</div>
                <small style="color:var(--text-2);">Source: {contact.get('source', '')}</small>
            </div>
            """).strip(), unsafe_allow_html=True)

    st.markdown("---")
    col_act1, col_act2 = st.columns([2, 1])
    with col_act1:
        if st.button("Proceed to employee hub", type="primary", use_container_width=True):
            st.session_state.page = "employee"
            st.rerun()
    with col_act2:
        if st.button("Skip to manager review", use_container_width=True):
            st.session_state.page = "review"
            st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 3: EMPLOYEE HUB
# ═══════════════════════════════════════════════════════════════════════════════
elif st.session_state.page == "employee":
    require_page_access("employee")
    step_indicator("employee")

    profile = st.session_state.knowledge_profile
    if not profile:
        st.error("No knowledge profile found. Please start by connecting sources.")
        st.stop()



    employee = st.session_state.employee_name or "Departing Engineer"
    project = st.session_state.project_role or "Key System Contributor"

    st.markdown(textwrap.dedent(f"""
    <div class="kb-panel-hero">
        <h2 style="font-size:1.25rem; font-weight:700; color:var(--text); margin:0 0 4px 0;">Employee knowledge hub</h2>
        <div style="color:var(--text-2); font-size:0.875rem; margin-bottom:0.6rem;">
            <b>Welcome, {employee}.</b> Verify extracted findings, resolve identified documentation gaps, and record unwritten operational context before departure.
        </div>
        <span class="kb-status-dot-item" style="color:var(--text-2);"><span class="kb-dot" style="background-color:var(--accent);"></span>{project}</span>
    </div>
    """).strip(), unsafe_allow_html=True)

    decisions = profile.get("decisions", [])
    risks = profile.get("risks", [])
    unresolved = profile.get("unresolved", [])
    tribal_items = st.session_state.employee_tribal_knowledge

    total_decisions = len(decisions)
    total_risks = len(risks)
    total_verifiable = total_decisions + total_risks
    verified_count = len(st.session_state.employee_verifications)

    gaps_resolved = sum(
        1 for q in unresolved
        if st.session_state.employee_gap_answers.get(q.get("question", ""), "").strip()
    )
    total_gaps = len(unresolved)

    v_pct = (verified_count / total_verifiable) if total_verifiable > 0 else 1.0
    g_pct = (gaps_resolved / total_gaps) if total_gaps > 0 else 1.0
    t_pct = min(1.0, len(tribal_items) / 3.0)
    readiness_score = int((v_pct * 0.4 + g_pct * 0.4 + t_pct * 0.2) * 100)

    st.markdown(textwrap.dedent("""
    <div class="kb-banner-tip">
        <b>Tip for departing engineers:</b> The most invaluable handover knowledge is usually what is unwritten — why a certain design pattern was rejected, vendor rate limits, and who to message during a late-night outage.
    </div>
    """).strip(), unsafe_allow_html=True)

    # Compact Summary Row
    st.markdown(textwrap.dedent(f"""
    <div class="kb-summary-row">
        <div class="kb-summary-item">
            <div class="kb-summary-value">{verified_count}/{total_verifiable}</div>
            <div class="kb-summary-label">Verified items</div>
        </div>
        <div class="kb-summary-divider"></div>
        <div class="kb-summary-item">
            <div class="kb-summary-value">{gaps_resolved}/{total_gaps}</div>
            <div class="kb-summary-label">Gaps resolved</div>
        </div>
        <div class="kb-summary-divider"></div>
        <div class="kb-summary-item">
            <div class="kb-summary-value">{len(tribal_items)}</div>
            <div class="kb-summary-label">Tribal wisdom</div>
        </div>
        <div class="kb-summary-divider"></div>
        <div class="kb-summary-item">
            <div class="kb-summary-value">{readiness_score}%</div>
            <div class="kb-summary-label">Handover readiness</div>
        </div>
    </div>
    """).strip(), unsafe_allow_html=True)

    st.progress(readiness_score / 100.0)
    st.markdown("---")

    emp_tab1, emp_tab2, emp_tab3 = st.tabs([
        "1. Verify findings",
        "2. Answer knowledge gaps",
        "3. Share tribal knowledge"
    ])

    with emp_tab1:
        st.markdown('<div class="kb-section-title">Architectural decisions verification</div>', unsafe_allow_html=True)
        st.caption("Confirm accuracy or add context explaining the trade-offs that led to each decision.")

        for i, decision in enumerate(decisions):
            conf = decision.get("confidence", "MEDIUM")
            stype = decision.get("source_type", "file")
            d_key = f"decision_{i}"
            saved_verif = st.session_state.employee_verifications.get(d_key, {})
            current_status = saved_verif.get("status", "Confirmed accurate")
            current_note = saved_verif.get("note", "")

            with st.expander(f"Decision #{i+1}: {decision.get('text', '')[:75]}...", expanded=(i == 0)):
                st.markdown(textwrap.dedent(f"""
                <div class="kb-card kb-card-info">
                    <p style="font-size:0.95rem; font-weight:600; color:var(--text); margin-bottom:0.4rem;">{decision.get('text', '')}</p>
                    <p>{source_badge(stype)} {confidence_badge(conf)} &nbsp;<span style="color:var(--text-2); font-size:0.8rem;">Source: {decision.get('source', '')}</span></p>
                </div>
                """).strip(), unsafe_allow_html=True)
                excerpt = decision.get("excerpt", "")
                if excerpt:
                    st.markdown(render_citation(decision.get("source", ""), excerpt), unsafe_allow_html=True)

                col_stat, col_note = st.columns([1, 2])
                with col_stat:
                    status_choice = st.radio(
                        "Your assessment:",
                        ["Confirmed accurate", "Needs context", "Inaccurate or outdated"],
                        index=["Confirmed accurate", "Needs context", "Inaccurate or outdated"].index(current_status) if current_status in ["Confirmed accurate", "Needs context", "Inaccurate or outdated"] else 0,
                        key=f"status_dec_{i}"
                    )
                with col_note:
                    note_input = st.text_area(
                        "Additional context or trade-offs:",
                        value=current_note,
                        key=f"note_dec_{i}",
                        height=90,
                        placeholder="Explain technical trade-offs, constraints, or warnings for your successor..."
                    )

                st.session_state.employee_verifications[d_key] = {
                    "status": status_choice,
                    "note": note_input,
                    "title": decision.get("text", "")
                }

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<div class="kb-section-title">Critical risks verification</div>', unsafe_allow_html=True)
        st.caption("Confirm known risks and specify concrete mitigation steps.")

        for j, risk in enumerate(risks):
            conf = risk.get("confidence", "MEDIUM")
            r_key = f"risk_{j}"
            saved_r_verif = st.session_state.employee_verifications.get(r_key, {})
            current_r_status = saved_r_verif.get("status", "Active risk")
            current_r_note = saved_r_verif.get("note", "")

            with st.expander(f"Risk #{j+1}: {risk.get('text', '')[:75]}...", expanded=(j == 0)):
                card_class = "kb-card-danger" if conf == "HIGH" else "kb-card-warning"
                st.markdown(textwrap.dedent(f"""
                <div class="kb-card {card_class}">
                    <p style="font-size:0.95rem; font-weight:600; color:var(--text); margin-bottom:0.4rem;">{risk.get('text', '')}</p>
                    <p>{confidence_badge(conf)} &nbsp;<span style="color:var(--text-2); font-size:0.8rem;">Source: {risk.get('source', '')}</span></p>
                </div>
                """).strip(), unsafe_allow_html=True)
                excerpt = risk.get("excerpt", "")
                if excerpt:
                    st.markdown(render_citation(risk.get("source", ""), excerpt), unsafe_allow_html=True)

                col_r_stat, col_r_note = st.columns([1, 2])
                with col_r_stat:
                    r_status_choice = st.radio(
                        "Severity and status:",
                        ["Active risk", "Mitigated or low priority", "False alarm or resolved"],
                        index=["Active risk", "Mitigated or low priority", "False alarm or resolved"].index(current_r_status) if current_r_status in ["Active risk", "Mitigated or low priority", "False alarm or resolved"] else 0,
                        key=f"status_risk_{j}"
                    )
                with col_r_note:
                    r_note_input = st.text_area(
                        "Mitigation guidance or next steps:",
                        value=current_r_note,
                        key=f"note_risk_{j}",
                        height=90,
                        placeholder="Provide runbook instructions, contact points, or timeline constraints..."
                    )

                st.session_state.employee_verifications[r_key] = {
                    "status": r_status_choice,
                    "note": r_note_input,
                    "title": risk.get("text", "")
                }

    with emp_tab2:
        st.markdown('<div class="kb-section-title">Resolve knowledge gaps</div>', unsafe_allow_html=True)
        st.info("Tacit knowledge opportunity: Unanswered questions discovered across codebase and documents. Add the unwritten context before leaving.")

        if unresolved:
            for k, q in enumerate(unresolved):
                q_text = q.get("question", "")
                why = q.get("why_unknown", "")
                existing_ans = st.session_state.employee_gap_answers.get(q_text, "")

                st.markdown(textwrap.dedent(f"""
                <div class="kb-card kb-card-warning">
                    <p style="font-size:0.95rem; font-weight:600; color:var(--warning); margin-bottom:4px;">Question #{k+1}: {q_text}</p>
                    <p style="color:var(--text-2); font-size:0.82rem; margin-bottom:0;"><i>Detection rationale: {why}</i></p>
                </div>
                """).strip(), unsafe_allow_html=True)

                ans_input = st.text_area(
                    f"Your resolution for Question #{k+1}:",
                    value=existing_ans,
                    key=f"gap_response_{k}",
                    height=100,
                    placeholder="Provide the unwritten answer, internal discussions, or current standard operating procedure..."
                )
                st.session_state.employee_gap_answers[q_text] = ans_input

                if ans_input.strip():
                    st.success("Resolved and added to handover package")
                else:
                    st.caption("Awaiting employee response")
                st.markdown("<br>", unsafe_allow_html=True)
        else:
            st.success("No unresolved knowledge gaps identified in this repository.")

    with emp_tab3:
        st.markdown('<div class="kb-section-title">Share tribal knowledge and operational notes</div>', unsafe_allow_html=True)
        st.markdown("Record informal wisdom that is not documented anywhere: deployment constraints, vendor quirks, debugging shortcuts, and unwritten team practices.")

        with st.form("add_tribal_knowledge_form", clear_on_submit=True):
            col_t1, col_t2 = st.columns([1, 2])
            with col_t1:
                category = st.selectbox(
                    "Category",
                    ["Warning", "Tip", "Process", "History", "Contact"]
                )
            with col_t2:
                t_title = st.text_input("Title or topic", placeholder="e.g. Stripe webhook secret rotation trap")

            t_content = st.text_area(
                "Guidance and context details",
                placeholder="Explain what happened, why it matters, and how your successor can avoid pitfalls...",
                height=105
            )

            submit_tribal = st.form_submit_button("Add tribal knowledge item", use_container_width=True)
            if submit_tribal:
                if t_title.strip() and t_content.strip():
                    new_item = {
                        "category": category,
                        "title": t_title.strip(),
                        "content": t_content.strip()
                    }
                    def _add_tk(d):
                        d.setdefault("employee_tribal_knowledge", []).append(new_item)
                    modify_project_state(_add_tk, session_state=st.session_state)
                    record_write(st.session_state, "tribal")
                    st.toast(f"Added: {t_title.strip()}")
                    st.rerun()
                else:
                    st.error("Please provide both a title and description.")

        if st.session_state.employee_tribal_knowledge:
            st.markdown("#### Recorded tribal knowledge items:")
            for idx, item in enumerate(st.session_state.employee_tribal_knowledge):
                cat = item.get("category", "Tip")
                card_class = "kb-card-danger" if cat == "Warning" else ("kb-card-success" if cat == "Contact" else "kb-card")

                c_item, c_del = st.columns([6, 1])
                with c_item:
                    st.markdown(textwrap.dedent(f"""
                    <div class="kb-card {card_class}">
                        <div style="font-weight:600; color:var(--text);">[{cat}] {item.get('title', '')}</div>
                        <p style="font-size:0.875rem; color:var(--text-2); margin-top:4px; margin-bottom:0;">{item.get('content', '')}</p>
                    </div>
                    """).strip(), unsafe_allow_html=True)
                with c_del:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("Remove", key=f"del_tk_{idx}"):
                        def _del_tk(d):
                            tk_list = d.get("employee_tribal_knowledge", [])
                            if 0 <= idx < len(tk_list):
                                tk_list.pop(idx)
                        modify_project_state(_del_tk, session_state=st.session_state)
                        record_write(st.session_state, "tribal")
                        st.rerun()

    st.markdown("---")
    col_nav1, col_nav2 = st.columns([2, 1])
    with col_nav1:
        if st.button("Proceed to manager review", type="primary", use_container_width=True):
            mgr_id = get_manager_id(st.session_state)
            emp_name = st.session_state.get("auth_name", "Employee")
            add_notification(st.session_state, mgr_id, "submit_review", f"{emp_name} submitted the handover for review.")
            st.session_state.page = "review"
            st.rerun()
    with col_nav2:
        if st.button("Back to reconstruct", use_container_width=True):
            st.session_state.page = "reconstruct"
            st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 4: MANAGER REVIEW & APPROVALS
# ═══════════════════════════════════════════════════════════════════════════════
elif st.session_state.page == "review":
    require_page_access("review")
    step_indicator("review")

    profile = st.session_state.knowledge_profile
    if not profile:
        st.error("No knowledge profile found. Please start by connecting sources.")
        st.stop()



    # Manager status line
    _mgr_profile = st.session_state.knowledge_profile
    if not _mgr_profile:
        _mgr_status = "Waiting for employee to upload sources"
        _mgr_dot_cls = "kb-dot-muted"
    else:
        _mgr_approved_count = sum(1 for v in st.session_state.approvals.values() if v is True)
        if _mgr_approved_count < 5:
            _mgr_status = f"Ready for manager review ({_mgr_approved_count}/5 approved)"
            _mgr_dot_cls = "kb-dot-warning"
        else:
            _mgr_status = "Ready for manager review (All approved)"
            _mgr_dot_cls = "kb-dot-success"

    st.markdown(textwrap.dedent(f"""
        <div style="background:var(--subtle);border:1px solid var(--border);border-radius:6px;padding:8px 14px;margin-bottom:14px;display:flex;align-items:center;gap:8px;">
          <span class="kb-dot {_mgr_dot_cls}" style="width:8px;height:8px;border-radius:50%;display:inline-block;"></span>
          <span style="font-size:13px;color:var(--text);font-weight:500;">Status: <b>{_mgr_status}</b></span>
        </div>
    """).strip(), unsafe_allow_html=True)

    st.markdown(textwrap.dedent("""
        <div class="kb-panel-hero">
          <h2 style="font-size:16px;font-weight:600;color:var(--text);margin:0 0 4px 0;">Manager review</h2>
          <div style="color:var(--text-2);font-size:13px;">
            Inspect verified findings, employee gap resolutions, and tribal knowledge. Add notes, then approve each section.
          </div>
        </div>
    """).strip(), unsafe_allow_html=True)

    sections = [
        ("decisions", "Decision log", profile.get("decisions", [])),
        ("risks", "Risks and dependencies", profile.get("risks", [])),
        ("unresolved", "Resolved and open questions", profile.get("unresolved", [])),
        ("tribal", "Tribal knowledge and constraints", st.session_state.employee_tribal_knowledge),
        ("contacts", "Key contacts and ownership", profile.get("contacts", [])),
    ]

    all_approved = True

    for section_id, section_title, section_data in sections:
        st.markdown(f'<div class="kb-section-title">{section_title}</div>', unsafe_allow_html=True)

        with st.container():
            if section_id == "decisions":
                for idx, item in enumerate(section_data):
                    verif = st.session_state.employee_verifications.get(f"decision_{idx}")
                    verif_badge = ""
                    if verif:
                        verif_badge = f" — <i>Employee: {verif.get('status', 'Confirmed accurate')}</i>"
                        if verif.get("note"):
                            verif_badge += f" (Note: \"{verif.get('note')}\")"
                    st.markdown(f"- **{item.get('text', '')[:100]}** _{source_badge(item.get('source_type','file'))} {confidence_badge(item.get('confidence','MEDIUM'))}_{verif_badge}",
                               unsafe_allow_html=True)
            elif section_id == "risks":
                for idx, item in enumerate(section_data):
                    verif = st.session_state.employee_verifications.get(f"risk_{idx}")
                    verif_badge = ""
                    if verif:
                        verif_badge = f" — <i>Employee: {verif.get('status', 'Active risk')}</i>"
                        if verif.get("note"):
                            verif_badge += f" (Note: \"{verif.get('note')}\")"
                    st.markdown(f"- **{item.get('text', '')[:100]}** _{confidence_badge(item.get('confidence','MEDIUM'))}_{verif_badge}",
                               unsafe_allow_html=True)
            elif section_id == "unresolved":
                for item in section_data:
                    q_text = item.get('question', '')
                    emp_ans = st.session_state.employee_gap_answers.get(q_text, "")
                    if emp_ans:
                        st.markdown(f"- **{q_text}**<br>&nbsp;&nbsp;&nbsp;&nbsp;<b>Employee Context:</b> <i>{emp_ans}</i>", unsafe_allow_html=True)
                    else:
                        st.markdown(f"- **{q_text}** <i>(Unresolved — awaiting response)</i>")
            elif section_id == "tribal":
                if section_data:
                    for item in section_data:
                        st.markdown(f"- **[{item.get('category', 'Tip')}] {item.get('title', '')}**: {item.get('content', '')}")
                else:
                    st.markdown("_- No tribal knowledge items recorded._")
            elif section_id == "contacts":
                for item in section_data:
                    st.markdown(f"- **{item.get('name', '')}** — {item.get('role', '')}")

        col_rev1, col_rev2 = st.columns([2, 1])
        with col_rev1:
            corrections = st.text_area(
                f"Manager notes and action assignments for {section_title}:",
                value=st.session_state.corrections.get(section_id, ""),
                key=f"correction_{section_id}",
                placeholder="Assign owner, link Jira ticket, or add sign-off caveats...",
                height=85
            )
            st.session_state.corrections[section_id] = corrections

        with col_rev2:
            st.markdown("<br>", unsafe_allow_html=True)
            current_status = st.session_state.approvals.get(section_id, None)

            btn_app_col, btn_rej_col = st.columns(2)
            with btn_app_col:
                if st.button("Approve section", key=f"btn_app_{section_id}", use_container_width=True):
                    def _app_sec(d):
                        d.setdefault("approvals", {})[section_id] = True
                    modify_project_state(_app_sec, session_state=st.session_state)
                    log_audit_entry(st.session_state, st.session_state.get("auth_username","manager"), f"Approved section: {section_title}")
                    st.rerun()

            with btn_rej_col:
                if st.button("Reject section", key=f"btn_rej_{section_id}", use_container_width=True):
                    rej_text = st.session_state.get(f"rej_reason_{section_id}", "").strip() or "Rejected by manager"
                    def _rej_sec(d):
                        d.setdefault("approvals", {})[section_id] = "rejected"
                    modify_project_state(_rej_sec, session_state=st.session_state)
                    log_audit_entry(st.session_state, st.session_state.get("auth_username","manager"), f"Rejected section: {section_title}", reason=rej_text)
                    emp_id = get_employee_id(st.session_state)
                    if "confidential" in section_title.lower() or "confidential" in section_id.lower():
                        rej_notif = "The manager rejected a confidential section."
                    else:
                        rej_notif = f"The manager rejected the section {section_title}. See the comment on Employee hub."
                    add_notification(st.session_state, emp_id, "section_rejected", rej_notif)
                    st.rerun()

            st.text_input(
                f"Rejection reason for {section_title}:",
                key=f"rej_reason_{section_id}",
                placeholder="Reason if rejecting...",
                label_visibility="collapsed"
            )

            if current_status is True:
                st.success("Section approved")
            elif current_status == "rejected":
                st.error("Section rejected")
                all_approved = False
            else:
                st.warning("Pending approval")
                all_approved = False

        st.markdown("---")

    with st.expander("Audit history log", expanded=False):
        if st.session_state.action_history:
            rows = []
            for entry in reversed(st.session_state.action_history):
                ts = entry.get('timestamp', '')
                who = entry.get('who', '')
                action = entry.get('action', '')
                reason = entry.get('reason', '')
                color = "var(--success)" if "Approved" in action else "var(--error)"
                rows.append(f"<tr><td>{ts}</td><td>{who}</td><td style='color:{color}; font-weight:600;'>{action}</td><td>{reason}</td></tr>")
            audit_table = textwrap.dedent(f"""
            <table class="kb-plain-table">
                <thead>
                    <tr>
                        <th style="width:160px;">Timestamp</th>
                        <th style="width:100px;">User</th>
                        <th style="width:180px;">Action</th>
                        <th>Notes / Reason</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(rows)}
                </tbody>
            </table>
            """).strip()
            st.markdown(audit_table, unsafe_allow_html=True)
        else:
            st.caption("No review actions recorded yet.")

    approved_count = sum(1 for v in st.session_state.approvals.values() if v is True)
    total_sections = len(sections)

    st.markdown(textwrap.dedent(f"""
    <div class="kb-approval-progress">
        <span class="kb-approval-progress-label">Approval progress</span>
        <span class="kb-approval-progress-count">{approved_count} / {total_sections}</span>
    </div>
    """).strip(), unsafe_allow_html=True)
    progress = approved_count / total_sections if total_sections > 0 else 0
    st.progress(progress)

    if all_approved:
        st.success("All sections approved. Handover package generation is available.")
    else:
        remaining = total_sections - approved_count
        st.info(f"{remaining} section(s) still require review and approval.")

    st.markdown("---")
    btn_disabled = not all_approved

    col_gen1, col_gen2 = st.columns([2, 1])
    with col_gen1:
        if st.button(
            "Generate handover package",
            type="primary",
            use_container_width=True,
            disabled=btn_disabled,
        ):
            if st.session_state.handovers_run >= 3:
                st.warning("Session limit reached. Please refresh the page to start a new session.")
            else:
                st.session_state.handovers_run += 1
                reviewed_profile = copy.deepcopy(profile)

                filtered_decisions = []
                for idx, decision in enumerate(profile.get("decisions", [])):
                    verif = st.session_state.employee_verifications.get(
                        f"decision_{idx}", {}
                    )
                    status = verif.get("status", "")
                    if status == "Inaccurate or outdated":
                        continue
                    item = copy.deepcopy(decision)
                    if status == "Needs context" and verif.get("note"):
                        item["text"] = item["text"] + f" [Employee note: {verif['note']}]"
                    filtered_decisions.append(item)
                reviewed_profile["decisions"] = filtered_decisions

                filtered_risks = []
                for idx, risk in enumerate(profile.get("risks", [])):
                    verif = st.session_state.employee_verifications.get(
                        f"risk_{idx}", {}
                    )
                    status = verif.get("status", "")
                    if status == "False alarm or resolved":
                        continue
                    item = copy.deepcopy(risk)
                    if status == "Mitigated or low priority":
                        suffix = " [Employee: mitigated / low priority]"
                        if verif.get("note"):
                            suffix += f" [Employee note: {verif['note']}]"
                        item["text"] = item["text"] + suffix
                    elif status == "Active risk" and verif.get("note"):
                        item["text"] = item["text"] + f" [Employee note: {verif['note']}]"
                    filtered_risks.append(item)
                reviewed_profile["risks"] = filtered_risks

                reviewed_profile["manager_notes"] = dict(st.session_state.corrections)

                with st.spinner("Generating manager handover with Gemini..."):
                    try:
                        from utils.gemini_engine import generate_manager_handover
                        mgr = generate_manager_handover(
                            reviewed_profile,
                            st.session_state.employee_name,
                            st.session_state.project_role,
                            st.session_state.api_key
                        )
                        st.session_state.manager_handover = mgr
                    except Exception as e:
                        st.error(f"Manager handover generation failed: {_safe_err(e)}")
                        st.stop()

                with st.spinner("Generating technical successor handover with Gemini..."):
                    try:
                        from utils.gemini_engine import generate_newhire_handover
                        nh = generate_newhire_handover(
                            reviewed_profile,
                            st.session_state.employee_name,
                            st.session_state.project_role,
                            st.session_state.api_key
                        )
                        st.session_state.newhire_handover = nh
                    except Exception as e:
                        st.error(f"Technical successor handover generation failed: {_safe_err(e)}")
                        st.stop()

                with st.spinner("Generating employee notes with Gemini..."):
                    try:
                        from utils.gemini_engine import generate_employee_handover
                        emp_doc = generate_employee_handover(
                            profile,
                            st.session_state.employee_name,
                            st.session_state.project_role,
                            st.session_state.employee_verifications,
                            st.session_state.employee_gap_answers,
                            st.session_state.employee_tribal_knowledge,
                            st.session_state.api_key
                        )
                        st.session_state.employee_handover = emp_doc
                    except Exception as e:
                        st.warning(f"Employee handover note: {_safe_err(e)}")
                        st.session_state.employee_handover = ""

                    def _save_pkg(d):
                        d["manager_handover"] = st.session_state.manager_handover
                        d["newhire_handover"] = st.session_state.newhire_handover
                        d["employee_handover"] = st.session_state.employee_handover
                        d["handovers_run"] = st.session_state.handovers_run
                    modify_project_state(_save_pkg, session_state=st.session_state)
                    log_audit_entry(st.session_state, st.session_state.get("auth_username","manager"), "Handover package generated")
                    emp_id = get_employee_id(st.session_state)
                    succ_id = get_successor_id(st.session_state)
                    add_notification(st.session_state, emp_id, "package_generated", "The handover package is ready.")
                    add_notification(st.session_state, succ_id, "package_generated", "The handover package is ready.")
                    st.session_state.page = "handover"
                    st.rerun()

    with col_gen2:
        if st.button("Back to employee hub", use_container_width=True):
            st.session_state.page = "employee"
            st.rerun()

    if btn_disabled:
        st.caption("Sign off on all sections above to generate the handover package.")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 5: FINAL HANDOVER PACKAGE
# ═══════════════════════════════════════════════════════════════════════════════
elif st.session_state.page == "handover":
    require_page_access("handover")
    step_indicator("handover")

    if not st.session_state.manager_handover or not st.session_state.newhire_handover:
        st.error("Handover documents not yet generated. Please complete Review first.")
        if st.button("Back to manager review"):
            st.session_state.page = "review"
            st.rerun()
        st.stop()



    employee = st.session_state.employee_name or "Departing Engineer"
    project = st.session_state.project_role or "Key System Contributor"
    initials = "".join([part[0] for part in employee.split() if part])[:2].upper() if employee else "HB"

    header_html = textwrap.dedent(f"""
    <div class="kb-panel-hero">
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:0.5rem;">
            <div style="display:flex; align-items:center; gap:10px;">
                <span class="kb-avatar-chip" style="width:28px; height:28px; font-size:0.78rem;">{initials}</span>
                <div>
                    <h2 style="font-size:1.25rem; font-weight:700; color:var(--text); margin:0 0 2px 0;">Handover package finalized</h2>
                    <div style="font-size:0.875rem; color:var(--text-2);">
                        All sections reviewed, enriched with employee context, and approved by management.
                    </div>
                </div>
            </div>
            <span class="kb-status-dot-item" style="color:var(--success); font-weight:600;"><span class="kb-dot" style="background-color:var(--success);"></span>Audited and approved</span>
        </div>
        <div style="margin-top:0.85rem; font-size:0.85rem; color:var(--text-2);">
            <b>Knowledge holder:</b> {employee} &nbsp;|&nbsp; <b>Scope:</b> {project}
        </div>
    </div>
    """)
    st.markdown(header_html, unsafe_allow_html=True)

    _auth_role = st.session_state.get("auth_role", "Manager")
    if _auth_role == "Manager":
        selected_role = "Manager"
    elif _auth_role == "Employee":
        selected_role = "Employee"
    else:
        selected_role = "Technical Successor"

    st.markdown(
        f'<div style="font-size:13px; color:var(--text-2); margin-bottom:12px;"><span class="kb-dot" style="background-color:var(--accent);"></span> Viewing as: <b>{selected_role}</b> ({_auth_role} account)</div>',
        unsafe_allow_html=True
    )

    st.markdown("---")

    # ── Role 1: Manager View ──────────────────────────────────────────────────
    if selected_role == "Manager":
        st.markdown('<div class="kb-section-title" style="font-size:1.1rem; margin-bottom:0.4rem;">Manager handover document</div>', unsafe_allow_html=True)
        st.caption("Executive risk summary, business impact, vendor expiration timeline, and required management actions.")
        st.markdown("---")
        raw_manager = st.session_state.manager_handover or ""
        redacted_manager = redact_sensitive_info(raw_manager)
        st.markdown(redacted_manager)
        st.markdown("---")

        st.download_button(
            label="Download manager handover (Markdown)",
            data=redacted_manager,
            file_name=f"handover_manager_{employee.replace(' ', '_')}.md",
            mime="text/markdown",
            use_container_width=True,
        )

    # ── Role 2: Technical Successor View ──────────────────────────────────────
    elif selected_role == "Technical Successor":
        st.markdown('<div class="kb-section-title" style="font-size:1.1rem; margin-bottom:0.4rem;">Technical successor handover</div>', unsafe_allow_html=True)
        st.caption("Deep architectural rationale, known landmines, critical paths, and local setup checklist.")
        st.markdown("---")
        raw_successor = st.session_state.newhire_handover or ""
        redacted_successor = redact_sensitive_info(raw_successor)
        st.markdown(redacted_successor)
        st.markdown("---")

        st.markdown('<div class="kb-section-title">Successor receipt acknowledgment</div>', unsafe_allow_html=True)
        if st.session_state.acknowledgement:
            ack_info = st.session_state.acknowledgement
            st.markdown(
                render_receipt_card(
                    name=ack_info["name"],
                    timestamp=ack_info["time"],
                    project=project,
                    employee=employee,
                ),
                unsafe_allow_html=True
            )
        else:
            st.caption("Sign the receipt below to confirm you have read and understood this handover document.")
            ack_c1, ack_c2 = st.columns([2, 1])
            with ack_c1:
                succ_name_input = st.text_input(
                    "Your full name:",
                    placeholder="Enter your name to acknowledge receipt...",
                    key="succ_name_ack"
                )
            with ack_c2:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("Acknowledge receipt", key="btn_ack_receipt", use_container_width=True):
                    confirmed_name = succ_name_input.strip() or "Successor"
                    ack_val = {
                        "name": confirmed_name,
                        "time": time.strftime("%Y-%m-%d %H:%M:%S")
                    }
                    def _ack(d):
                        d["acknowledgement"] = ack_val
                    modify_project_state(_ack, session_state=st.session_state)
                    log_audit_entry(st.session_state, st.session_state.get("auth_username","successor"), f"Handover acknowledged by {confirmed_name}")
                    st.rerun()

        st.markdown("---")
        st.download_button(
            label="Download successor handover (Markdown)",
            data=redacted_successor,
            file_name=f"handover_successor_{employee.replace(' ', '_')}.md",
            mime="text/markdown",
            use_container_width=True,
        )

    # ── Role 3: Employee Notes View ───────────────────────────────────────────
    elif selected_role == "Employee":
        st.markdown('<div class="kb-section-title" style="font-size:1.1rem; margin-bottom:0.4rem;">Employee notes and tribal knowledge</div>', unsafe_allow_html=True)
        st.caption("First-person context, verified architectural decisions, resolved blind spots, and unwritten operational tips.")
        st.markdown("---")
        raw_employee = st.session_state.employee_handover or ""
        redacted_employee = redact_sensitive_info(raw_employee)
        st.markdown(redacted_employee)
        st.markdown("---")

        st.download_button(
            label="Download employee notes (Markdown)",
            data=redacted_employee,
            file_name=f"handover_employee_{employee.replace(' ', '_')}.md",
            mime="text/markdown",
            use_container_width=True,
        )

    st.markdown("---")
    col_reset1, col_reset2 = st.columns(2)
    with col_reset1:
        if st.button("Start new handover", use_container_width=True):
            _empty = get_empty_state()
            def _reset(d):
                for k, v in _empty.items():
                    d[k] = v
            modify_project_state(_reset, session_state=st.session_state)
            st.session_state.page = "connect"
            st.rerun()

    with col_reset2:
        if st.button("Back to manager review", use_container_width=True):
            st.session_state.page = "review"
            st.rerun()

# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 6: EMPLOYEE NOTES (Employee role only)
# ═══════════════════════════════════════════════════════════════════════════════
elif st.session_state.page == "employee_notes":
    require_page_access("employee_notes")
    step_indicator("employee_notes")
    render_role_status_line("Employee")

    employee = st.session_state.auth_name or "Departing Engineer"
    project = st.session_state.project_role or "Key System Contributor"

    st.markdown(textwrap.dedent(f"""
    <div class="kb-panel-hero">
        <h2 style="font-size:1.25rem; font-weight:700; color:var(--text); margin:0 0 4px 0;">My employee notes</h2>
        <div style="color:var(--text-2); font-size:0.875rem;">
            Your first-person handover document, generated from your verified findings and tribal knowledge.
        </div>
    </div>
    """).strip(), unsafe_allow_html=True)

    raw_emp = st.session_state.employee_handover
    if not raw_emp:
        st.info("Your employee notes document will appear here after the manager generates the handover package.")
        st.stop()

    redacted_emp = redact_sensitive_info(raw_emp)
    st.markdown(redacted_emp)
    st.markdown("---")
    st.download_button(
        label="Download my employee notes (Markdown)",
        data=redacted_emp,
        file_name=f"employee_notes_{employee.replace(' ', '_')}.md",
        mime="text/markdown",
        use_container_width=True,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 7: SUCCESSOR HANDOVER (Successor role only)
# ═══════════════════════════════════════════════════════════════════════════════
elif st.session_state.page == "successor_handover":
    require_page_access("successor_handover")
    step_indicator("successor_handover")
    render_role_status_line("Successor")

    approvals = st.session_state.get("approvals", {})
    all_approved = sum(1 for v in approvals.values() if v is True) >= 5
    has_handover = bool(st.session_state.get("manager_handover") and st.session_state.get("newhire_handover"))

    if not has_handover or not all_approved:
        st.markdown(textwrap.dedent("""
        <div class="kb-panel-hero">
            <h2 style="font-size:1.25rem; font-weight:700; color:var(--text); margin:0 0 4px 0;">Technical handover</h2>
            <div style="color:var(--text-2); font-size:0.875rem;">
                Your handover document will appear here once the manager has approved all sections and generated the package.
            </div>
        </div>
        """).strip(), unsafe_allow_html=True)
        st.warning("Handover not approved yet. Check back after the manager completes the review.")
        st.stop()

    employee = st.session_state.employee_name or "Departing Engineer"
    project = st.session_state.project_role or "Key System Contributor"

    st.markdown(textwrap.dedent(f"""
    <div class="kb-panel-hero">
        <h2 style="font-size:1.25rem; font-weight:700; color:var(--text); margin:0 0 4px 0;">Technical handover — {project}</h2>
        <div style="color:var(--text-2); font-size:0.875rem;">
            Deep architectural rationale, known risks, critical paths, and operational guidance from {employee}.
        </div>
    </div>
    """).strip(), unsafe_allow_html=True)

    raw_successor = st.session_state.newhire_handover or ""
    redacted_successor = redact_sensitive_info(raw_successor)
    st.markdown(redacted_successor)
    st.markdown("---")

    st.markdown('<div class="kb-section-title">Acknowledge receipt</div>', unsafe_allow_html=True)
    if st.session_state.acknowledgement:
        ack_info = st.session_state.acknowledgement
        st.markdown(
            render_receipt_card(
                name=ack_info["name"],
                timestamp=ack_info["time"],
                project=project,
                employee=employee,
            ),
            unsafe_allow_html=True
        )
    else:
        st.caption("Sign below to confirm you have read and understood this handover document.")
        ack_c1, ack_c2 = st.columns([2, 1])
        with ack_c1:
            succ_name_input = st.text_input(
                "Your full name:",
                placeholder="Enter your name to acknowledge receipt...",
                key="succ_name_ack_suc"
            )
        with ack_c2:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Acknowledge receipt", key="btn_ack_receipt_suc", use_container_width=True):
                confirmed_name = succ_name_input.strip() or st.session_state.get("auth_name", "Successor")
                ack_val = {
                    "name": confirmed_name,
                    "time": time.strftime("%Y-%m-%d %H:%M:%S")
                }
                def _ack(d):
                    d["acknowledgement"] = ack_val
                modify_project_state(_ack, session_state=st.session_state)
                log_audit_entry(st.session_state, st.session_state.get("auth_username","successor"), f"Handover acknowledged by {confirmed_name}")
                st.rerun()

    st.markdown("---")
    st.download_button(
        label="Download technical handover (Markdown)",
        data=redacted_successor,
        file_name=f"handover_successor_{employee.replace(' ', '_')}.md",
        mime="text/markdown",
        use_container_width=True,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 8: AUDIT LOG (Manager only)
# ═══════════════════════════════════════════════════════════════════════════════
elif st.session_state.page == "audit":
    require_page_access("audit")
    step_indicator("audit")

    st.markdown(textwrap.dedent("""
    <div class="kb-panel-hero">
        <h2 style="font-size:1.25rem; font-weight:700; color:var(--text); margin:0 0 4px 0;">Audit log</h2>
        <div style="color:var(--text-2); font-size:0.875rem;">
            Complete record of logins, page views, approvals, rejections, handover generation, and acknowledgements.
        </div>
    </div>
    """).strip(), unsafe_allow_html=True)

    history = st.session_state.get("action_history", [])
    if not history:
        st.info("No audit events recorded yet.")
    else:
        rows_html = ""
        for entry in reversed(history):
            ts = entry.get("timestamp", "")
            who = entry.get("who", "")
            action = entry.get("action", "")
            reason = entry.get("reason", "")
            if "Approved" in action:
                color = "var(--success)"
            elif "Rejected" in action or "Failed" in action:
                color = "var(--error)"
            elif "Logged out" in action:
                color = "var(--warning)"
            else:
                color = "var(--text)"
            rows_html += f"<tr><td style='color:var(--text-2);font-family:monospace;font-size:12px;'>{ts}</td><td style='font-weight:600;'>{who}</td><td style='color:{color};font-weight:500;'>{action}</td><td style='color:var(--text-2);font-size:13px;'>{reason}</td></tr>"

        st.markdown(textwrap.dedent(f"""
        <table class="kb-plain-table">
            <thead>
                <tr>
                    <th style="width:160px;">Timestamp</th>
                    <th style="width:120px;">User</th>
                    <th style="width:220px;">Action</th>
                    <th>Details / Reason</th>
                </tr>
            </thead>
            <tbody>
                {rows_html}
            </tbody>
        </table>
        """).strip(), unsafe_allow_html=True)

        # CSV download
        csv_buf = io.StringIO()
        writer = csv.DictWriter(csv_buf, fieldnames=["timestamp","who","action","reason"])
        writer.writeheader()
        for entry in reversed(history):
            writer.writerow({
                "timestamp": entry.get("timestamp",""),
                "who": entry.get("who",""),
                "action": entry.get("action",""),
                "reason": entry.get("reason",""),
            })
        st.download_button(
            label="Download audit log (CSV)",
            data=csv_buf.getvalue(),
            file_name="baton_audit_log.csv",
            mime="text/csv",
            use_container_width=False,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 9: MY ACCESS
# ═══════════════════════════════════════════════════════════════════════════════
elif st.session_state.page == "my_access":
    require_page_access("my_access")
    st.header("My access")

    cur_user = {
        "id": st.session_state.get("auth_username", ""),
        "username": st.session_state.get("auth_username", ""),
        "name": st.session_state.get("auth_name", ""),
        "role": st.session_state.get("auth_role", ""),
    }
    eff = get_effective_access(cur_user, st.session_state)
    st.table([{
        "Name": eff["name"],
        "Role": eff["role"],
        "Project content": eff["project_content"],
        "Confidential files": eff["confidential_files"],
    }])

    st.subheader("Request access")
    cur_grants = get_member_grants(st.session_state, cur_user["id"])
    if cur_user["role"] == "Employee":
        candidates = ["confidential_read", "confidential_write"]
    else:
        candidates = ["normal_write", "confidential_read", "confidential_write"]

    available = [c for c in candidates if c not in cur_grants]
    if "confidential_write" in cur_grants:
        available = [c for c in available if c != "confidential_read"]

    if available:
        req_type_choice = st.selectbox(
            "Access type",
            options=available,
            format_func=lambda x: REQUEST_LABELS.get(x, x),
            key="my_access_req_type"
        )
        my_reqs = [
            r for r in st.session_state.get("access_requests", [])
            if r.get("requester_id") == cur_user["id"]
        ]
        has_pending = any(
            r.get("type") == req_type_choice and r.get("status") == "pending"
            for r in my_reqs
        )
        if has_pending:
            st.info("You already have a pending request for this.")
        else:
            reason = st.text_area("Reason (optional)", key="my_access_reason")
            if st.button("Send request", type="primary", key="btn_send_req"):
                create_request(st.session_state, cur_user, req_type_choice, reason)
                st.rerun()
    else:
        st.info("You hold all available permissions.")

    st.subheader("My requests")
    my_reqs = [
        r for r in st.session_state.get("access_requests", [])
        if r.get("requester_id") == cur_user["id"]
    ]
    if my_reqs:
        req_table = []
        for r in reversed(my_reqs):
            req_table.append({
                "Requested": REQUEST_LABELS.get(r.get("type"), r.get("type")),
                "Reason": r.get("reason") or "none given",
                "Submitted": r.get("created_at", ""),
                "Status": (r.get("status") or "pending").capitalize(),
                "Manager comment": r.get("decision_comment") or "—",
            })
        st.table(req_table)
    else:
        st.caption("No requests submitted yet.")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 10: ACCESS MANAGEMENT (Manager only)
# ═══════════════════════════════════════════════════════════════════════════════
elif st.session_state.page == "access_management":
    require_page_access("access_management")
    st.header("Access management")

    # a. Pending requests
    st.subheader("Pending requests")
    pending = [r for r in st.session_state.get("access_requests", []) if r.get("status") == "pending"]
    if not pending:
        st.caption("No pending requests.")
    else:
        for req in pending:
            with st.container(border=True):
                r_id = req["id"]
                r_name = req.get("requester_name", req.get("requester_id"))
                r_role = get_role_label(req.get("requester_role", ""))
                r_type = REQUEST_LABELS.get(req.get("type"), req.get("type"))
                r_reason = req.get("reason") or "none given"
                r_date = req.get("created_at", "")
                st.markdown(f"**{r_name}** ({r_role}) &mdash; {r_type}")
                st.caption(f"Submitted: {r_date} | Reason: {r_reason}")
                comment = st.text_input("Comment (optional)", key=f"req_comment_{r_id}")
                col_app, col_deny, _ = st.columns([1, 1, 4])
                with col_app:
                    if st.button("Approve", key=f"btn_app_{r_id}", type="primary"):
                        mgr = {
                            "id": st.session_state.get("auth_username", "manager"),
                            "username": st.session_state.get("auth_username", "manager"),
                            "role": st.session_state.get("auth_role", "Manager"),
                        }
                        decide_request(st.session_state, mgr, r_id, approve=True, comment=comment)
                        st.rerun()
                with col_deny:
                    if st.button("Deny", key=f"btn_deny_{r_id}"):
                        mgr = {
                            "id": st.session_state.get("auth_username", "manager"),
                            "username": st.session_state.get("auth_username", "manager"),
                            "role": st.session_state.get("auth_role", "Manager"),
                        }
                        decide_request(st.session_state, mgr, r_id, approve=False, comment=comment)
                        st.rerun()

    # b. Members and access
    st.subheader("Members and access")
    members_list = list(st.session_state.get("members", []))
    mgr_username = st.session_state.get("auth_username", "manager")
    if not any(m.get("id") == mgr_username or m.get("username") == mgr_username for m in members_list):
        members_list.insert(0, {
            "id": mgr_username,
            "username": mgr_username,
            "name": st.session_state.get("auth_name", "Manager"),
            "role": "Manager",
        })

    member_rows = []
    for m in members_list:
        eff = get_effective_access(m, st.session_state)
        member_rows.append({
            "Name": eff["name"],
            "Role": eff["role"],
            "Project content": eff["project_content"],
            "Confidential files": eff["confidential_files"],
        })
    st.table(member_rows)

    # c. For each non-manager active member, an st.expander(name) holding an st.form
    non_managers = [m for m in members_list if m.get("role") != "Manager"]
    for m in non_managers:
        uid = m.get("id") or m.get("username")
        m_name = m.get("name", uid)
        with st.expander(m_name):
            with st.form(f"form_grants_{uid}"):
                cur_g = get_member_grants(st.session_state, uid)
                is_employee = (m.get("role") == "Employee")
                has_write = True if is_employee else ("normal_write" in cur_g)
                has_cread = "confidential_read" in cur_g or "confidential_write" in cur_g
                has_cwrite = "confidential_write" in cur_g

                cb_w = st.checkbox(
                    "Write access to project content",
                    value=has_write,
                    disabled=is_employee,
                    key=f"cb_w_{uid}"
                )
                cb_cr = st.checkbox(
                    "Read confidential files",
                    value=has_cread,
                    key=f"cb_cr_{uid}"
                )
                cb_cw = st.checkbox(
                    "Read and write confidential files",
                    value=has_cwrite,
                    key=f"cb_cw_{uid}"
                )
                if st.form_submit_button("Save access", type="primary"):
                    mgr = {
                        "id": st.session_state.get("auth_username", "manager"),
                        "username": st.session_state.get("auth_username", "manager"),
                        "role": st.session_state.get("auth_role", "Manager"),
                    }
                    new_g = []
                    if cb_w and not is_employee:
                        new_g.append("normal_write")
                    if cb_cr:
                        new_g.append("confidential_read")
                    if cb_cw:
                        new_g.append("confidential_write")
                        new_g.append("confidential_read")
                    set_grants(st.session_state, mgr, uid, new_g)
                    st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 11: NOTIFICATIONS
# ═══════════════════════════════════════════════════════════════════════════════
elif st.session_state.page == "notifications":
    require_page_access("notifications")
    st.header("Notifications")

    cur_uid = st.session_state.get("auth_username", "")
    col_n1, col_n2, _ = st.columns([2, 1, 4])
    with col_n1:
        if st.button("Mark all as read", key="btn_mark_all_read"):
            mark_notifications_read(cur_uid, session_state=st.session_state)
            st.rerun()
    with col_n2:
        if st.button("Refresh", key="btn_refresh_notifs"):
            st.rerun()

    st.caption("Notifications update when you open a page or press Refresh.")

    my_notifs = [n for n in st.session_state.get("notifications", []) if n.get("to") == cur_uid]
    if not my_notifs:
        st.caption("No notifications.")
    else:
        for n in reversed(my_notifs):
            with st.container(border=True):
                is_unread = not n.get("read")
                prefix = "**New** &mdash; " if is_unread else ""
                st.markdown(f"{prefix}{n.get('message', '')}")
                st.caption(n.get("created_at", ""))


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 12: CONFIDENTIAL FILES
# ═══════════════════════════════════════════════════════════════════════════════
elif st.session_state.page == "confidential":
    require_page_access("confidential")
    st.header("Confidential files")

    cur_user = {
        "id": st.session_state.get("auth_username", ""),
        "username": st.session_state.get("auth_username", ""),
        "name": st.session_state.get("auth_name", ""),
        "role": st.session_state.get("auth_role", ""),
    }

    c_files = st.session_state.get("confidential_files", [])
    if not c_files:
        st.caption("No confidential files stored.")
    else:
        for _cf_idx, cf in enumerate(c_files):
            with st.container(border=True):
                _cf_name = cf.get("name", "File")
                st.markdown(f"**{_cf_name}** ({cf.get('size', 0)} bytes)")
                st.caption(f"Uploaded: {cf.get('uploaded_at', '')} by {cf.get('uploaded_by', '')}")
                # Permission check before showing content
                if can_read(cur_user, is_confidential=True, state=st.session_state):
                    with st.expander("View file content"):
                        # Files stored before this fix had content as decoded text string.
                        # Files stored after this fix have content=None (bytes stored separately).
                        _cf_content = cf.get("content")
                        if _cf_content is None:
                            # New storage: bytes not in db, need re-upload
                            st.info("File content not available in this session. Re-upload to enable preview.")
                        elif isinstance(_cf_content, (bytes, bytearray)):
                            render_file_preview(
                                _cf_name, bytes(_cf_content),
                                key_prefix=f"cf_{_cf_idx}",
                                can_download=True,
                            )
                        else:
                            # Legacy: content was stored as a decoded string
                            _legacy_bytes = _cf_content.encode("utf-8", errors="replace")
                            if _legacy_bytes[:4] == b"%PDF" or _cf_name.lower().endswith(".pdf"):
                                st.warning("This file was stored incorrectly. Please upload it again.")
                            else:
                                st.text_area(
                                    label="File content",
                                    value=_cf_content,
                                    height=300,
                                    disabled=True,
                                    label_visibility="collapsed",
                                    key=f"cf_{_cf_idx}_preview",
                                )

    if can_write(cur_user, is_confidential=True, state=st.session_state):
        st.subheader("Upload confidential file")
        up_file = st.file_uploader("Select confidential file", key="conf_file_uploader")
        if up_file is not None:
            if st.button("Upload confidential file", type="primary", key="btn_upload_conf"):
                _conf_bytes = up_file.getvalue()  # read once; second read returns empty
                if not _conf_bytes:
                    st.error("The uploaded file is empty. Please upload it again.")
                else:
                    _cf_id = register_confidential_meta(
                        name=up_file.name,
                        size_bytes=len(_conf_bytes),
                        uploaded_by=cur_user["id"],
                    )
                    # Store metadata in session-state list (no bytes in db)
                    conf_item = {
                        "id": _cf_id,
                        "name": up_file.name,
                        "size": len(_conf_bytes),
                        "uploaded_by": cur_user["id"],
                        "uploaded_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                        "content": None,  # bytes not persisted in db per Phase 4
                    }
                    def _add_conf(d):
                        d.setdefault("confidential_files", []).append(conf_item)
                    modify_project_state(_add_conf, session_state=st.session_state)
                    log_audit_entry(st.session_state, cur_user["id"], "uploaded confidential file")
                    st.rerun()
