"""
Baton — Knowledge Handover Platform
Enterprise Presentation Layer Refactor
"""

import copy
import json
import os
import re
import textwrap
import time
import streamlit as st

# ─── Page config (must be first Streamlit call) ───────────────────────────────
st.set_page_config(
    page_title="Baton — Knowledge Handover Platform",
    page_icon=":material/swap_horiz:",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── SESSION STATE INIT (Early Initialization for Theme) ──────────────────────
def init_session_state():
    defaults = {
        "page": "connect",
        "theme": "System",
        "api_key": "",
        "employee_name": "",
        "project_role": "",
        "uploaded_files": None,
        "github_url": "",
        "github_token": "",
        "pasted_text": "",
        "knowledge_profile": None,
        "is_demo": False,
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
        "view_role": "Manager",
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val

init_session_state()

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


# ─── GLOBAL DESIGN SYSTEM & THEME ENGINE ──────────────────────────────────────
def get_theme_css(theme: str) -> str:
    light_tokens = """
    --bg-canvas: #F8F9FC;
    --bg-surface: #FFFFFF;
    --bg-subtle: #F1F4F9;
    --border-color: #E2E6EF;
    --border-strong: #CBD2E0;
    --text-primary: #0F172A;
    --text-secondary: #475569;
    --text-muted: #64748B;
    
    --accent: #4F46E5;
    --accent-hover: #4338CA;
    --accent-subtle: rgba(79, 70, 229, 0.08);
    --accent-border: rgba(79, 70, 229, 0.25);
    --accent-gradient: linear-gradient(135deg, #6366F1 0%, #4F46E5 100%);
    --card-shadow: 0 1px 3px rgba(15, 23, 42, 0.05), 0 6px 16px rgba(15, 23, 42, 0.03);
    --card-shadow-hover: 0 4px 20px rgba(79, 70, 229, 0.09);
    
    --status-success-text: #059669;
    --status-success-bg: #ECFDF5;
    --status-success-border: #A7F3D0;
    
    --status-warning-text: #D97706;
    --status-warning-bg: #FFFBEB;
    --status-warning-border: #FDE68A;
    
    --status-danger-text: #DC2626;
    --status-danger-bg: #FEF2F2;
    --status-danger-border: #FECACA;

    --radius: 10px;
    --radius-sm: 6px;
    --radius-lg: 14px;
    """

    dark_tokens = """
    --bg-canvas: #0F1117;
    --bg-surface: #171923;
    --bg-subtle: #1F2230;
    --border-color: #272B3C;
    --border-strong: #383D54;
    --text-primary: #F3F4F8;
    --text-secondary: #9FA6BC;
    --text-muted: #687087;
    
    --accent: #6366F1;
    --accent-hover: #4F46E5;
    --accent-subtle: rgba(99, 102, 241, 0.15);
    --accent-border: rgba(99, 102, 241, 0.35);
    --accent-gradient: linear-gradient(135deg, #818CF8 0%, #6366F1 100%);
    --card-shadow: 0 4px 20px rgba(0, 0, 0, 0.35), inset 0 1px 0 rgba(255, 255, 255, 0.06);
    --card-shadow-hover: 0 6px 24px rgba(99, 102, 241, 0.16), inset 0 1px 0 rgba(255, 255, 255, 0.10);
    
    --status-success-text: #34D399;
    --status-success-bg: rgba(16, 185, 129, 0.12);
    --status-success-border: rgba(16, 185, 129, 0.28);
    
    --status-warning-text: #FBBF24;
    --status-warning-bg: rgba(245, 158, 11, 0.12);
    --status-warning-border: rgba(245, 158, 11, 0.28);
    
    --status-danger-text: #F87171;
    --status-danger-bg: rgba(239, 68, 68, 0.12);
    --status-danger-border: rgba(239, 68, 68, 0.28);

    --radius: 10px;
    --radius-sm: 6px;
    --radius-lg: 14px;
    """

    if theme == "Dark":
        vars_block = f":root {{\n{dark_tokens}\n}}"
    elif theme == "Light":
        vars_block = f":root {{\n{light_tokens}\n}}"
    else:  # "System"
        vars_block = f""":root {{
{light_tokens}
}}
@media (prefers-color-scheme: dark) {{
    :root {{
{dark_tokens}
    }}
}}"""

    return f"""
<style>
{vars_block}

/* Global resets & human typography with atmospheric ambient background */
html, body, [data-testid="stAppViewContainer"] {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif !important;
    background-color: var(--bg-canvas) !important;
    background-image: radial-gradient(circle at 50% -12%, rgba(99, 102, 241, 0.11), transparent 60%),
                      radial-gradient(circle at 92% 16%, rgba(245, 158, 11, 0.04), transparent 45%) !important;
    background-attachment: fixed !important;
    color: var(--text-primary) !important;
    -webkit-font-smoothing: antialiased;
}}

[data-testid="stHeader"] {{
    background: transparent !important;
}}

/* Container shell: fluid, open workspace instead of a claustrophobic box */
.main .block-container {{
    max-width: 1240px !important;
    padding: 1.25rem 2rem 3rem 2rem !important;
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    color: var(--text-primary) !important;
}}

/* Top Stepper Navigation: Floating executive header */
.kb-top-navbar {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.85rem 1.35rem;
    background: var(--bg-surface);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-lg);
    margin-bottom: 1.5rem;
    gap: 1rem;
    flex-wrap: wrap;
    box-shadow: var(--card-shadow);
}}
.kb-nav-brand {{
    display: flex;
    align-items: center;
    gap: 0.75rem;
}}
.kb-brand-logo {{
    width: 32px;
    height: 32px;
    border-radius: 9px;
    background: var(--accent-gradient);
    display: flex;
    align-items: center;
    justify-content: center;
    color: #FFFFFF;
    box-shadow: 0 2px 10px rgba(99, 102, 241, 0.35);
}}
.kb-brand-text {{
    display: flex;
    flex-direction: column;
}}
.kb-brand-title {{
    font-size: 1.12rem;
    font-weight: 700;
    color: var(--text-primary);
    letter-spacing: -0.02em;
    line-height: 1.15;
}}
.kb-brand-sub {{
    font-size: 0.72rem;
    font-weight: 500;
    color: var(--text-muted);
    letter-spacing: 0.01em;
}}
.kb-nav-steps {{
    display: flex;
    align-items: center;
    gap: 0.4rem;
    flex-wrap: wrap;
}}
.kb-step-connector {{
    width: 12px;
    height: 2px;
    background: var(--border-color);
    border-radius: 1px;
}}
.kb-nav-step-item {{
    display: inline-flex;
    align-items: center;
    gap: 0.45rem;
    font-size: 0.8125rem;
    font-weight: 500;
    color: var(--text-muted);
    padding: 4px 10px;
    border-radius: 20px;
    border: 1px solid transparent;
    transition: all 0.18s ease;
}}
.kb-step-num {{
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 18px;
    height: 18px;
    border-radius: 50%;
    font-size: 0.68rem;
    font-weight: 600;
    background: var(--bg-subtle);
    color: var(--text-secondary);
    line-height: 1;
}}
.kb-nav-step-item.active {{
    background: var(--accent-subtle);
    color: var(--accent) !important;
    border-color: var(--accent-border);
    font-weight: 600;
    box-shadow: 0 0 14px rgba(99, 102, 241, 0.2);
}}
.kb-nav-step-item.active .kb-step-num {{
    background: var(--accent-gradient);
    color: #FFFFFF;
}}
.kb-nav-step-item.done {{
    color: var(--status-success-text);
    background: var(--status-success-bg);
    border-color: var(--status-success-border);
}}
.kb-nav-step-item.done .kb-step-num {{
    background: transparent;
    color: var(--status-success-text);
}}
.kb-nav-status {{
    background: var(--bg-subtle);
    color: var(--text-secondary);
    padding: 4px 10px;
    border-radius: 20px;
    border: 1px solid var(--border-color);
    font-size: 0.78rem;
    font-weight: 500;
}}
.kb-nav-persona {{
    display: flex;
    align-items: center;
    gap: 0.5rem;
    background: var(--bg-subtle);
    border: 1px solid var(--border-color);
    padding: 4px 11px;
    border-radius: 20px;
    font-size: 0.78rem;
    font-weight: 500;
    color: var(--text-secondary);
}}
.kb-avatar-chip {{
    width: 20px;
    height: 20px;
    border-radius: 50%;
    background: linear-gradient(135deg, #F59E0B 0%, #D97706 100%);
    color: #FFFFFF;
    font-size: 0.62rem;
    font-weight: 700;
    display: inline-flex;
    align-items: center;
    justify-content: center;
}}

/* Sidebar: Refined, warm neutral with elevation */
[data-testid="stSidebar"] {{
    background-color: var(--bg-canvas) !important;
    border-right: 1px solid var(--border-color) !important;
}}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] span,
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] strong,
[data-testid="stSidebar"] label {{
    color: var(--text-primary) !important;
}}
.kb-sidebar-header {{
    padding: 0.25rem 0 0.75rem 0;
}}
.kb-sidebar-subtitle {{
    font-size: 0.76rem;
    color: var(--text-muted);
    margin-top: 3px;
    line-height: 1.4;
}}
.kb-sidebar-section-title {{
    font-size: 0.75rem;
    font-weight: 600;
    color: var(--text-secondary);
    margin: 1rem 0 0.45rem 0;
    text-transform: uppercase;
    letter-spacing: 0.03em;
}}
.kb-sidebar-footer {{
    font-size: 0.74rem;
    color: var(--text-muted);
    margin-top: 1.5rem;
    line-height: 1.5;
}}
[data-testid="stSidebar"] .stButton > button {{
    background: var(--bg-surface) !important;
    color: var(--text-primary) !important;
    border: 1px solid var(--border-color) !important;
    border-radius: var(--radius-sm) !important;
    font-weight: 500 !important;
    font-size: 0.85rem !important;
    text-align: left !important;
    padding: 0.5rem 0.9rem !important;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03) !important;
    transition: all 0.15s ease !important;
}}
[data-testid="stSidebar"] .stButton > button:hover {{
    background: var(--bg-subtle) !important;
    border-color: var(--accent) !important;
    transform: translateY(-1px) !important;
}}
[data-testid="stSidebar"] .stButton > button:active {{
    transform: scale(0.985) !important;
}}
[data-testid="stSidebar"] .stButton > button[kind="primary"] {{
    background: var(--accent-gradient) !important;
    color: #FFFFFF !important;
    border: 1px solid transparent !important;
    font-weight: 600 !important;
    box-shadow: 0 2px 8px rgba(79, 70, 229, 0.3) !important;
}}

/* Stat Cards: Elevated, distinctive colored stripe on top */
.kb-stat-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
    gap: 0.85rem;
    margin: 1rem 0 1.35rem 0;
}}
.kb-stat-card {{
    background: var(--bg-surface);
    border: 1px solid var(--border-color);
    border-radius: var(--radius);
    padding: 1rem 1.25rem;
    box-shadow: var(--card-shadow);
    transition: transform 0.16s ease, border-color 0.16s ease, box-shadow 0.16s ease;
    position: relative;
    overflow: hidden;
}}
.kb-stat-card:hover {{
    transform: translateY(-2px);
    border-color: var(--border-strong);
    box-shadow: var(--card-shadow-hover);
}}
.kb-stat-indicator {{
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 3px;
    background: var(--accent);
    opacity: 0.9;
}}
.kb-stat-label {{
    font-size: 0.72rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--text-muted);
    margin-bottom: 5px;
    display: flex;
    align-items: center;
    gap: 5px;
}}
.kb-stat-number {{
    font-size: 1.65rem;
    font-weight: 700;
    font-variant-numeric: tabular-nums;
    color: var(--text-primary);
    line-height: 1.15;
    letter-spacing: -0.03em;
}}

/* Structured Panels & Cards */
.kb-panel {{
    background: var(--bg-surface);
    border: 1px solid var(--border-color);
    border-radius: var(--radius);
    padding: 1.35rem 1.6rem;
    margin-bottom: 1.25rem;
    color: var(--text-primary);
    box-shadow: var(--card-shadow);
}}
.kb-panel-subtle {{
    background: var(--bg-subtle);
    border: 1px solid var(--border-color);
    border-radius: var(--radius);
    padding: 1.35rem 1.6rem;
    margin-bottom: 1.25rem;
    color: var(--text-primary);
}}
.kb-panel-hero {{
    background: var(--bg-surface);
    border: 1px solid var(--border-color);
    border-left: 4px solid var(--accent);
    border-radius: var(--radius);
    padding: 1.35rem 1.6rem;
    margin-bottom: 1.25rem;
    color: var(--text-primary);
    box-shadow: var(--card-shadow);
}}
.kb-preview-row {{
    background: var(--bg-subtle);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-sm);
    padding: 8px 12px;
    margin-bottom: 0.5rem;
    font-size: 0.85rem;
    color: var(--text-secondary);
}}
.kb-file-row {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: var(--bg-surface);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-sm);
    padding: 8px 12px;
    margin-bottom: 0.45rem;
    font-size: 0.85rem;
    color: var(--text-primary);
    box-shadow: var(--card-shadow);
    transition: border-color 0.15s ease, transform 0.15s ease;
}}
.kb-file-row:hover {{
    border-color: var(--accent);
    transform: translateY(-1px);
}}
.kb-file-info {{
    display: flex;
    align-items: center;
    gap: 8px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}}
.kb-file-ext-chip {{
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    font-size: 0.68rem;
    font-weight: 700;
    text-transform: uppercase;
    background: var(--accent-subtle);
    color: var(--accent);
    padding: 2px 6px;
    border-radius: 4px;
    border: 1px solid var(--accent-border);
    letter-spacing: 0.02em;
}}
.kb-file-size {{
    font-size: 0.75rem;
    color: var(--text-muted);
    font-variant-numeric: tabular-nums;
}}
.kb-meta-list {{
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    margin: 0.85rem 0;
}}
.kb-meta-row {{
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    font-size: 0.84rem;
    padding: 7px 11px;
    border-radius: var(--radius-sm);
    background: var(--bg-subtle);
    border: 1px solid var(--border-color);
}}
.kb-meta-key {{
    color: var(--text-muted);
    font-weight: 600;
    font-size: 0.74rem;
    text-transform: uppercase;
    letter-spacing: 0.03em;
}}
.kb-meta-val {{
    color: var(--text-primary);
    font-weight: 600;
    text-align: right;
}}
.kb-citation {{
    background: var(--bg-subtle);
    border: 1px solid var(--border-color);
    border-left: 3px solid var(--accent);
    border-radius: var(--radius-sm);
    padding: 9px 13px;
    margin: 0.5rem 0 0.75rem 0;
}}
.kb-citation-header {{
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 4px;
}}
.kb-citation-tag {{
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    font-size: 0.65rem;
    font-weight: 700;
    color: var(--accent);
    background: var(--accent-subtle);
    padding: 1px 6px;
    border-radius: 3px;
    border: 1px solid var(--accent-border);
    letter-spacing: 0.04em;
}}
.kb-citation-source {{
    font-size: 0.75rem;
    color: var(--text-muted);
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}}
.kb-citation-body {{
    font-size: 0.85rem;
    font-style: italic;
    color: var(--text-secondary);
    line-height: 1.5;
}}
.kb-audit-entry {{
    display: flex;
    align-items: flex-start;
    gap: 12px;
    padding: 7px 9px;
    border-bottom: 1px solid var(--border-color);
    font-size: 0.8125rem;
}}
.kb-audit-time {{
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    font-size: 0.75rem;
    color: var(--text-muted);
    white-space: nowrap;
    font-variant-numeric: tabular-nums;
}}
.kb-audit-who {{
    font-weight: 600;
    color: var(--text-primary);
}}
.kb-audit-action {{
    color: var(--text-secondary);
}}
.kb-audit-reason {{
    font-style: italic;
    color: var(--text-muted);
}}
.kb-receipt-card {{
    background: var(--bg-surface);
    border: 1px solid var(--status-success-border);
    border-left: 4px solid var(--status-success-text);
    border-radius: var(--radius);
    padding: 1.15rem 1.4rem;
    margin: 1rem 0;
    box-shadow: var(--card-shadow);
}}
.kb-receipt-header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1px solid var(--status-success-border);
    padding-bottom: 0.65rem;
    margin-bottom: 0.85rem;
}}
.kb-receipt-badge {{
    font-size: 0.86rem;
    font-weight: 600;
    color: var(--status-success-text);
    display: flex;
    align-items: center;
    gap: 6px;
}}
.kb-receipt-timestamp {{
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    font-size: 0.75rem;
    color: var(--text-muted);
    font-variant-numeric: tabular-nums;
}}
.kb-receipt-body {{
    display: flex;
    flex-direction: column;
    gap: 0.45rem;
}}
.kb-receipt-meta {{
    display: flex;
    justify-content: space-between;
    font-size: 0.85rem;
}}
.kb-receipt-label {{
    color: var(--text-muted);
}}
.kb-receipt-value {{
    color: var(--text-primary);
}}
.kb-card {{
    background: var(--bg-surface);
    border: 1px solid var(--border-color);
    border-radius: var(--radius);
    padding: 1.1rem 1.35rem;
    margin-bottom: 0.85rem;
    color: var(--text-primary);
    box-shadow: var(--card-shadow);
    transition: transform 0.16s ease, border-color 0.16s ease, box-shadow 0.16s ease;
}}
.kb-card:hover {{
    transform: translateY(-1px);
    border-color: var(--border-strong);
    box-shadow: var(--card-shadow-hover);
}}
.kb-card-warning {{
    background: var(--status-warning-bg);
    border: 1px solid var(--status-warning-border);
    border-left: 3px solid var(--status-warning-text);
}}
.kb-card-danger {{
    background: var(--status-danger-bg);
    border: 1px solid var(--status-danger-border);
    border-left: 3px solid var(--status-danger-text);
}}
.kb-card-success {{
    background: var(--status-success-bg);
    border: 1px solid var(--status-success-border);
    border-left: 3px solid var(--status-success-text);
}}
.kb-card-info {{
    background: var(--bg-surface);
    border: 1px solid var(--border-color);
    border-left: 3px solid var(--accent);
}}
.kb-section-title {{
    font-size: 1.08rem;
    font-weight: 600;
    color: var(--text-primary);
    margin-bottom: 0.85rem;
    letter-spacing: -0.01em;
}}

/* Badges: Soft pills, readable contrast */
.badge {{
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 3px 9px;
    border-radius: 12px;
    font-size: 0.74rem;
    font-weight: 600;
    line-height: 1.2;
}}
.badge-neutral {{ background: var(--bg-subtle); color: var(--text-secondary); border: 1px solid var(--border-color); }}
.badge-success {{ background: var(--status-success-bg); color: var(--status-success-text); border: 1px solid var(--status-success-border); }}
.badge-warning {{ background: var(--status-warning-bg); color: var(--status-warning-text); border: 1px solid var(--status-warning-border); }}
.badge-danger  {{ background: var(--status-danger-bg); color: var(--status-danger-text); border: 1px solid var(--status-danger-border); }}

/* Buttons: Tactile controls with human polish */
button[kind="primary"] {{
    background: var(--accent-gradient) !important;
    color: #FFFFFF !important;
    border: 1px solid transparent !important;
    border-radius: var(--radius-sm) !important;
    font-weight: 600 !important;
    font-size: 0.88rem !important;
    padding: 0.55rem 1.25rem !important;
    box-shadow: 0 2px 8px rgba(79, 70, 229, 0.28) !important;
    transition: all 0.18s ease !important;
}}
button[kind="primary"]:hover {{
    filter: brightness(1.08) !important;
    box-shadow: 0 4px 14px rgba(79, 70, 229, 0.4) !important;
    transform: translateY(-1px) !important;
}}
button[kind="primary"]:active {{
    transform: scale(0.985) !important;
}}
button[kind="secondary"] {{
    background-color: var(--bg-surface) !important;
    color: var(--text-primary) !important;
    border: 1px solid var(--border-strong) !important;
    border-radius: var(--radius-sm) !important;
    font-weight: 500 !important;
    font-size: 0.88rem !important;
    padding: 0.55rem 1.25rem !important;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04) !important;
    transition: all 0.15s ease !important;
}}
button[kind="secondary"]:hover {{
    background-color: var(--bg-subtle) !important;
    border-color: var(--accent) !important;
    color: var(--text-primary) !important;
    transform: translateY(-1px) !important;
}}
button[kind="secondary"]:active {{
    transform: scale(0.985) !important;
}}
button:focus-visible {{
    outline: 2px solid var(--accent) !important;
    outline-offset: 2px !important;
}}

/* Form Controls */
div[data-baseweb="input"] > div,
div[data-baseweb="textarea"] > div,
div[data-baseweb="select"] > div {{
    background-color: var(--bg-surface) !important;
    border: 1px solid var(--border-strong) !important;
    border-radius: var(--radius-sm) !important;
    color: var(--text-primary) !important;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03) !important;
    transition: border-color 0.15s ease !important;
}}
div[data-baseweb="input"] input,
div[data-baseweb="textarea"] textarea {{
    color: var(--text-primary) !important;
    background-color: transparent !important;
}}
div[data-baseweb="input"] > div:focus-within,
div[data-baseweb="textarea"] > div:focus-within,
div[data-baseweb="select"] > div:focus-within {{
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 2px var(--accent-subtle) !important;
}}

/* Selectbox dropdown menu */
div[role="listbox"] {{
    background-color: var(--bg-surface) !important;
    border: 1px solid var(--border-strong) !important;
    border-radius: var(--radius-sm) !important;
    box-shadow: var(--card-shadow) !important;
}}
div[role="option"] {{
    color: var(--text-primary) !important;
}}
div[role="option"]:hover,
div[role="option"][aria-selected="true"] {{
    background-color: var(--bg-subtle) !important;
}}

/* Radio options */
div[data-testid="stRadio"] label span {{
    color: var(--text-primary) !important;
}}

/* Blockquote & Markdown styling */
blockquote {{
    border-left: 3px solid var(--accent) !important;
    background: var(--bg-subtle) !important;
    color: var(--text-secondary) !important;
    padding: 0.6rem 1rem !important;
    margin: 0.6rem 0 !important;
    border-radius: 0 var(--radius-sm) var(--radius-sm) 0 !important;
}}
hr {{
    border-color: var(--border-color) !important;
}}
h1, h2, h3, h4, h5, h6 {{
    color: var(--text-primary) !important;
}}

/* Tabs */
button[data-baseweb="tab"] {{
    font-size: 0.85rem !important;
    font-weight: 500 !important;
    color: var(--text-muted) !important;
    border-radius: var(--radius-sm) !important;
    padding: 0.45rem 0.9rem !important;
}}
button[data-baseweb="tab"][aria-selected="true"] {{
    color: var(--accent) !important;
    background-color: var(--accent-subtle) !important;
    border-bottom: 2px solid var(--accent) !important;
}}

/* Expanders */
div[data-testid="stExpander"] {{
    background: var(--bg-surface) !important;
    border: 1px solid var(--border-color) !important;
    border-radius: var(--radius) !important;
    box-shadow: var(--card-shadow) !important;
    margin-bottom: 0.6rem !important;
}}
div[data-testid="stExpander"] details summary span {{
    color: var(--text-primary) !important;
}}

/* Notices & Banners: Human Callout with Warm Accent */
.kb-banner {{
    background: var(--bg-surface);
    border: 1px solid var(--border-color);
    border-left: 4px solid var(--accent);
    border-radius: var(--radius);
    padding: 12px 16px;
    margin-bottom: 1.25rem;
    font-size: 0.86rem;
    color: var(--text-secondary);
    box-shadow: var(--card-shadow);
    line-height: 1.5;
}}
.kb-banner-tip {{
    background: var(--accent-subtle);
    border: 1px solid var(--accent-border);
    border-left: 4px solid var(--accent);
    border-radius: var(--radius);
    padding: 12px 16px;
    margin-bottom: 1.25rem;
    font-size: 0.86rem;
    color: var(--text-primary);
    line-height: 1.5;
}}

/* Progress Bar */
.stProgress > div > div > div > div {{
    background: var(--accent-gradient) !important;
    border-radius: var(--radius-sm) !important;
}}

/* Responsive Rules down to ~375px */
@media (max-width: 768px) {{
    .main .block-container {{
        padding: 1rem 1rem 2rem 1rem !important;
    }}
    .kb-top-navbar {{
        flex-direction: column;
        align-items: flex-start;
        gap: 0.75rem;
    }}
    .kb-nav-steps {{
        flex-wrap: wrap;
    }}
    .kb-stat-grid {{
        grid-template-columns: repeat(2, 1fr);
    }}
}}
@media (max-width: 480px) {{
    .kb-stat-grid {{
        grid-template-columns: 1fr;
    }}
    .main .block-container {{
        padding: 0.75rem 0.75rem 1.5rem 0.75rem !important;
    }}
}}

/* Markdown document typography — tables and code blocks */
div[data-testid="stMarkdownContainer"] table {{
    border-collapse: collapse !important;
    width: 100% !important;
    font-size: 0.84rem !important;
    margin: 1rem 0 !important;
    border: 1px solid var(--border-color) !important;
    border-radius: var(--radius) !important;
    overflow: hidden !important;
    box-shadow: var(--card-shadow) !important;
}}
div[data-testid="stMarkdownContainer"] th {{
    background: var(--bg-subtle) !important;
    color: var(--text-secondary) !important;
    font-weight: 600 !important;
    font-size: 0.75rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.04em !important;
    padding: 8px 12px !important;
    border-bottom: 1px solid var(--border-strong) !important;
    text-align: left !important;
}}
div[data-testid="stMarkdownContainer"] td {{
    color: var(--text-primary) !important;
    padding: 7px 12px !important;
    border-bottom: 1px solid var(--border-color) !important;
    vertical-align: top !important;
}}
div[data-testid="stMarkdownContainer"] tr:last-child td {{
    border-bottom: none !important;
}}
div[data-testid="stMarkdownContainer"] tr:nth-child(even) td {{
    background: var(--bg-subtle) !important;
}}
div[data-testid="stMarkdownContainer"] code {{
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace !important;
    font-size: 0.82em !important;
    background: var(--bg-subtle) !important;
    color: var(--accent) !important;
    padding: 2px 6px !important;
    border-radius: 4px !important;
    border: 1px solid var(--border-color) !important;
}}
div[data-testid="stMarkdownContainer"] pre {{
    background: var(--bg-subtle) !important;
    border: 1px solid var(--border-color) !important;
    border-radius: var(--radius) !important;
    padding: 1rem 1.25rem !important;
    overflow-x: auto !important;
}}
div[data-testid="stMarkdownContainer"] pre code {{
    background: transparent !important;
    border: none !important;
    padding: 0 !important;
    color: var(--text-primary) !important;
    font-size: 0.84rem !important;
}}

/* Approval progress heading */
.kb-approval-progress {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.6rem 0;
    margin-bottom: 0.5rem;
}}
.kb-approval-progress-label {{
    font-size: 0.875rem;
    font-weight: 600;
    color: var(--text-secondary);
}}
.kb-approval-progress-count {{
    font-size: 1.1rem;
    font-weight: 700;
    font-variant-numeric: tabular-nums;
    color: var(--text-primary);
    letter-spacing: -0.025em;
}}

/* Review action box */
.kb-review-action-box {{
    background: var(--bg-subtle);
    border: 1px solid var(--border-color);
    border-radius: var(--radius);
    padding: 0.85rem 1rem;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
}}

/* Accessibility: Reduced motion */
@media (prefers-reduced-motion: reduce) {{
    *, ::before, ::after {{
        animation-duration: 0.01ms !important;
        animation-iteration-count: 1 !important;
        transition-duration: 0.01ms !important;
        scroll-behavior: auto !important;
    }}
}}
</style>
"""

st.markdown(get_theme_css(st.session_state.get("theme", "System")), unsafe_allow_html=True)


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
    return f"""
    <div class="kb-file-row">
        <div class="kb-file-info">
            {icon_svg("file", 13)}
            <span class="kb-file-ext-chip">{ext}</span>
            <span style="font-weight:500;">{filename}</span>
        </div>
        <span class="kb-file-size">{size_str}</span>
    </div>
    """


def render_citation(source: str, excerpt: str) -> str:
    """Structured citation block: monospace source tag + styled excerpt."""
    if not excerpt:
        return ""
    return f"""
    <div class="kb-citation">
        <div class="kb-citation-header">
            <span class="kb-citation-tag">SOURCE</span>
            <span class="kb-citation-source">{source}</span>
        </div>
        <div class="kb-citation-body">"{excerpt}"</div>
    </div>
    """


def render_audit_entry(entry: dict) -> str:
    """Structured audit log row with monospace timestamp."""
    status_color = "var(--status-success-text)" if "Approved" in entry.get("action", "") else "var(--status-danger-text)"
    return f"""
    <div class="kb-audit-entry">
        <span class="kb-audit-time">{entry.get('timestamp', '')}</span>
        <span class="kb-audit-who">{entry.get('who', '')}</span>
        <span class="kb-audit-action" style="color:{status_color};">{entry.get('action', '')}</span>
        <span class="kb-audit-reason">{entry.get('reason', '')}</span>
    </div>
    """


def render_receipt_card(name: str, timestamp: str, project: str, employee: str) -> str:
    """Post-acknowledgment signed receipt card."""
    return f"""
    <div class="kb-receipt-card">
        <div class="kb-receipt-header">
            <span class="kb-receipt-badge">
                {icon_svg("check", 14)} Receipt acknowledged
            </span>
            <span class="kb-receipt-timestamp">{timestamp}</span>
        </div>
        <div class="kb-receipt-body">
            <div class="kb-receipt-meta">
                <span class="kb-receipt-label">Successor</span>
                <span class="kb-receipt-value">{name}</span>
            </div>
            <div class="kb-receipt-meta">
                <span class="kb-receipt-label">Knowledge holder</span>
                <span class="kb-receipt-value">{employee}</span>
            </div>
            <div class="kb-receipt-meta">
                <span class="kb-receipt-label">Project scope</span>
                <span class="kb-receipt-value">{project}</span>
            </div>
            <div class="kb-receipt-meta">
                <span class="kb-receipt-label">Status</span>
                <span class="kb-receipt-value" style="color:var(--status-success-text);">Handover complete</span>
            </div>
        </div>
    </div>
    """


# ─── DEMO DATA ────────────────────────────────────────────────────────────────
DEMO_KNOWLEDGE_PROFILE = {
    "summary": (
        "Sarah Chen served as Senior Backend Engineer on PayFlow for 3 years, "
        "architecting the core payment processing microservice. Key decisions include "
        "the PostgreSQL over MongoDB choice, the circuit breaker pattern, and the "
        "Stripe SDK integration. Critical risks include a pending database migration "
        "and an expiring vendor contract with DataVerify Inc. Several Redis caching "
        "strategies remain undocumented and require immediate attention."
    ),
    "decisions": [
        {
            "text": "Chose PostgreSQL over MongoDB for transaction storage to ensure ACID compliance for financial data.",
            "source": "architecture_notes.md",
            "source_type": "file",
            "confidence": "HIGH",
            "excerpt": "After evaluating MongoDB's eventual consistency model, we decided PostgreSQL was non-negotiable for payment ledger tables where ACID guarantees matter most."
        },
        {
            "text": "Implemented Circuit Breaker pattern using the resilience4j library to handle downstream payment gateway failures gracefully.",
            "source": "owner/payflow/README",
            "source_type": "github",
            "confidence": "HIGH",
            "excerpt": "Circuit breaker configured with 50% failure threshold and 10s half-open window. See PaymentGatewayService.java for impl."
        },
        {
            "text": "Adopted event-driven architecture with Kafka for async notification delivery, decoupling payment processing from email/SMS.",
            "source": "architecture_notes.md",
            "source_type": "file",
            "confidence": "MEDIUM",
            "excerpt": "Kafka topics: payflow.payment.completed, payflow.payment.failed, payflow.refund.initiated"
        },
        {
            "text": "Chose Stripe SDK over direct API integration for PCI-DSS compliance — avoids storing raw card data on our servers.",
            "source": "Handover Notes",
            "source_type": "text",
            "confidence": "HIGH",
            "excerpt": "NEVER implement raw card storage. Stripe handles tokenization. This was a deliberate legal decision."
        },
        {
            "text": "Rate limiting set at 1000 requests/minute per merchant using Redis sliding window counter — prevents API abuse.",
            "source": "owner/payflow/README",
            "source_type": "github",
            "confidence": "MEDIUM",
            "excerpt": "RateLimiter bean in infrastructure/RateLimiterConfig.java. Adjust RATE_LIMIT_RPM env var to change."
        },
        {
            "text": "Blue-green deployment strategy adopted for zero-downtime releases; Kubernetes manifests in /k8s directory.",
            "source": "architecture_notes.md",
            "source_type": "file",
            "confidence": "MEDIUM",
            "excerpt": "Blue/green via two Deployments sharing same LoadBalancer Service. Switch traffic by updating selector labels."
        },
    ],
    "risks": [
        {
            "text": "PostgreSQL schema migration v2.4 is incomplete — 3 tables require column additions before Q1 deadline.",
            "source": "Handover Notes",
            "confidence": "HIGH",
            "excerpt": "Migration scripts in /db/migrations/v2.4/ — DO NOT run in production without DBA review. Needs ~4h maintenance window."
        },
        {
            "text": "DataVerify Inc. vendor contract expires December 31st — identity verification will break if not renewed.",
            "source": "architecture_notes.md",
            "confidence": "HIGH",
            "excerpt": "Contact: James Whitfield (james@dataverify.io). Contract ID: DV-2021-0847. Auto-renewal was disabled."
        },
        {
            "text": "Redis cluster has no documented failover procedure — if primary node fails, rate limiting and session caching will be lost.",
            "source": "owner/payflow/open-issues",
            "confidence": "MEDIUM",
            "excerpt": "Issue #47: Redis failover runbook missing. Assigned to Sarah (never completed)."
        },
        {
            "text": "Mobile team has an undocumented direct dependency on the /v1/legacy-payments endpoint which is marked for deprecation.",
            "source": "Handover Notes",
            "confidence": "LOW",
            "excerpt": "I believe mobile is using the old endpoint but I never got written confirmation. CHECK BEFORE DEPRECATING."
        },
    ],
    "unresolved": [
        {
            "question": "What is the Redis cache invalidation strategy for user session tokens?",
            "why_unknown": "Only verbal discussions with the infrastructure team were found. No written documentation exists in any source."
        },
        {
            "question": "Is the mobile team actually calling /v1/legacy-payments in production?",
            "why_unknown": "Mobile team dependency was flagged by Sarah as uncertain. No API logs or mobile team documentation was provided."
        },
        {
            "question": "What is the disaster recovery RTO/RPO for PayFlow?",
            "why_unknown": "DR documentation was referenced in commits but the actual DR doc was not included in any source material."
        },
    ],
    "contacts": [
        {"name": "Marcus Rivera", "role": "DevOps lead — owns Kubernetes cluster and CI/CD pipeline", "source": "Handover Notes"},
        {"name": "Priya Sharma", "role": "Product Manager — owns roadmap and stakeholder communication", "source": "Handover Notes"},
        {"name": "James Whitfield", "role": "DataVerify Inc. vendor contact (james@dataverify.io) — for contract renewal", "source": "architecture_notes.md"},
    ],
    "dependencies": [
        {"item": "Stripe", "description": "Payment gateway SDK. All card processing routes through Stripe. PCI-DSS compliance depends on this.", "source": "architecture_notes.md"},
        {"item": "Kafka (Confluent Cloud)", "description": "Async messaging for payment events. Credentials in AWS Secrets Manager under /payflow/kafka.", "source": "owner/payflow/README"},
        {"item": "DataVerify Inc.", "description": "Identity verification vendor. Contract expires Dec 31. KYC flows break without this.", "source": "architecture_notes.md"},
        {"item": "Redis (AWS ElastiCache)", "description": "Rate limiting and session caching. No documented failover procedure.", "source": "owner/payflow/open-issues"},
        {"item": "Mobile Team", "description": "Internal team with possible dependency on legacy endpoint. Status unclear.", "source": "Handover Notes"},
    ]
}

DEMO_MANAGER_HANDOVER = """# Manager Handover — PayFlow Project
### Departing: Sarah Chen | Senior Backend Engineer

---

## Executive Summary
PayFlow is a production-grade payment processing microservice processing thousands of transactions daily. Sarah Chen, its primary architect and engineer for 3 years, is departing. This handover identifies **two critical time-sensitive risks** requiring immediate management action before her last day.

## Key Decisions & Rationale
| Decision | Business Impact |
|----------|----------------|
| PostgreSQL for transactions | ACID compliance — critical for financial audit trails |
| Stripe SDK integration | PCI-DSS compliance — avoids costly card data liability |
| Circuit Breaker pattern | Resilience — payment gateway outages do not cascade |
| Event-driven (Kafka) | Scale — async processing supports 10x transaction growth |

## Critical Risks — Action Required
1. **Database Migration Incomplete** — v2.4 schema changes must be completed before Q1. Requires a 4-hour maintenance window and DBA oversight. Assign immediately.
2. **Vendor Contract Expiring Dec 31** — DataVerify Inc. identity verification contract auto-renewal was disabled. Contact James Whitfield (james@dataverify.io) this week.
3. **Redis Failover Undocumented** — If the caching layer fails, rate limiting breaks. Ask DevOps (Marcus Rivera) to document the runbook.

## Ownership & Contacts
- **Marcus Rivera** — DevOps, Kubernetes, CI/CD (first call for infra issues)
- **Priya Sharma** — Product Manager, roadmap owner, stakeholder communication
- **James Whitfield** — DataVerify vendor, contract renewal (external)

## External Dependencies
| Vendor/Service | Criticality | Action Required |
|---------------|-------------|-----------------|
| Stripe | Critical | Monitor SDK updates |
| DataVerify Inc. | Critical | Renew contract before Dec 31 |
| Confluent Kafka | High | Check Confluent Cloud billing |
| AWS ElastiCache (Redis) | High | Document failover procedure |

## Open Items Requiring Management Action
- [ ] Assign engineer to complete DB migration v2.4
- [ ] Renew DataVerify contract (deadline: Dec 31)
- [ ] Confirm mobile team's dependency on legacy endpoint
- [ ] Hire/assign Redis failover runbook owner
- [ ] Schedule 1:1 knowledge transfer sessions with Marcus Rivera
"""

DEMO_NEWHIRE_HANDOVER = """# Technical Successor Handover — PayFlow Technical Guide
### From: Sarah Chen | To: Technical Successor

---

## Architecture & Technical Decisions

### Why PostgreSQL (not MongoDB)?
We evaluated MongoDB in 2021. The eventual consistency model is not acceptable for a financial ledger. Every payment record needs ACID guarantees. If someone ever suggests switching to MongoDB again, reference Issue #3 in the repository.

### Circuit Breaker Pattern
`PaymentGatewayService.java` uses resilience4j. The thresholds (50% failure rate, 10s half-open window) were tuned over 6 months. Do not change them without load testing.

### Kafka Topics
```
payflow.payment.completed   → triggers email/SMS notifications
payflow.payment.failed      → triggers retry logic and alerts
payflow.refund.initiated    → triggers refund workflow
```
Credentials: AWS Secrets Manager → `/payflow/kafka/`

### Stripe Integration
We use the Stripe SDK deliberately. Never store raw card data. Never bypass the SDK for efficiency. This is a legal and compliance decision, not a technical preference.

## What Not To Break

| Area | Context |
|------|---------|
| `/v1/legacy-payments` endpoint | Mobile team may depend on it. Confirm before deprecating. |
| PostgreSQL migration v2.4 | Incomplete. Run in staging first with a DBA. |
| Rate limiter config | 1000 req/min per merchant. Changing this needs product sign-off. |
| Blue/green deploy selector | Wrong label routes traffic to wrong version. Verify Kubernetes manifests. |

## Key Contacts
- **Marcus Rivera** — Infrastructure, Kubernetes, deployment issues (#devops).
- **Priya Sharma** — Product roadmap, merchant requirements, business escalations.
- **James Whitfield** (james@dataverify.io) — DataVerify KYC API issues. Contract expires Dec 31.

## Unresolved Technical Debt
1. **Redis failover** — No runbook exists. If ElastiCache primary fails, the rate limiter breaks. Consult Marcus Rivera.
2. **Redis cache invalidation** — Session token TTL strategy was discussed verbally. Verify with infrastructure team.
3. **DR RTO/RPO** — Referenced in commits but the formal DR specification requires completion before the next compliance audit.

## Deprecated Approaches
- MongoDB — Evaluated in 2021. Data consistency issues. Abandoned.
- Direct Stripe API calls — Compliance burden without SDK tokenization. Abandoned.
- Synchronous notifications — Caused payment timeouts under load. Kafka event architecture resolved this.
"""

DEMO_EMPLOYEE_GAP_ANSWERS = {
    "What is the Redis cache invalidation strategy for user session tokens?": (
        "We use a TTL-based approach: session tokens expire after 30 minutes of inactivity. "
        "On every authenticated request, the TTL is refreshed. If a user explicitly logs out, "
        "we delete the key immediately. There is also a daily cleanup cron that sweeps orphaned keys. "
        "Marcus Rivera and I discussed this over Slack in March 2023 — the infra team preferred "
        "passive expiry over active invalidation for simplicity."
    ),
    "Is the mobile team actually calling /v1/legacy-payments in production?": (
        "YES — I checked the API gateway logs in August and saw ~200 req/day from the mobile app's "
        "user-agent hitting /v1/legacy-payments. I told their lead (Dev Kapoor) about deprecation "
        "plans and he said they would migrate to v2, but I never received a timeline. DO NOT deprecate "
        "without confirming with Dev first. His Slack handle is @dev.kapoor."
    ),
    "What is the disaster recovery RTO/RPO for PayFlow?": (
        "Unofficial targets are RTO=1hr, RPO=15min based on a conversation with our VP of Engineering "
        "in Q2 2023. We never formalized this in writing. The PostgreSQL backups run every 15 minutes "
        "via AWS RDS automated snapshots. Redis is not backed up — it is treated as ephemeral. "
        "If you lose Redis, you lose active sessions and rate limiter state, but no financial data."
    ),
}

DEMO_EMPLOYEE_TRIBAL_KNOWLEDGE = [
    {
        "category": "Warning",
        "title": "Never deploy on Fridays or month-end",
        "content": (
            "Merchant transaction volume spikes 3x on the last 3 days of every month. "
            "A deploy caused a 12-minute outage in June 2022 during peak processing resulting in $8K in failed transactions. "
            "The SRE team maintains a soft freeze policy, but it is not automated in CI/CD."
        ),
    },
    {
        "category": "Tip",
        "title": "Stripe webhook debugging shortcut",
        "content": (
            "When payment webhooks fail silently, check Stripe Dashboard → Developers → Webhooks → event response code. "
            "Most errors are 401s from rotated webhook signing secrets in AWS Secrets Manager not updated in the Stripe dashboard."
        ),
    },
    {
        "category": "Process",
        "title": "PCI compliance audit preparation",
        "content": (
            "The annual PCI audit occurs in March. ComplianceFirst Inc. requires: "
            "1) Network diagram (/docs/network-arch.pdf), 2) AWS IAM access control lists, "
            "3) Proof that no raw card data touches internal servers. Priya Sharma coordinates schedules starting in January."
        ),
    },
    {
        "category": "History",
        "title": "GraphQL API evaluation findings",
        "content": (
            "In Q3 2022, a GraphQL layer on top of the REST API produced N+1 query bottlenecks on payment history endpoints. "
            "The mobile team also preferred REST. Reverted in Q4. Resolver logic is preserved in the branch feature/graphql-api."
        ),
    },
    {
        "category": "Contact",
        "title": "AWS Technical Account Manager",
        "content": (
            "Our AWS TAM is Linda Park (linda.park@aws-tam.example.com). For critical ElastiCache or RDS production incidents, "
            "emailing her directly yields response within an hour on weekdays."
        ),
    },
]

DEMO_EMPLOYEE_HANDOVER = """# Employee Notes — Sarah Chen | PayFlow
### Knowledge Addendum

---

## Employee Corrections and Context

### Decision: PostgreSQL over MongoDB
**Confirmed accurate.** This decision was pivotal during the 2023 compliance audit. Auditors reviewed data consistency guarantees and PostgreSQL ACID compliance passed inspection.

### Decision: Circuit Breaker pattern
**Confirmed accurate.** The 50% failure threshold and 10s half-open window were calibrated through 6 months of production telemetry. Do not adjust without benchmark load testing.

### Risk: Mobile team legacy endpoint
**Active risk.** API gateway telemetry verified ~200 requests/day from mobile clients to `/v1/legacy-payments`. Coordinate with Dev Kapoor (@dev.kapoor) prior to endpoint deprecation.

---

## Resolved Questions

### What is the Redis cache invalidation strategy for user session tokens?
TTL sliding expiration set to 30 minutes. Explicit logout executes instant key eviction. Daily cron sweeps expired references. Agreed verbally with Marcus Rivera in March 2023.

### Is the mobile team actually calling /v1/legacy-payments in production?
Confirmed active. ~200 requests/day recorded in gateway telemetry. Dev Kapoor informed; awaiting migration commit.

### What is the disaster recovery RTO/RPO for PayFlow?
Working targets: RTO = 1 hour, RPO = 15 minutes. PostgreSQL backups run via 15-minute RDS snapshots. Redis is ephemeral.

---

## Tribal Knowledge and Constraints

### Warning: Deployment freezes on month-end
Transaction volume increases 3x during month-end closes. Deployments are discouraged during the final three calendar days.

### Tip: Stripe webhook triage
Verify Stripe Dashboard event response codes first before inspecting CloudWatch logs.

### Process: PCI audit requirements
Annual March audit requires updated network diagrams, IAM access lists, and SDK tokenization verification.

### Contact: AWS escalation
Direct TAM contact: Linda Park (linda.park@aws-tam.example.com).
"""




# ─── COMPONENT HELPERS ────────────────────────────────────────────────────────
def source_badge(source_type: str) -> str:
    badges = {
        "file":   f'<span class="badge badge-neutral">{icon_svg("file")} File</span>',
        "github": f'<span class="badge badge-neutral">{icon_svg("repo")} Repository</span>',
        "text":   f'<span class="badge badge-neutral">{icon_svg("text")} Notes</span>',
    }
    return badges.get(source_type, f'<span class="badge badge-neutral">{icon_svg("file")} Source</span>')


def confidence_badge(confidence: str) -> str:
    badges = {
        "HIGH":   '<span class="badge badge-success">High confidence</span>',
        "MEDIUM": '<span class="badge badge-warning">Medium confidence</span>',
        "LOW":    '<span class="badge badge-danger">Low confidence</span>',
    }
    return badges.get(confidence, '<span class="badge badge-warning">Medium confidence</span>')


def render_stat_card(label: str, number: str, accent_color: str = "var(--accent)") -> str:
    """Refined metric card with human craft and distinct accent indicator."""
    return f"""
    <div class="kb-stat-card">
        <div class="kb-stat-indicator" style="background:{accent_color};"></div>
        <div class="kb-stat-label">
            <span style="display:inline-block; width:6px; height:6px; border-radius:50%; background:{accent_color};"></span>
            {label}
        </div>
        <div class="kb-stat-number">{number}</div>
    </div>
    """


def step_indicator(current_page: str):
    """Authoritative top workflow navigation bar with human craft."""
    pages = [
        ("connect",     "1", "Connect Sources"),
        ("reconstruct", "2", "Reconstruct"),
        ("employee",    "3", "Employee Hub"),
        ("review",      "4", "Manager Review"),
        ("handover",    "5", "Handover Package"),
    ]
    page_order = [p[0] for p in pages]
    current_idx = page_order.index(current_page) if current_page in page_order else 0

    emp_name = st.session_state.employee_name or ("Sarah Chen" if st.session_state.is_demo or not st.session_state.api_key else "")
    project_scope = st.session_state.project_role or ("PayFlow" if st.session_state.is_demo or not st.session_state.api_key else "")
    initials = "".join([part[0] for part in emp_name.split() if part])[:2].upper() if emp_name else "HB"

    html = '<div class="kb-top-navbar">'
    html += '<div class="kb-nav-brand">'
    html += f'<div class="kb-brand-logo">{icon_svg("baton", 17)}</div>'
    html += '<div class="kb-brand-text">'
    html += '<span class="kb-brand-title">Baton</span>'
    html += '<span class="kb-brand-sub">Handover Engine</span>'
    html += '</div>'
    html += '</div>'

    html += '<div class="kb-nav-steps">'
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

    if emp_name:
        html += f'<div class="kb-nav-persona"><span class="kb-avatar-chip">{initials}</span> <span>{emp_name}</span> <span style="opacity:0.4;">➔</span> <span style="color:var(--text-primary); font-weight:600;">{project_scope}</span></div>'
    else:
        status_label = "Demo mode active" if st.session_state.is_demo or not st.session_state.api_key else "Gemini active"
        html += f'<div class="kb-nav-status">{status_label}</div>'
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)


# ─── SIDEBAR ──────────────────────────────────────────────────────────────────
with st.sidebar:
    emp_name = st.session_state.employee_name or ("Sarah Chen" if st.session_state.is_demo or not st.session_state.api_key else "")
    project_scope = st.session_state.project_role or ("Senior Backend Engineer &bull; PayFlow" if st.session_state.is_demo or not st.session_state.api_key else "")
    initials = "".join([part[0] for part in emp_name.split() if part])[:2].upper() if emp_name else "HB"

    st.markdown(f"""
    <div class="kb-sidebar-header">
        <div style="display:flex; align-items:center; gap:8px;">
            <div class="kb-brand-logo" style="width:26px; height:26px;">{icon_svg("baton", 14)}</div>
            <div class="kb-brand-title" style="font-size:1.15rem;">Baton</div>
        </div>
        <div class="kb-sidebar-subtitle">Ensure nothing gets lost when teammates move on.</div>
    </div>
    """, unsafe_allow_html=True)

    if emp_name:
        st.markdown(f"""
        <div style="background:var(--bg-subtle); border:1px solid var(--border-color); border-radius:var(--radius); padding:10px 12px; margin-bottom:1rem; box-shadow:var(--card-shadow);">
            <div style="display:flex; align-items:center; gap:8px; margin-bottom:4px;">
                <span class="kb-avatar-chip">{initials}</span>
                <div style="font-size:0.83rem; font-weight:600; color:var(--text-primary);">{emp_name}</div>
            </div>
            <div style="font-size:0.75rem; color:var(--text-secondary); line-height:1.4;">{project_scope}</div>
            <div style="display:flex; align-items:center; gap:5px; margin-top:6px; font-size:0.72rem; color:var(--status-success-text); font-weight:600;">
                <span style="width:6px; height:6px; border-radius:50%; background:var(--status-success-text); display:inline-block;"></span>
                Active Handover Dossier
            </div>
        </div>
        """, unsafe_allow_html=True)

    if st.session_state.api_key:
        st.markdown(
            '<div class="kb-banner" style="margin-bottom:0.75rem; border-left:3px solid var(--status-success-text); background:var(--status-success-bg); color:var(--status-success-text); font-weight:500;">'
            f'{icon_svg("shield", 12)} Gemini API active'
            '</div>',
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            '<div class="kb-banner" style="margin-bottom:0.75rem;">'
            'Demo mode active (Sarah Chen profile loaded)'
            '</div>',
            unsafe_allow_html=True
        )

    st.markdown('<div class="kb-sidebar-section-title">Workflow stages</div>', unsafe_allow_html=True)

    nav_pages = [
        ("connect", "1. Connect Sources"),
        ("reconstruct", "2. Reconstruct"),
        ("employee", "3. Employee Hub"),
        ("review", "4. Manager Review"),
        ("handover", "5. Handover Package"),
    ]
    for page_id, page_label in nav_pages:
        is_active = st.session_state.page == page_id
        if st.button(
            page_label,
            use_container_width=True,
            type="primary" if is_active else "secondary",
            disabled=(page_id in ("reconstruct", "employee", "review", "handover") and
                      st.session_state.knowledge_profile is None and
                      not st.session_state.is_demo)
        ):
            st.session_state.page = page_id
            st.rerun()

    st.markdown('<div class="kb-sidebar-section-title">Interface theme</div>', unsafe_allow_html=True)
    theme_choice = st.radio(
        "Theme mode:",
        ["System", "Light", "Dark"],
        index=["System", "Light", "Dark"].index(st.session_state.get("theme", "System")),
        horizontal=True,
        label_visibility="collapsed",
        key="theme_selector",
    )
    if theme_choice != st.session_state.get("theme"):
        st.session_state.theme = theme_choice
        st.rerun()

    st.markdown('<div class="kb-sidebar-footer">Baton Knowledge Platform<br/>Institutional context preservation</div>', unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 1: CONNECT SOURCES
# ═══════════════════════════════════════════════════════════════════════════════
if st.session_state.page == "connect":
    step_indicator("connect")

    if not st.session_state.api_key:
        st.markdown("""
        <div class="kb-banner">
            <b>Demo mode active:</b> Exploring the 5-stage handover journey with <b>Sarah Chen</b> (PayFlow microservice). All views, verifications, and export packages are functional.
        </div>
        """, unsafe_allow_html=True)

    st.markdown("""
    <div class="kb-banner-tip">
        <b>💡 Why Baton?</b> 70% of vital engineering decisions, vendor quirks, and unwritten operational rules aren't in the README. Baton distills them into a verified, peer-reviewed handover package before teammates move on.
    </div>
    """, unsafe_allow_html=True)

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
        with col_p1:
            employee_name = st.text_input(
                "Departing employee name",
                value=st.session_state.employee_name,
                placeholder="e.g. Sarah Chen",
            )
            st.session_state.employee_name = employee_name

        with col_p2:
            project_role = st.text_input(
                "Role and project scope",
                value=st.session_state.project_role,
                placeholder="e.g. Senior Backend Engineer, PayFlow",
            )
            st.session_state.project_role = project_role

    with col_right:
        emp_display = st.session_state.employee_name.strip() or ("Sarah Chen" if not st.session_state.api_key else "Pending input")
        role_display = st.session_state.project_role.strip() or ("Senior Backend Engineer, PayFlow" if not st.session_state.api_key else "Pending input")
        initials = "".join([part[0] for part in emp_display.split() if part])[:2].upper() if emp_display else "HB"

        file_count = len(st.session_state.uploaded_files) if st.session_state.uploaded_files else 0
        has_gh = bool(st.session_state.github_url.strip())
        text_len = len(st.session_state.pasted_text.strip())

        preview_html = textwrap.dedent(f"""
        <div class="kb-panel">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.9rem;">
                <div style="display:flex; align-items:center; gap:8px;">
                    <span class="kb-avatar-chip" style="width:24px; height:24px; font-size:0.7rem;">{initials}</span>
                    <h3 style="margin:0; font-size:1.0rem; font-weight:600; color:var(--text-primary);">Staged handover dossier</h3>
                </div>
                <span class="badge badge-success">Ready for analysis</span>
            </div>

            <p style="font-size:0.83rem; color:var(--text-secondary); margin-bottom:0.85rem; line-height:1.5;">
                Extracts tacit architectural decisions, production landmines, and undocumented operational context into an actionable package for your successor.
            </p>

            <div class="kb-meta-list">
                <div class="kb-meta-row">
                    <span class="kb-meta-key">Departing Engineer</span>
                    <span class="kb-meta-val">{emp_display}</span>
                </div>
                <div class="kb-meta-row">
                    <span class="kb-meta-key">Project Scope</span>
                    <span class="kb-meta-val">{role_display}</span>
                </div>
                <div class="kb-meta-row">
                    <span class="kb-meta-key">Source Documents</span>
                    <span class="kb-meta-val">{file_count} uploaded</span>
                </div>
                <div class="kb-meta-row">
                    <span class="kb-meta-key">Code Repository</span>
                    <span class="kb-meta-val">{'Connected' if has_gh else 'None'}</span>
                </div>
                <div class="kb-meta-row">
                    <span class="kb-meta-key">Informal Notes</span>
                    <span class="kb-meta-val">{text_len} chars</span>
                </div>
            </div>

            <div style="border-top:1px solid var(--border-color); margin-top:0.85rem; padding-top:0.85rem;">
                <div style="font-size:0.72rem; font-weight:600; color:var(--text-muted); text-transform:uppercase; letter-spacing:0.04em; margin-bottom:0.45rem;">Handover Deliverables</div>
                <div style="font-size:0.82rem; line-height:1.6; color:var(--text-secondary);">
                    • Architectural decision log with citations<br/>
                    • Production risks and dependency landmines<br/>
                    • Employee verification & tribal wisdom addendum<br/>
                    • Multi-role handover dossier (Manager & Successor)
                </div>
            </div>
        </div>
        """)
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
                if total_len > 30000:
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

                st.session_state.all_sources = all_sources

                with st.spinner(f"Reconstructing knowledge graph across {len(all_sources)} source(s)..."):
                    try:
                        from utils.gemini_engine import analyze_sources
                        profile = analyze_sources(all_sources, st.session_state.api_key)
                        st.session_state.knowledge_profile = profile
                        st.session_state.is_demo = False
                        st.session_state.page = "reconstruct"
                        st.rerun()
                    except Exception as e:
                        st.error(f"Gemini analysis error: {_safe_err(e)}")
                        st.info("Check your key at aistudio.google.com")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 2: RECONSTRUCT KNOWLEDGE PROFILE
# ═══════════════════════════════════════════════════════════════════════════════
elif st.session_state.page == "reconstruct":
    step_indicator("reconstruct")

    profile = st.session_state.knowledge_profile
    if not profile:
        st.error("No knowledge profile found. Please start by connecting sources.")
        st.stop()

    if st.session_state.is_demo:
        st.markdown("""
        <div class="kb-banner">
            <b>Demo mode:</b> Displaying AI reconstruction for <b>Sarah Chen</b> (PayFlow microservice). Inspect citations, confidence scores, and identified knowledge gaps below.
        </div>
        """, unsafe_allow_html=True)

    # Executive Hero Banner
    st.markdown(f"""
    <div class="kb-panel-hero">
        <div style="display:flex; justify-content:space-between; align-items:flex-start; flex-wrap:wrap; gap:0.75rem;">
            <div>
                <h2 style="font-size:1.25rem; font-weight:700; color:var(--text-primary); margin:0 0 4px 0;">Reconstructed Knowledge Profile</h2>
                <div style="color:var(--text-secondary); font-size:0.875rem;">
                    <b>Departing:</b> {st.session_state.employee_name or 'Unknown'} &nbsp;|&nbsp;
                    <b>Project Scope:</b> {st.session_state.project_role or 'Unknown'}
                </div>
            </div>
            <span class="badge badge-neutral">Citation-linked</span>
        </div>
        <p style="font-size:0.9rem; line-height:1.6; color:var(--text-primary); margin-top:0.85rem; margin-bottom:0;">
            {profile.get("summary", "")}
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Stat Cards
    st.markdown('<div class="kb-stat-grid">', unsafe_allow_html=True)
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.markdown(render_stat_card("Core Decisions", str(len(profile.get("decisions", []))), "var(--accent)"), unsafe_allow_html=True)
    with c2:
        st.markdown(render_stat_card("Risks & Traps", str(len(profile.get("risks", []))), "var(--status-warning-text)"), unsafe_allow_html=True)
    with c3:
        st.markdown(render_stat_card("Knowledge Gaps", str(len(profile.get("unresolved", []))), "var(--status-danger-text)"), unsafe_allow_html=True)
    with c4:
        st.markdown(render_stat_card("Key Teammates", str(len(profile.get("contacts", []))), "var(--status-success-text)"), unsafe_allow_html=True)
    with c5:
        st.markdown(render_stat_card("Dependencies", str(len(profile.get("dependencies", []))), "#38BDF8"), unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Clean Solid Distribution Bar
    high_count = sum(1 for d in profile.get("decisions", []) if d.get("confidence") == "HIGH")
    med_count = sum(1 for d in profile.get("decisions", []) if d.get("confidence") == "MEDIUM")
    low_count = sum(1 for d in profile.get("decisions", []) if d.get("confidence") == "LOW")
    total_d = max(1, len(profile.get("decisions", [])))
    high_pct = int((high_count / total_d) * 100)
    med_pct = int((med_count / total_d) * 100)
    low_pct = 100 - high_pct - med_pct

    st.markdown(f"""
    <div style="background:var(--bg-subtle); border:1px solid var(--border-color); border-radius:var(--radius); padding:0.9rem 1.2rem; margin-bottom:1.5rem;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.5rem;">
            <span style="font-size:0.8rem; font-weight:600; color:var(--text-secondary);">Evidence confidence breakdown</span>
            <span style="font-size:0.8rem; font-weight:500; color:var(--text-muted);">{high_pct}% High • {med_pct}% Medium • {low_pct}% Inferred</span>
        </div>
        <div style="height:8px; border-radius:var(--radius-sm); display:flex; overflow:hidden; background:var(--border-color);">
            <div style="width:{high_pct}%; background:#16A34A;" title="High confidence: {high_count}"></div>
            <div style="width:{med_pct}%; background:#CA8A04;" title="Medium confidence: {med_count}"></div>
            <div style="width:{low_pct}%; background:#DC2626;" title="Low confidence: {low_count}"></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Content Grid
    col_grid1, col_grid2 = st.columns([1, 1], gap="large")

    with col_grid1:
        st.markdown('<div class="kb-section-title">Architectural Decision Log</div>', unsafe_allow_html=True)
        for i, decision in enumerate(profile.get("decisions", [])):
            conf = decision.get("confidence", "MEDIUM")
            stype = decision.get("source_type", "file")
            with st.expander(f"Decision #{i+1}: {decision.get('text', '')[:75]}...", expanded=(i < 2)):
                st.markdown(f"""
                <div class="kb-card kb-card-info">
                    <p style="font-size:0.95rem; font-weight:600; color:var(--text-primary); margin-bottom:0.5rem;">{decision.get('text', '')}</p>
                    <p>{source_badge(stype)} {confidence_badge(conf)} &nbsp;<span style="color:var(--text-muted); font-size:0.8rem;">Source: {decision.get('source', '')}</span></p>
                </div>
                """, unsafe_allow_html=True)
                excerpt = decision.get("excerpt", "")
                if excerpt:
                    st.markdown(render_citation(decision.get("source", ""), excerpt), unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<div class="kb-section-title">Key Dependencies</div>', unsafe_allow_html=True)
        for dep in profile.get("dependencies", []):
            st.markdown(f"""
            <div class="kb-card">
                <b>{dep.get('item', '')}</b> — {dep.get('description', '')}
                <br/><small style="color:var(--text-muted);">Source citation: {dep.get('source', '')}</small>
            </div>
            """, unsafe_allow_html=True)

    with col_grid2:
        st.markdown('<div class="kb-section-title">Critical Risks and Landmines</div>', unsafe_allow_html=True)
        for j, risk in enumerate(profile.get("risks", [])):
            conf = risk.get("confidence", "MEDIUM")
            card_class = "kb-card-danger" if conf == "HIGH" else "kb-card-warning"
            with st.expander(f"Risk #{j+1}: {risk.get('text', '')[:75]}...", expanded=(j < 2)):
                st.markdown(f"""
                <div class="kb-card {card_class}">
                    <p style="font-size:0.95rem; font-weight:600; color:var(--text-primary); margin-bottom:0.5rem;">{risk.get('text', '')}</p>
                    <p>{confidence_badge(conf)} &nbsp;<span style="color:var(--text-muted); font-size:0.8rem;">Source: {risk.get('source', '')}</span></p>
                </div>
                """, unsafe_allow_html=True)
                excerpt = risk.get("excerpt", "")
                if excerpt:
                    st.markdown(render_citation(risk.get("source", ""), excerpt), unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<div class="kb-section-title">Unresolved Knowledge Gaps</div>', unsafe_allow_html=True)
        for q in profile.get("unresolved", []):
            st.markdown(f"""
            <div class="kb-card kb-card-warning">
                <p style="font-weight:600; color:var(--status-warning-text); margin-bottom:4px;">{q.get('question', '')}</p>
                <p style="color:var(--text-secondary); font-size:0.82rem; margin-bottom:0;">
                    <i>Detection note: {q.get('why_unknown', '')}</i>
                </p>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<div class="kb-section-title">Stakeholders and Key Contacts</div>', unsafe_allow_html=True)
        for contact in profile.get("contacts", []):
            st.markdown(f"""
            <div class="kb-card kb-card-success">
                <div style="font-weight:600; color:var(--text-primary);">{contact.get('name', '')}</div>
                <div style="font-size:0.85rem; color:var(--text-secondary);">{contact.get('role', '')}</div>
                <small style="color:var(--text-muted);">Source: {contact.get('source', '')}</small>
            </div>
            """, unsafe_allow_html=True)

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
    step_indicator("employee")

    profile = st.session_state.knowledge_profile
    if not profile:
        st.error("No knowledge profile found. Please start by connecting sources.")
        st.stop()

    if st.session_state.is_demo:
        st.markdown("""
        <div class="kb-banner">
            <b>Demo mode active:</b> Interacting as <b>Sarah Chen</b>. Pre-populated decision assessments, resolved questions, and critical tribal guidance are loaded.
        </div>
        """, unsafe_allow_html=True)

    employee = st.session_state.employee_name or "Departing Engineer"
    project = st.session_state.project_role or "Key System Contributor"

    st.markdown(f"""
    <div class="kb-panel-hero">
        <h2 style="font-size:1.25rem; font-weight:700; color:var(--text-primary); margin:0 0 4px 0;">Employee Knowledge Hub</h2>
        <div style="color:var(--text-secondary); font-size:0.875rem; margin-bottom:0.6rem;">
            <b>Welcome, {employee}.</b> Verify extracted findings, resolve identified documentation gaps, and record unwritten operational context before departure.
        </div>
        <span class="badge badge-neutral">{project}</span>
    </div>
    """, unsafe_allow_html=True)

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

    st.markdown("""
    <div class="kb-banner-tip">
        <b>💡 Pro-Tip for Departing Engineers:</b> The most invaluable handover knowledge is usually what is unwritten — why a certain design pattern was rejected, vendor rate limits, and who to message during a late-night outage.
    </div>
    """, unsafe_allow_html=True)

    # Stat Cards
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(render_stat_card("Verified Items", f"{verified_count}/{total_verifiable}", "var(--status-success-text)"), unsafe_allow_html=True)
    with c2:
        st.markdown(render_stat_card("Gaps Resolved", f"{gaps_resolved}/{total_gaps}", "var(--accent)"), unsafe_allow_html=True)
    with c3:
        st.markdown(render_stat_card("Tribal Wisdom", str(len(tribal_items)), "var(--status-warning-text)"), unsafe_allow_html=True)
    with c4:
        st.markdown(render_stat_card("Handover Readiness", f"{readiness_score}%", "#10B981"), unsafe_allow_html=True)

    st.progress(readiness_score / 100.0)
    st.markdown("---")

    emp_tab1, emp_tab2, emp_tab3 = st.tabs([
        "1. Verify findings",
        "2. Answer knowledge gaps",
        "3. Share tribal knowledge"
    ])

    with emp_tab1:
        st.markdown('<div class="kb-section-title">Architectural Decisions Verification</div>', unsafe_allow_html=True)
        st.caption("Confirm accuracy or add context explaining the trade-offs that led to each decision.")

        for i, decision in enumerate(decisions):
            conf = decision.get("confidence", "MEDIUM")
            stype = decision.get("source_type", "file")
            d_key = f"decision_{i}"
            saved_verif = st.session_state.employee_verifications.get(d_key, {})
            current_status = saved_verif.get("status", "Confirmed accurate")
            current_note = saved_verif.get("note", "")

            with st.expander(f"Decision #{i+1}: {decision.get('text', '')[:75]}...", expanded=(i == 0)):
                st.markdown(f"""
                <div class="kb-card kb-card-info">
                    <p style="font-size:0.95rem; font-weight:600; color:var(--text-primary); margin-bottom:0.4rem;">{decision.get('text', '')}</p>
                    <p>{source_badge(stype)} {confidence_badge(conf)} &nbsp;<span style="color:var(--text-muted); font-size:0.8rem;">Source: {decision.get('source', '')}</span></p>
                </div>
                """, unsafe_allow_html=True)
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
        st.markdown('<div class="kb-section-title">Critical Risks Verification</div>', unsafe_allow_html=True)
        st.caption("Confirm known risks and specify concrete mitigation steps.")

        for j, risk in enumerate(risks):
            conf = risk.get("confidence", "MEDIUM")
            r_key = f"risk_{j}"
            saved_r_verif = st.session_state.employee_verifications.get(r_key, {})
            current_r_status = saved_r_verif.get("status", "Active risk")
            current_r_note = saved_r_verif.get("note", "")

            with st.expander(f"Risk #{j+1}: {risk.get('text', '')[:75]}...", expanded=(j == 0)):
                card_class = "kb-card-danger" if conf == "HIGH" else "kb-card-warning"
                st.markdown(f"""
                <div class="kb-card {card_class}">
                    <p style="font-size:0.95rem; font-weight:600; color:var(--text-primary); margin-bottom:0.4rem;">{risk.get('text', '')}</p>
                    <p>{confidence_badge(conf)} &nbsp;<span style="color:var(--text-muted); font-size:0.8rem;">Source: {risk.get('source', '')}</span></p>
                </div>
                """, unsafe_allow_html=True)
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
        st.markdown('<div class="kb-section-title">Resolve Knowledge Gaps</div>', unsafe_allow_html=True)
        st.info("Tacit knowledge opportunity: Unanswered questions discovered across codebase and documents. Add the unwritten context before leaving.")

        if unresolved:
            for k, q in enumerate(unresolved):
                q_text = q.get("question", "")
                why = q.get("why_unknown", "")
                existing_ans = st.session_state.employee_gap_answers.get(q_text, "")

                st.markdown(f"""
                <div class="kb-card kb-card-warning">
                    <p style="font-size:0.95rem; font-weight:600; color:var(--status-warning-text); margin-bottom:4px;">Question #{k+1}: {q_text}</p>
                    <p style="color:var(--text-secondary); font-size:0.82rem; margin-bottom:0;"><i>Detection rationale: {why}</i></p>
                </div>
                """, unsafe_allow_html=True)

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
        st.markdown('<div class="kb-section-title">Share Tribal Knowledge and Operational Notes</div>', unsafe_allow_html=True)
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
                    st.session_state.employee_tribal_knowledge.append({
                        "category": category,
                        "title": t_title.strip(),
                        "content": t_content.strip()
                    })
                    st.toast(f"Added: {t_title.strip()}")
                    st.rerun()
                else:
                    st.error("Please provide both a title and description.")

        if st.session_state.employee_tribal_knowledge:
            st.markdown("#### Recorded Tribal Knowledge Items:")
            for idx, item in enumerate(st.session_state.employee_tribal_knowledge):
                cat = item.get("category", "Tip")
                card_class = "kb-card-danger" if cat == "Warning" else ("kb-card-success" if cat == "Contact" else "kb-card")

                c_item, c_del = st.columns([6, 1])
                with c_item:
                    st.markdown(f"""
                    <div class="kb-card {card_class}">
                        <div style="font-weight:600; color:var(--text-primary);">[{cat}] {item.get('title', '')}</div>
                        <p style="font-size:0.875rem; color:var(--text-secondary); margin-top:4px; margin-bottom:0;">{item.get('content', '')}</p>
                    </div>
                    """, unsafe_allow_html=True)
                with c_del:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("Remove", key=f"del_tk_{idx}"):
                        st.session_state.employee_tribal_knowledge.pop(idx)
                        st.rerun()

    st.markdown("---")
    col_nav1, col_nav2 = st.columns([2, 1])
    with col_nav1:
        if st.button("Proceed to manager review", type="primary", use_container_width=True):
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
    step_indicator("review")

    profile = st.session_state.knowledge_profile
    if not profile:
        st.error("No knowledge profile found. Please start by connecting sources.")
        st.stop()

    if st.session_state.is_demo:
        st.markdown("""
        <div class="kb-banner">
            <b>Demo mode active:</b> Review and sign off on each section to unlock the multi-perspective handover package.
        </div>
        """, unsafe_allow_html=True)

    st.markdown("""
    <div class="kb-panel-hero">
        <h2 style="font-size:1.25rem; font-weight:700; color:var(--text-primary); margin:0 0 4px 0;">Manager Review and Executive Sign-Off</h2>
        <div style="color:var(--text-secondary); font-size:0.875rem;">
            Inspect verified findings, employee gap resolutions, and tribal knowledge. Add managerial follow-ups, then approve each section.
        </div>
    </div>
    """, unsafe_allow_html=True)

    sections = [
        ("decisions", "Decision Log", profile.get("decisions", [])),
        ("risks", "Risks and Dependencies", profile.get("risks", [])),
        ("unresolved", "Resolved and Open Questions", profile.get("unresolved", [])),
        ("tribal", "Tribal Knowledge and Constraints", st.session_state.employee_tribal_knowledge),
        ("contacts", "Key Contacts and Ownership", profile.get("contacts", [])),
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
                    st.session_state.approvals[section_id] = True
                    st.session_state.action_history.append({
                        "who": "Manager",
                        "action": f"Approved {section_title}",
                        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                        "reason": st.session_state.corrections.get(section_id, "Approved") or "Approved"
                    })
                    st.rerun()

            with btn_rej_col:
                if st.button("Reject section", key=f"btn_rej_{section_id}", use_container_width=True):
                    rej_text = st.session_state.get(f"rej_reason_{section_id}", "").strip() or "Rejected by manager"
                    st.session_state.approvals[section_id] = "rejected"
                    st.session_state.action_history.append({
                        "who": "Manager",
                        "action": f"Rejected {section_title}",
                        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                        "reason": rej_text
                    })
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
            audit_html = '<div style="border:1px solid var(--border-color); border-radius:var(--radius); overflow:hidden;">'
            for entry in reversed(st.session_state.action_history):
                audit_html += render_audit_entry(entry)
            audit_html += "</div>"
            st.markdown(audit_html, unsafe_allow_html=True)
        else:
            st.caption("No review actions recorded yet.")

    approved_count = sum(1 for v in st.session_state.approvals.values() if v is True)
    total_sections = len(sections)

    st.markdown(f"""
    <div class="kb-approval-progress">
        <span class="kb-approval-progress-label">Approval progress</span>
        <span class="kb-approval-progress-count">{approved_count} / {total_sections}</span>
    </div>
    """, unsafe_allow_html=True)
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
                if st.session_state.is_demo:
                    st.session_state.employee_handover = DEMO_EMPLOYEE_HANDOVER
                    st.session_state.page = "handover"
                    st.rerun()
                else:
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
                            st.session_state.employee_handover = DEMO_EMPLOYEE_HANDOVER

                    st.session_state.page = "handover"
                    st.rerun()

    with col_gen2:
        if st.button("Back to employee hub", use_container_width=True):
            st.session_state.page = "employee"
            st.rerun()

    if btn_disabled:
        st.caption("Sign off on all sections above to unlock handover generation.")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 5: FINAL HANDOVER PACKAGE
# ═══════════════════════════════════════════════════════════════════════════════
elif st.session_state.page == "handover":
    step_indicator("handover")

    if not st.session_state.manager_handover or not st.session_state.newhire_handover:
        st.error("Handover documents not yet generated. Please complete Review first.")
        if st.button("Back to manager review"):
            st.session_state.page = "review"
            st.rerun()
        st.stop()

    if st.session_state.is_demo:
        st.markdown("""
        <div class="kb-banner">
            <b>Demo mode:</b> Displaying finalized handover documents for <b>Sarah Chen</b> (PayFlow). Ready for Markdown export.
        </div>
        """, unsafe_allow_html=True)

    employee = st.session_state.employee_name or "Departing Engineer"
    project = st.session_state.project_role or "Key System Contributor"
    initials = "".join([part[0] for part in employee.split() if part])[:2].upper() if employee else "HB"

    header_html = textwrap.dedent(f"""
    <div class="kb-panel-hero">
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:0.5rem;">
            <div style="display:flex; align-items:center; gap:10px;">
                <span class="kb-avatar-chip" style="width:28px; height:28px; font-size:0.78rem;">{initials}</span>
                <div>
                    <h2 style="font-size:1.25rem; font-weight:700; color:var(--text-primary); margin:0 0 2px 0;">Handover Package Finalized</h2>
                    <div style="font-size:0.875rem; color:var(--text-secondary);">
                        All sections reviewed, enriched with employee context, and approved by management.
                    </div>
                </div>
            </div>
            <span class="badge badge-success">{icon_svg("check", 12)} Audited and approved</span>
        </div>
        <div style="margin-top:0.85rem; font-size:0.85rem; color:var(--text-muted);">
            <b>Knowledge holder:</b> {employee} &nbsp;|&nbsp; <b>Scope:</b> {project}
        </div>
    </div>
    """)
    st.markdown(header_html, unsafe_allow_html=True)

    role_col1, role_col2 = st.columns([3, 1])
    with role_col1:
        current_role_idx = ["Manager", "Technical Successor", "Employee"].index(st.session_state.get("view_role", "Manager")) if st.session_state.get("view_role") in ["Manager", "Technical Successor", "Employee"] else 0
        selected_role = st.selectbox(
            "View handover perspective as:",
            ["Manager", "Technical Successor", "Employee"],
            index=current_role_idx,
            key="handover_view_role"
        )
        st.session_state.view_role = selected_role
    with role_col2:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(
            f'<div style="text-align:right;"><span class="badge badge-neutral" style="font-size:0.8rem; padding:6px 12px;">{icon_svg("shield", 12)} Role perspective: {selected_role}</span></div>',
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
                    st.session_state.acknowledgement = {
                        "name": confirmed_name,
                        "time": time.strftime("%Y-%m-%d %H:%M:%S")
                    }
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
        raw_employee = st.session_state.employee_handover or DEMO_EMPLOYEE_HANDOVER
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
            for key in ["knowledge_profile", "is_demo", "approvals", "corrections",
                        "manager_handover", "newhire_handover", "employee_handover",
                        "employee_verifications", "employee_gap_answers", "employee_tribal_knowledge",
                        "all_sources", "employee_name", "project_role", "github_url", "github_token",
                        "pasted_text", "uploaded_files", "action_history", "acknowledgement"]:
                if "approvals" in key or "corrections" in key or "verifications" in key or "gap_answers" in key:
                    st.session_state[key] = {}
                elif "sources" in key or "tribal_knowledge" in key or "history" in key:
                    st.session_state[key] = []
                elif key in ("uploaded_files", "acknowledgement"):
                    st.session_state[key] = None
                elif key == "is_demo":
                    st.session_state[key] = False
                else:
                    st.session_state[key] = ""
            st.session_state.view_role = "Manager"
            st.session_state.page = "connect"
            st.rerun()

    with col_reset2:
        if st.button("Back to manager review", use_container_width=True):
            st.session_state.page = "review"
            st.rerun()
