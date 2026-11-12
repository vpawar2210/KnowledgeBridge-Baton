"""Shared project state persistence for Baton.

Saves and loads all project state from data/project_state.json.
Gracefully handles missing or corrupted state files with empty state fallbacks.
"""

from pathlib import Path
import json
import time
from typing import Dict, Any, Tuple, Optional


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
STATE_FILE = DATA_DIR / "project_state.json"

PROJECT_KEYS = [
    "knowledge_profile",
    "employee_name",
    "project_role",
    "employee_verifications",
    "employee_gap_answers",
    "employee_tribal_knowledge",
    "approvals",
    "corrections",
    "manager_handover",
    "newhire_handover",
    "employee_handover",
    "action_history",
    "acknowledgement",
    "all_sources",
    "analyses_run",
    "handovers_run",
]


def ensure_data_dir() -> Path:
    """Ensure data/ directory exists using pathlib."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR


def get_empty_state() -> Dict[str, Any]:
    """Return a pristine empty project state."""
    return {
        "knowledge_profile": None,
        "employee_name": "",
        "project_role": "",
        "employee_verifications": {},
        "employee_gap_answers": {},
        "employee_tribal_knowledge": [],
        "approvals": {},
        "corrections": {},
        "manager_handover": None,
        "newhire_handover": None,
        "employee_handover": None,
        "action_history": [],
        "acknowledgement": None,
        "all_sources": [],
        "analyses_run": 0,
        "handovers_run": 0,
    }


def get_seed_state() -> Dict[str, Any]:
    """Return initial synthetic project state for PayFlow / Sarah Chen evaluation."""
    return {
        "employee_name": "Sarah Chen",
        "project_role": "Senior Backend Engineer • PayFlow",
        "knowledge_profile": {
            "summary": (
                "Sarah Chen served as Senior Backend Engineer on PayFlow for 3 years, "
                "architecting the core payment processing microservice. Key decisions include "
                "the PostgreSQL over MongoDB choice, the circuit breaker pattern, and the "
                "Stripe SDK integration. Critical risks include a pending database migration "
                "and an expiring vendor contract with DataVerify Inc."
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
                }
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
                }
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
                }
            ],
            "contacts": [
                {"name": "Marcus Rivera", "role": "DevOps lead — owns Kubernetes cluster and CI/CD pipeline", "source": "Handover Notes"},
                {"name": "Priya Sharma", "role": "Product Manager — owns roadmap and stakeholder communication", "source": "Handover Notes"},
                {"name": "James Whitfield", "role": "DataVerify Inc. vendor contact (james@dataverify.io) — for contract renewal", "source": "architecture_notes.md"}
            ],
            "dependencies": [
                {"item": "Stripe", "description": "Payment gateway SDK. All card processing routes through Stripe.", "source": "architecture_notes.md"},
                {"item": "Kafka (Confluent Cloud)", "description": "Async messaging for payment events.", "source": "owner/payflow/README"},
                {"item": "DataVerify Inc.", "description": "Identity verification vendor. Contract expires Dec 31.", "source": "architecture_notes.md"}
            ]
        },
        "all_sources": [
            {"name": "architecture_notes.md", "type": "file", "content": "PayFlow architecture documentation..."},
            {"name": "owner/payflow/README", "type": "github", "content": "PayFlow repository readme..."},
            {"name": "Handover Notes", "type": "text", "content": "Departing notes from Sarah Chen..."}
        ],
        "employee_verifications": {},
        "employee_gap_answers": {},
        "employee_tribal_knowledge": [],
        "approvals": {},
        "corrections": {},
        "manager_handover": None,
        "newhire_handover": None,
        "employee_handover": None,
        "action_history": [],
        "acknowledgement": None,
        "analyses_run": 1,
        "handovers_run": 0,
    }


def load_project_state() -> Tuple[Dict[str, Any], Optional[str]]:
    """Load project state from disk.
    
    Returns (state_dict, notice_message).
    If file is missing or corrupted, returns (empty_state, notice).
    """
    ensure_data_dir()
    if not STATE_FILE.exists():
        return get_empty_state(), "No saved project state found. Starting with empty state."

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return get_empty_state(), "Project state file was corrupted. Starting with empty state."
        # Ensure all standard keys exist
        empty = get_empty_state()
        for k, v in empty.items():
            if k not in data:
                data[k] = v
        return data, None
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return get_empty_state(), "Project state file was corrupted. Starting with empty state."


def save_project_state(source) -> bool:
    """Save project state keys from session_state or dict to data/project_state.json.
    
    Returns True if successfully written, False otherwise.
    """
    ensure_data_dir()
    data_to_save = {}
    for key in PROJECT_KEYS:
        if hasattr(source, "get"):
            val = source.get(key)
        elif hasattr(source, "__getitem__"):
            try:
                val = source[key]
            except KeyError:
                val = None
        else:
            val = getattr(source, key, None)
        data_to_save[key] = val

    try:
        temp_file = STATE_FILE.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data_to_save, f, indent=2, default=str)
        temp_file.replace(STATE_FILE)
        return True
    except Exception:
        return False


def load_into_session(session_state) -> Optional[str]:
    """Load disk state into Streamlit session_state. Returns notice string if any."""
    data, notice = load_project_state()
    for key, val in data.items():
        session_state[key] = val
    return notice


def log_audit_entry(session_state, who: str, action: str, reason: str = ""):
    """Append a structured audit log entry to action_history and persist immediately."""
    entry = {
        "who": who,
        "action": action,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "reason": reason,
    }
    if "action_history" not in session_state or not isinstance(session_state.action_history, list):
        session_state.action_history = []
    session_state.action_history.append(entry)
    save_project_state(session_state)

