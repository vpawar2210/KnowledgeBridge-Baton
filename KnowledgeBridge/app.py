"""
🏃‍♂️ Baton — Knowledge Handover Platform
Merged Style A (Premium SaaS) + Style B (Bold Plum & Tool Identity)
"""

import copy
import json
import time
import streamlit as st

# ─── Page config (must be first Streamlit call) ───────────────────────────────
st.set_page_config(
    page_title="Baton — Knowledge Handover Platform",
    page_icon="🏃‍♂️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── GLOBAL DESIGN SYSTEM & TOKENS ───────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

:root {
    --color-plum: #29102F;
    --color-plum-secondary: #3B1744;
    --color-plum-tint: rgba(41, 16, 47, 0.06);
    --color-bg: #EDF2F5;
    --color-white: #FFFFFF;
    --color-orange: #F49B54;
    --color-orange-hover: #E68B40;
    --color-blue: #245BEA;
    --color-blue-hover: #1A47C2;
    --color-blue-light: #EEF4FF;
    --color-text: #242428;
    --color-text-secondary: #64748B;
    --color-text-muted: #94A3B8;
    --color-border: #DCE2E8;
    --color-border-light: #F1F5F9;

    --color-success: #059669;
    --color-success-bg: #ECFDF5;
    --color-warning: #D97706;
    --color-warning-bg: #FFFBEB;
    --color-error: #DC2626;
    --color-error-bg: #FEF2F2;

    --radius-sm: 8px;
    --radius-md: 12px;
    --radius-lg: 16px;
    --radius-xl: 20px;
    --radius-2xl: 28px;
    --radius-pill: 9999px;

    --shadow-subtle: 0 1px 3px rgba(36, 36, 40, 0.04), 0 1px 2px rgba(36, 36, 40, 0.02);
    --shadow-card: 0 4px 16px -2px rgba(36, 36, 40, 0.06), 0 2px 6px -1px rgba(36, 36, 40, 0.04);
    --shadow-container: 0 14px 34px -4px rgba(41, 16, 47, 0.07), 0 4px 12px -2px rgba(41, 16, 47, 0.03);
    --transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
}

/* Global resets & typography */
html, body, [data-testid="stAppViewContainer"] {
    font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif !important;
    background-color: var(--color-bg) !important;
    color: var(--color-text) !important;
}

[data-testid="stHeader"] {
    background: transparent !important;
}

/* Style A: Large rounded outer container */
.main .block-container {
    max-width: 1260px !important;
    padding: 2.2rem 2.6rem 3.2rem 2.6rem !important;
    background-color: var(--color-white) !important;
    border-radius: var(--radius-2xl) !important;
    border: 1px solid var(--color-border) !important;
    box-shadow: var(--shadow-container) !important;
    margin-top: 1.25rem !important;
    margin-bottom: 2rem !important;
}

/* Top Navigation Bar */
.kb-top-navbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.9rem 1.5rem;
    background: var(--color-white);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-xl);
    box-shadow: var(--shadow-subtle);
    margin-bottom: 1.75rem;
    gap: 1rem;
    flex-wrap: wrap;
}
.kb-nav-brand {
    display: flex;
    align-items: center;
    gap: 0.65rem;
}
.kb-brand-icon {
    width: 38px;
    height: 38px;
    border-radius: var(--radius-md);
    background: linear-gradient(135deg, var(--color-plum), var(--color-plum-secondary));
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.25rem;
    box-shadow: 0 2px 8px rgba(41, 16, 47, 0.25);
}
.kb-brand-title {
    font-size: 1.25rem;
    font-weight: 800;
    color: var(--color-plum);
    letter-spacing: -0.02em;
}
.kb-brand-pill {
    background: var(--color-plum-tint);
    color: var(--color-plum);
    font-size: 0.72rem;
    font-weight: 700;
    padding: 3px 9px;
    border-radius: var(--radius-pill);
    margin-left: 4px;
}
.kb-nav-steps {
    display: flex;
    align-items: center;
    gap: 0.35rem;
}
.kb-nav-step-item {
    font-size: 0.84rem;
    font-weight: 600;
    color: var(--color-text-secondary);
    padding: 6px 14px;
    border-radius: var(--radius-pill);
    transition: var(--transition);
}
.kb-nav-step-item.active {
    background: var(--color-blue);
    color: #FFFFFF !important;
    box-shadow: 0 2px 8px rgba(36, 91, 234, 0.3);
}
.kb-nav-step-item.done {
    background: var(--color-success-bg);
    color: var(--color-success);
}
.kb-nav-arrow {
    color: var(--color-border);
    font-size: 0.8rem;
    margin: 0 2px;
}
.kb-nav-status-pill {
    background: var(--color-plum);
    color: #FFFFFF;
    padding: 6px 14px;
    border-radius: var(--radius-pill);
    font-size: 0.78rem;
    font-weight: 700;
    letter-spacing: 0.02em;
    box-shadow: 0 2px 6px rgba(41, 16, 47, 0.2);
}

/* Sidebar: Deep Plum Identity & Blue Active Pill */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, var(--color-plum) 0%, var(--color-plum-secondary) 100%) !important;
    border-right: 1px solid rgba(255, 255, 255, 0.08) !important;
}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] span,
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] strong,
[data-testid="stSidebar"] label {
    color: #F8FAFC !important;
}
[data-testid="stSidebar"] .stButton > button {
    background: rgba(255, 255, 255, 0.06) !important;
    color: #E2E8F0 !important;
    border: 1px solid rgba(255, 255, 255, 0.08) !important;
    border-radius: var(--radius-pill) !important;
    font-weight: 600 !important;
    font-size: 0.88rem !important;
    text-align: left !important;
    padding: 0.55rem 1.15rem !important;
    transition: var(--transition) !important;
}
[data-testid="stSidebar"] .stButton > button:hover {
    background: rgba(255, 255, 255, 0.14) !important;
    color: #FFFFFF !important;
    border-color: rgba(255, 255, 255, 0.25) !important;
    transform: translateY(-1px);
}
[data-testid="stSidebar"] .stButton > button[kind="primary"] {
    background: var(--color-blue) !important;
    color: #FFFFFF !important;
    border: none !important;
    font-weight: 700 !important;
    box-shadow: 0 4px 14px rgba(36, 91, 234, 0.45) !important;
}

/* Stat Cards (Style A) */
.kb-stat-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
    gap: 1rem;
    margin: 1.25rem 0 1.75rem 0;
}
.kb-stat-card {
    background: var(--color-white);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    padding: 1.1rem 1.25rem;
    display: flex;
    align-items: center;
    gap: 1rem;
    box-shadow: var(--shadow-subtle);
    transition: var(--transition);
}
.kb-stat-card:hover {
    transform: translateY(-2px);
    box-shadow: var(--shadow-card);
    border-color: #CBD5E1;
}
.kb-stat-icon-chip {
    width: 44px;
    height: 44px;
    border-radius: var(--radius-md);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.3rem;
    flex-shrink: 0;
}
.kb-stat-label {
    font-size: 0.74rem;
    font-weight: 700;
    color: var(--color-text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 2px;
}
.kb-stat-number {
    font-size: 1.65rem;
    font-weight: 800;
    color: var(--color-text);
    line-height: 1.1;
    letter-spacing: -0.02em;
}

/* Split-Panel Containers (Style B) */
.kb-panel-white {
    background: var(--color-white);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-xl);
    padding: 1.75rem 2rem;
    box-shadow: var(--shadow-card);
}
.kb-panel-plum {
    background: linear-gradient(150deg, var(--color-plum) 0%, var(--color-plum-secondary) 100%);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: var(--radius-xl);
    padding: 1.75rem 2rem;
    color: #F8FAFC;
    box-shadow: var(--shadow-container);
}
.kb-panel-plum h1, .kb-panel-plum h2, .kb-panel-plum h3, .kb-panel-plum h4 {
    color: #FFFFFF !important;
}
.kb-panel-plum p, .kb-panel-plum span {
    color: #E2E8F0 !important;
}

/* Numbered Steps Header */
.kb-step-badge {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    background: var(--color-blue);
    color: #FFFFFF;
    border-radius: var(--radius-pill);
    font-size: 0.85rem;
    font-weight: 700;
    margin-right: 0.55rem;
    vertical-align: middle;
}
.kb-section-title {
    font-size: 1.25rem;
    font-weight: 700;
    color: var(--color-text);
    display: flex;
    align-items: center;
    margin-bottom: 1rem;
    letter-spacing: -0.01em;
}

/* Cards & Accents */
.kb-card {
    background: var(--color-white);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    padding: 1.25rem 1.5rem;
    margin-bottom: 1rem;
    box-shadow: var(--shadow-subtle);
    transition: var(--transition);
}
.kb-card:hover {
    box-shadow: var(--shadow-card);
}
.kb-card-hero {
    background: linear-gradient(135deg, #FFFFFF 0%, #F8FAFC 100%);
    border: 1px solid var(--color-border);
    border-left: 5px solid var(--color-plum);
    border-radius: var(--radius-xl);
    padding: 1.5rem 1.75rem;
    margin-bottom: 1.5rem;
    box-shadow: var(--shadow-subtle);
}
.kb-card-blue-tint {
    background: #F8FAFC;
    border-left: 4px solid var(--color-blue);
}
.kb-card-orange-tint {
    background: #FFFAF5;
    border-left: 4px solid var(--color-orange);
}
.kb-card-green-tint {
    background: #F7FDF9;
    border-left: 4px solid var(--color-success);
}
.kb-card-red-tint {
    background: #FEF8F8;
    border-left: 4px solid var(--color-error);
}

/* Badges */
.badge {
    display: inline-flex;
    align-items: center;
    padding: 3px 11px;
    border-radius: var(--radius-pill);
    font-size: 0.74rem;
    font-weight: 700;
    margin-right: 6px;
    letter-spacing: 0.02em;
}
.badge-file   { background: #EFF6FF; color: #1D4ED8; border: 1px solid #DBEAFE; }
.badge-github { background: #F1F5F9; color: #334155; border: 1px solid #E2E8F0; }
.badge-text   { background: #FAF5FF; color: #7E22CE; border: 1px solid #F3E8FF; }
.badge-high   { background: var(--color-success-bg); color: var(--color-success); border: 1px solid rgba(5, 150, 105, 0.2); }
.badge-medium { background: var(--color-warning-bg); color: var(--color-warning); border: 1px solid rgba(217, 119, 6, 0.2); }
.badge-low    { background: var(--color-error-bg); color: var(--color-error); border: 1px solid rgba(220, 38, 38, 0.2); }

/* Buttons: Primary Warm Orange #F49B54 with AAA Contrast #1E1B26 */
button[kind="primary"] {
    background-color: var(--color-orange) !important;
    color: #1E1B26 !important;
    border: none !important;
    border-radius: var(--radius-pill) !important;
    font-weight: 700 !important;
    font-size: 0.95rem !important;
    padding: 0.65rem 1.6rem !important;
    box-shadow: 0 4px 14px rgba(244, 155, 84, 0.35) !important;
    transition: var(--transition) !important;
}
button[kind="primary"]:hover {
    background-color: var(--color-orange-hover) !important;
    color: #1E1B26 !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 6px 18px rgba(244, 155, 84, 0.45) !important;
}
button[kind="primary"]:focus-visible {
    outline: 2px solid var(--color-blue) !important;
    outline-offset: 2px !important;
}

/* Secondary Button: Clean White with subtle border */
button[kind="secondary"] {
    background-color: var(--color-white) !important;
    color: var(--color-text) !important;
    border: 1px solid var(--color-border) !important;
    border-radius: var(--radius-pill) !important;
    font-weight: 600 !important;
    font-size: 0.9rem !important;
    padding: 0.6rem 1.35rem !important;
    box-shadow: var(--shadow-subtle) !important;
    transition: var(--transition) !important;
}
button[kind="secondary"]:hover {
    border-color: var(--color-blue) !important;
    color: var(--color-blue) !important;
    background-color: var(--color-blue-light) !important;
    transform: translateY(-1px) !important;
}

/* Inputs, Textareas, Selects */
div[data-baseweb="input"] > div,
div[data-baseweb="textarea"] > div,
div[data-baseweb="select"] > div {
    background-color: var(--color-white) !important;
    border: 1px solid var(--color-border) !important;
    border-radius: var(--radius-md) !important;
    color: var(--color-text) !important;
    box-shadow: var(--shadow-subtle) !important;
    transition: var(--transition) !important;
}
div[data-baseweb="input"] > div:focus-within,
div[data-baseweb="textarea"] > div:focus-within,
div[data-baseweb="select"] > div:focus-within {
    border-color: var(--color-blue) !important;
    box-shadow: 0 0 0 3px rgba(36, 91, 234, 0.15) !important;
}

/* Tabs */
button[data-baseweb="tab"] {
    font-family: 'Plus Jakarta Sans', sans-serif !important;
    font-weight: 600 !important;
    color: var(--color-text-secondary) !important;
    border-radius: var(--radius-pill) !important;
    padding: 0.5rem 1.1rem !important;
    transition: var(--transition) !important;
}
button[data-baseweb="tab"][aria-selected="true"] {
    color: var(--color-blue) !important;
    background-color: var(--color-blue-light) !important;
}

/* Expanders */
div[data-testid="stExpander"] {
    background: var(--color-white) !important;
    border: 1px solid var(--color-border) !important;
    border-radius: var(--radius-lg) !important;
    box-shadow: var(--shadow-subtle) !important;
    margin-bottom: 0.75rem !important;
}

/* Banners */
.kb-banner-demo {
    background: linear-gradient(90deg, #F8FAFC, #EEF4FF);
    border: 1px solid #BFDBFE;
    border-radius: var(--radius-md);
    padding: 12px 18px;
    margin-bottom: 1.5rem;
    font-size: 0.9rem;
    color: #1E3A8A;
}
.kb-plum-pill-item {
    background: rgba(255, 255, 255, 0.1);
    border: 1px solid rgba(255, 255, 255, 0.16);
    border-radius: var(--radius-md);
    padding: 10px 14px;
    margin-bottom: 0.6rem;
    font-size: 0.88rem;
    color: #F1F5F9;
}

/* Progress Bar */
.stProgress > div > div > div > div {
    background-color: var(--color-blue) !important;
    border-radius: var(--radius-pill) !important;
}
</style>
""", unsafe_allow_html=True)


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
            "text": "🚨 PostgreSQL schema migration v2.4 is INCOMPLETE — 3 tables need column additions before Q1 deadline.",
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

DEMO_MANAGER_HANDOVER = """# 👔 Manager Handover — PayFlow Project
### Departing: Sarah Chen | Senior Backend Engineer

---

## Executive Summary
PayFlow is a production-grade payment processing microservice processing thousands of transactions daily. Sarah Chen, its primary architect and engineer for 3 years, is departing. This handover identifies **two critical time-sensitive risks** requiring immediate management action before her last day.

## Key Decisions & Rationale
| Decision | Business Impact |
|----------|----------------|
| PostgreSQL for transactions | ACID compliance — critical for financial audit trails |
| Stripe SDK integration | PCI-DSS compliance — avoids costly card data liability |
| Circuit Breaker pattern | Resilience — payment gateway outages don't cascade |
| Event-driven (Kafka) | Scale — async processing supports 10x transaction growth |

## ⚠️ Critical Risks — Act Now
1. **🚨 Database Migration Incomplete** — v2.4 schema changes must be completed before Q1. Requires a 4-hour maintenance window and DBA oversight. Assign immediately.
2. **🚨 Vendor Contract Expiring Dec 31** — DataVerify Inc. identity verification contract auto-renewal was disabled. Contact James Whitfield (james@dataverify.io) this week.
3. **⚠️ Redis Failover Undocumented** — If the caching layer fails, rate limiting breaks. Ask DevOps (Marcus Rivera) to document the runbook.

## Ownership & Contacts
- **Marcus Rivera** — DevOps, Kubernetes, CI/CD (first call for infra issues)
- **Priya Sharma** — Product Manager, roadmap owner, stakeholder communication
- **James Whitfield** — DataVerify vendor, contract renewal (external)

## External Dependencies
| Vendor/Service | Criticality | Action Required |
|---------------|-------------|-----------------|
| Stripe | 🔴 Critical | Monitor SDK updates |
| DataVerify Inc. | 🔴 Critical | Renew contract before Dec 31 |
| Confluent Kafka | 🟡 High | Check Confluent Cloud billing |
| AWS ElastiCache (Redis) | 🟡 High | Document failover procedure |

## Open Items Requiring Management Action
- [ ] Assign engineer to complete DB migration v2.4
- [ ] Renew DataVerify contract (deadline: Dec 31)
- [ ] Confirm mobile team's dependency on legacy endpoint
- [ ] Hire/assign Redis failover runbook owner
- [ ] Schedule 1:1 knowledge transfer sessions with Marcus Rivera
"""

DEMO_NEWHIRE_HANDOVER = """# 👩‍💻 New Hire Handover — PayFlow Technical Guide
### From: Sarah Chen | To: Her Successor

---

## Welcome & Context
Welcome to PayFlow. You're inheriting a 3-year-old payment microservice that processes real money for real merchants. It works, it's battle-tested, but there are land mines. Read this document carefully before touching anything in production.

## Architecture & Technical Decisions

### Why PostgreSQL (not MongoDB)?
We evaluated MongoDB in 2021. The eventual consistency model is a **hard no** for a financial ledger. Every payment record needs ACID guarantees. If someone ever suggests switching to MongoDB again, show them Issue #3 in the repo.

### Circuit Breaker Pattern
`PaymentGatewayService.java` uses resilience4j. The thresholds (50% failure rate, 10s half-open window) were tuned over 6 months. **Don't change them without load testing.**

### Kafka Topics
```
payflow.payment.completed   → triggers email/SMS notifications
payflow.payment.failed      → triggers retry logic and alerts
payflow.refund.initiated    → triggers refund workflow
```
Credentials: AWS Secrets Manager → `/payflow/kafka/`

### Stripe Integration
We use the Stripe SDK deliberately. **NEVER** store raw card data. NEVER bypass the SDK for "efficiency." This is a legal/compliance decision, not a technical preference.

## 💡 What NOT To Break

| Thing | Why It Matters |
|-------|---------------|
| `/v1/legacy-payments` endpoint | Mobile team MAY depend on it. Confirm before deprecating. |
| PostgreSQL migration v2.4 | Incomplete. Run in staging FIRST with a DBA. |
| Rate limiter config | 1000 req/min per merchant. Changing this needs product sign-off. |
| Blue/green deploy selector | Wrong label = traffic to wrong version. Double-check k8s manifests. |

## 👥 Who To Call
- **Marcus Rivera** — Any infra/Kubernetes/deployment issue. Very responsive on Slack (#devops).
- **Priya Sharma** — Any product/roadmap/merchant escalation. She knows every merchant's quirks.
- **James Whitfield** (james@dataverify.io) — External. Only for DataVerify KYC API issues. Contract expires Dec 31 — make sure your manager knows.

## ⚠️ Unresolved Technical Debt

1. **Redis failover** — There's no runbook. If ElastiCache primary fails, the rate limiter breaks. Talk to Marcus about documenting this.
2. **Redis cache invalidation** — The session token TTL strategy was only ever discussed verbally. Check with the infrastructure team.
3. **DR RTO/RPO** — Referenced in commit messages but I never finished the DR doc. This needs to be written before the next compliance audit.

## 🔗 External Dependencies & Integration Points
- **Stripe Dashboard**: `https://dashboard.stripe.com` — webhook logs are your best friend for debugging payment failures
- **Confluent Cloud**: Kafka cluster monitoring — check consumer lag if notifications are delayed
- **DataVerify API docs**: Ask James Whitfield for the latest Postman collection
- **AWS Secrets Manager**: All credentials live here. Never hardcode secrets.

## Things That Were Tried (Save Yourself The Time)
- ❌ **MongoDB** — Tried in 2021. ACID issues. Abandoned.
- ❌ **Direct Stripe API calls** (without SDK) — PCI compliance nightmare. Never again.
- ❌ **Synchronous notification delivery** — Caused payment endpoint timeouts at scale. Kafka async is the fix.
- ❌ **Redis Cluster mode** — ElastiCache cluster mode had network partition issues in our VPC config. Switched to Replication Group (non-cluster mode).

## Getting Started Checklist
- [ ] Get AWS IAM access (Marcus Rivera sets this up)
- [ ] Get added to `#payflow-alerts` and `#payflow-oncall` Slack channels
- [ ] Run the service locally using `docker-compose up` (see /docs/local-setup.md)
- [ ] Read `/db/migrations/v2.4/` migration scripts — understand what's pending
- [ ] Talk to Priya Sharma about the Q1 roadmap
- [ ] Confirm with mobile team: are they using `/v1/legacy-payments`?
- [ ] Set up PagerDuty alerts (ask Marcus)
"""

DEMO_EMPLOYEE_GAP_ANSWERS = {
    "What is the Redis cache invalidation strategy for user session tokens?": (
        "We use a TTL-based approach: session tokens expire after 30 minutes of inactivity. "
        "On every authenticated request, the TTL is refreshed. If a user explicitly logs out, "
        "we delete the key immediately. There's also a daily cleanup cron that sweeps orphaned keys. "
        "Marcus Rivera and I discussed this over Slack in March 2023 — the infra team preferred "
        "passive expiry over active invalidation for simplicity."
    ),
    "Is the mobile team actually calling /v1/legacy-payments in production?": (
        "YES — I checked the API gateway logs in August and saw ~200 req/day from the mobile app's "
        "user-agent hitting /v1/legacy-payments. I told their lead (Dev Kapoor) about deprecation "
        "plans and he said they'd migrate to v2, but I never got a timeline. DO NOT deprecate "
        "without confirming with Dev first. His Slack handle is @dev.kapoor."
    ),
    "What is the disaster recovery RTO/RPO for PayFlow?": (
        "Unofficial targets are RTO=1hr, RPO=15min based on a conversation with our VP of Engineering "
        "in Q2 2023. We never formalized this in writing. The PostgreSQL backups run every 15 minutes "
        "via AWS RDS automated snapshots. Redis is NOT backed up — it's treated as ephemeral. "
        "If you lose Redis, you lose active sessions and rate limiter state, but no financial data."
    ),
}

DEMO_EMPLOYEE_TRIBAL_KNOWLEDGE = [
    {
        "category": "Warning",
        "title": "Never deploy on Fridays or month-end",
        "content": (
            "Merchant transaction volume spikes 3x on the last 3 days of every month. "
            "I learned this the hard way in June 2022 when a deploy caused a 12-minute outage "
            "during peak processing. We lost $8K in failed transactions. The SRE team now has "
            "a soft freeze policy, but it's not enforced by CI/CD. Be careful."
        ),
    },
    {
        "category": "Tip",
        "title": "Stripe webhook debugging shortcut",
        "content": (
            "When payment webhooks fail silently, don't dig through CloudWatch first. Go to "
            "Stripe Dashboard → Developers → Webhooks → click the event → check the response code. "
            "90% of the time it's a 401 because someone rotated the webhook signing secret in AWS "
            "Secrets Manager but forgot to update the Stripe dashboard. Takes 2 minutes vs 2 hours."
        ),
    },
    {
        "category": "Process",
        "title": "How to handle PCI compliance audits",
        "content": (
            "The annual PCI audit happens in March. The auditor (ComplianceFirst Inc.) asks for: "
            "1) Network diagram (in /docs/network-arch.pdf — UPDATE IT FIRST), "
            "2) Access control list (pull from AWS IAM), "
            "3) Proof that no raw card data touches our servers (show them the Stripe SDK integration). "
            "Priya Sharma coordinates the audit schedule. Start prep in January."
        ),
    },
    {
        "category": "History",
        "title": "Why we abandoned the GraphQL API",
        "content": (
            "In Q3 2022, we spent 6 weeks building a GraphQL layer on top of the REST API. "
            "It worked technically but caused N+1 query problems with our payment history endpoint "
            "that were really hard to optimize. The mobile team also said they preferred REST. "
            "We reverted in Q4. The dead branch is `feature/graphql-api` — don't delete it, "
            "there's useful resolver logic we might salvage for the admin dashboard."
        ),
    },
    {
        "category": "Contact",
        "title": "AWS Technical Account Manager",
        "content": (
            "Our AWS TAM is Linda Park (linda.park@aws-tam.example.com). She's incredibly helpful "
            "and has saved us twice during production incidents. If ElastiCache or RDS has issues, "
            "skip normal support and email her directly — she responds within an hour on weekdays. "
            "She also gave us $15K in credits last year. Worth maintaining the relationship."
        ),
    },
]

DEMO_EMPLOYEE_HANDOVER = """# 👤 Employee Notes — Sarah Chen | PayFlow
### Personal Knowledge Addendum

---

## 📝 Employee Corrections & Context

### Decision: PostgreSQL over MongoDB
✅ **Confirmed** — This is correct and I want to emphasize: this decision saved us during the 2023 compliance audit. The auditors specifically asked about data consistency guarantees and PostgreSQL's ACID compliance was a key factor in passing.

### Decision: Circuit Breaker pattern
✅ **Confirmed** with added context: The 50% failure threshold and 10s half-open window took **6 months of production tuning** to get right. The original values (30% threshold, 30s window) caused too many false positives. Don't change these without at least 2 weeks of load testing.

### Risk: Mobile team legacy endpoint
⚠️ **Confirmed — this is REAL**: I checked API gateway logs in August and saw ~200 req/day from mobile hitting `/v1/legacy-payments`. Contact Dev Kapoor (@dev.kapoor on Slack) before ANY deprecation work.

---

## ✅ Resolved Questions

### What is the Redis cache invalidation strategy for user session tokens?
💡 TTL-based approach: 30-minute sliding expiry. On each authenticated request, the TTL resets. Explicit logout deletes the key immediately. A daily cron job sweeps orphaned keys. This was decided verbally with the infra team (Marcus Rivera) in March 2023.

### Is the mobile team actually calling /v1/legacy-payments in production?
⚠️ **YES.** ~200 requests/day confirmed via API gateway logs (checked August 2024). Dev Kapoor (mobile lead) acknowledged but never committed to a migration timeline. **Do not deprecate without his sign-off.**

### What is the disaster recovery RTO/RPO for PayFlow?
📝 Unofficial targets: **RTO = 1 hour, RPO = 15 minutes**. Based on a conversation with VP of Engineering in Q2 2023 — never formalized. PostgreSQL: 15-min automated RDS snapshots. Redis: NOT backed up (ephemeral — sessions and rate limiter state only, no financial data).

---

## 💡 Tribal Knowledge

### ⚠️ Warning: Never deploy on Fridays or month-end
Merchant transaction volume spikes 3x in the last 3 days of every month. I caused a 12-minute outage in June 2022 by deploying during peak. Lost $8K in failed transactions. There's a soft freeze policy but CI/CD doesn't enforce it.

### 💡 Tip: Stripe webhook debugging shortcut
When webhooks fail silently: Stripe Dashboard → Developers → Webhooks → click event → check response code. 90% of the time it's a 401 from a rotated webhook signing secret that wasn't updated in the Stripe dashboard. 2 minutes vs 2 hours of CloudWatch digging.

### 📋 Process: PCI compliance audit prep
Annual audit in March by ComplianceFirst Inc. They need: network diagram (`/docs/network-arch.pdf` — update first!), AWS IAM access control list, and proof that no raw card data touches our servers (show Stripe SDK). Priya Sharma coordinates. Start prep in January.

### 📚 History: Why we abandoned GraphQL
Spent 6 weeks in Q3 2022 building a GraphQL layer. Hit N+1 query problems on payment history. Mobile team preferred REST anyway. Reverted in Q4. Dead branch: `feature/graphql-api` — don't delete it, has useful resolver logic for admin dashboard.

### 👤 Contact: AWS Technical Account Manager
Linda Park (linda.park@aws-tam.example.com). Skip normal AWS support for ElastiCache/RDS issues — email her directly, she responds within an hour on weekdays. She also helped us get $15K in credits. Maintain this relationship.

---

## 🎯 Final Recommendations

1. **First week priority**: Meet with Dev Kapoor about the legacy endpoint migration — this is a ticking time bomb.
2. **First month priority**: Formalize the DR RTO/RPO with the VP of Engineering and write it down.
3. **Ongoing**: Keep the relationship with Linda Park (AWS TAM) warm — she's worth her weight in gold during incidents.
4. **Don't waste time on**: Re-evaluating MongoDB or GraphQL. We tried both. The current stack is the right one.

*Good luck. PayFlow is a great system — treat it well.* 🌉
"""

DEMO_EMPLOYEE_GAP_ANSWERS = {
    "What is the Redis cache invalidation strategy for user session tokens?": (
        "We use a TTL-based approach: session tokens expire after 30 minutes of inactivity. "
        "On every authenticated request, the TTL is refreshed. If a user explicitly logs out, "
        "we delete the key immediately. There's also a daily cleanup cron that sweeps orphaned keys. "
        "Marcus Rivera and I discussed this over Slack in March 2023 — the infra team preferred "
        "passive expiry over active invalidation for simplicity."
    ),
    "Is the mobile team actually calling /v1/legacy-payments in production?": (
        "YES — I checked the API gateway logs in August and saw ~200 req/day from the mobile app's "
        "user-agent hitting /v1/legacy-payments. I told their lead (Dev Kapoor) about deprecation "
        "plans and he said they'd migrate to v2, but I never got a timeline. DO NOT deprecate "
        "without confirming with Dev first. His Slack handle is @dev.kapoor."
    ),
    "What is the disaster recovery RTO/RPO for PayFlow?": (
        "Unofficial targets are RTO=1hr, RPO=15min based on a conversation with our VP of Engineering "
        "in Q2 2023. We never formalized this in writing. The PostgreSQL backups run every 15 minutes "
        "via AWS RDS automated snapshots. Redis is NOT backed up — it's treated as ephemeral. "
        "If you lose Redis, you lose active sessions and rate limiter state, but no financial data."
    ),
}

DEMO_EMPLOYEE_TRIBAL_KNOWLEDGE = [
    {
        "category": "Warning",
        "title": "Never deploy on Fridays or month-end",
        "content": (
            "Merchant transaction volume spikes 3x on the last 3 days of every month. "
            "I learned this the hard way in June 2022 when a deploy caused a 12-minute outage "
            "during peak processing. We lost $8K in failed transactions. The SRE team now has "
            "a soft freeze policy, but it's not enforced by CI/CD. Be careful."
        ),
    },
    {
        "category": "Tip",
        "title": "Stripe webhook debugging shortcut",
        "content": (
            "When payment webhooks fail silently, don't dig through CloudWatch first. Go to "
            "Stripe Dashboard → Developers → Webhooks → click the event → check the response code. "
            "90% of the time it's a 401 because someone rotated the webhook signing secret in AWS "
            "Secrets Manager but forgot to update the Stripe dashboard. Takes 2 minutes vs 2 hours."
        ),
    },
    {
        "category": "Process",
        "title": "How to handle PCI compliance audits",
        "content": (
            "The annual PCI audit happens in March. The auditor (ComplianceFirst Inc.) asks for: "
            "1) Network diagram (in /docs/network-arch.pdf — UPDATE IT FIRST), "
            "2) Access control list (pull from AWS IAM), "
            "3) Proof that no raw card data touches our servers (show them the Stripe SDK integration). "
            "Priya Sharma coordinates the audit schedule. Start prep in January."
        ),
    },
    {
        "category": "History",
        "title": "Why we abandoned the GraphQL API",
        "content": (
            "In Q3 2022, we spent 6 weeks building a GraphQL layer on top of the REST API. "
            "It worked technically but caused N+1 query problems with our payment history endpoint "
            "that were really hard to optimize. The mobile team also said they preferred REST. "
            "We reverted in Q4. The dead branch is `feature/graphql-api` — don't delete it, "
            "there's useful resolver logic we might salvage for the admin dashboard."
        ),
    },
    {
        "category": "Contact",
        "title": "AWS Technical Account Manager",
        "content": (
            "Our AWS TAM is Linda Park (linda.park@aws-tam.example.com). She's incredibly helpful "
            "and has saved us twice during production incidents. If ElastiCache or RDS has issues, "
            "skip normal support and email her directly — she responds within an hour on weekdays. "
            "She also gave us $15K in credits last year. Worth maintaining the relationship."
        ),
    },
]

DEMO_EMPLOYEE_HANDOVER = """# 👤 Employee Notes — Sarah Chen | PayFlow
### Personal Knowledge Addendum

---

## 📝 Employee Corrections & Context

### Decision: PostgreSQL over MongoDB
✅ **Confirmed** — This is correct and I want to emphasize: this decision saved us during the 2023 compliance audit. The auditors specifically asked about data consistency guarantees and PostgreSQL's ACID compliance was a key factor in passing.

### Decision: Circuit Breaker pattern
✅ **Confirmed** with added context: The 50% failure threshold and 10s half-open window took **6 months of production tuning** to get right. The original values (30% threshold, 30s window) caused too many false positives. Don't change these without at least 2 weeks of load testing.

### Risk: Mobile team legacy endpoint
⚠️ **Confirmed — this is REAL**: I checked API gateway logs in August and saw ~200 req/day from mobile hitting `/v1/legacy-payments`. Contact Dev Kapoor (@dev.kapoor on Slack) before ANY deprecation work.

---

## ✅ Resolved Questions

### What is the Redis cache invalidation strategy for user session tokens?
💡 TTL-based approach: 30-minute sliding expiry. On each authenticated request, the TTL resets. Explicit logout deletes the key immediately. A daily cron job sweeps orphaned keys. This was decided verbally with the infra team (Marcus Rivera) in March 2023.

### Is the mobile team actually calling /v1/legacy-payments in production?
⚠️ **YES.** ~200 requests/day confirmed via API gateway logs (checked August 2024). Dev Kapoor (mobile lead) acknowledged but never committed to a migration timeline. **Do not deprecate without his sign-off.**

### What is the disaster recovery RTO/RPO for PayFlow?
📝 Unofficial targets: **RTO = 1 hour, RPO = 15 minutes**. Based on a conversation with VP of Engineering in Q2 2023 — never formalized. PostgreSQL: 15-min automated RDS snapshots. Redis: NOT backed up (ephemeral — sessions and rate limiter state only, no financial data).

---

## 💡 Tribal Knowledge

### ⚠️ Warning: Never deploy on Fridays or month-end
Merchant transaction volume spikes 3x in the last 3 days of every month. I caused a 12-minute outage in June 2022 by deploying during peak. Lost $8K in failed transactions. There's a soft freeze policy but CI/CD doesn't enforce it.

### 💡 Tip: Stripe webhook debugging shortcut
When webhooks fail silently: Stripe Dashboard → Developers → Webhooks → click event → check response code. 90% of the time it's a 401 from a rotated webhook signing secret that wasn't updated in the Stripe dashboard. 2 minutes vs 2 hours of CloudWatch digging.

### 📋 Process: PCI compliance audit prep
Annual audit in March by ComplianceFirst Inc. They need: network diagram (`/docs/network-arch.pdf` — update first!), AWS IAM access control list, and proof that no raw card data touches our servers (show Stripe SDK). Priya Sharma coordinates. Start prep in January.

### 📚 History: Why we abandoned GraphQL
Spent 6 weeks in Q3 2022 building a GraphQL layer. Hit N+1 query problems on payment history. Mobile team preferred REST anyway. Reverted in Q4. Dead branch: `feature/graphql-api` — don't delete it, has useful resolver logic for admin dashboard.

### 👤 Contact: AWS Technical Account Manager
Linda Park (linda.park@aws-tam.example.com). Skip normal AWS support for ElastiCache/RDS issues — email her directly, she responds within an hour on weekdays. She also helped us get $15K in credits. Maintain this relationship.
"""


# ─── SESSION STATE INIT ───────────────────────────────────────────────────────
def init_session_state():
    defaults = {
        "page": "connect",
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


# ─── COMPONENT HELPERS ────────────────────────────────────────────────────────
def source_badge(source_type: str) -> str:
    badges = {
        "file":   '<span class="badge badge-file">📁 File</span>',
        "github": '<span class="badge badge-github">🐙 GitHub</span>',
        "text":   '<span class="badge badge-text">📝 Notes</span>',
    }
    return badges.get(source_type, '<span class="badge badge-file">📄 Source</span>')


def confidence_badge(confidence: str) -> str:
    badges = {
        "HIGH":   '<span class="badge badge-high">🟢 High Confidence</span>',
        "MEDIUM": '<span class="badge badge-medium">🟡 Medium Confidence</span>',
        "LOW":    '<span class="badge badge-low">🔴 Low Confidence</span>',
    }
    return badges.get(confidence, '<span class="badge badge-medium">🟡 Medium Confidence</span>')


def render_stat_card(icon: str, label: str, number: str, chip_bg: str = "#EEF4FF") -> str:
    """Style A SaaS Stat Card component."""
    return f"""
    <div class="kb-stat-card">
        <div class="kb-stat-icon-chip" style="background:{chip_bg};">{icon}</div>
        <div>
            <div class="kb-stat-label">{label}</div>
            <div class="kb-stat-number">{number}</div>
        </div>
    </div>
    """


def step_indicator(current_page: str):
    """Style A Top Navbar + Step indicator with electric blue active highlight."""
    pages = [
        ("connect",     "1. Connect"),
        ("reconstruct", "2. Reconstruct"),
        ("employee",    "3. Employee"),
        ("review",      "4. Review"),
        ("handover",    "5. Handover"),
    ]
    page_order = [p[0] for p in pages]
    current_idx = page_order.index(current_page) if current_page in page_order else 0

    html = '<div class="kb-top-navbar">'
    html += '<div class="kb-nav-brand">'
    html += '<div class="kb-brand-icon">🏃‍♂️</div>'
    html += '<div><span class="kb-brand-title">Baton</span> <span class="kb-brand-pill">KNOWLEDGE HANDOVER</span></div>'
    html += '</div>'

    html += '<div class="kb-nav-steps">'
    for i, (pid, label) in enumerate(pages):
        cls = "kb-nav-step-item"
        if i < current_idx:
            cls += " done"
            label = "✓ " + label
        elif i == current_idx:
            cls += " active"
        html += f'<span class="{cls}">{label}</span>'
        if i < len(pages) - 1:
            html += '<span class="kb-nav-arrow">→</span>'
    html += '</div>'

    status_label = "🎭 Demo Simulator" if st.session_state.is_demo or not st.session_state.api_key else "⚡ Gemini 1.5 Active"
    html += f'<div class="kb-nav-status-pill">{status_label}</div>'
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)


# ─── SIDEBAR (Deep Plum Identity + Blue Active Pill) ──────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="display:flex; align-items:center; gap:0.6rem; margin-bottom:1.25rem;">
        <div style="width:36px; height:36px; border-radius:10px; background:rgba(255,255,255,0.12); display:flex; align-items:center; justify-content:center; font-size:1.2rem;">🏃‍♂️</div>
        <div>
            <div style="font-size:1.15rem; font-weight:800; color:#FFFFFF;">Baton</div>
            <div style="font-size:0.75rem; color:#CBD5E1;">Knowledge Retention Platform</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("---")

    if st.session_state.api_key:
        st.success("Gemini connected")
    else:
        st.info("No key configured - demo only")

    st.markdown("---")
    st.markdown("**Workflow Navigation**")

    nav_pages = [
        ("connect", "🔌 1. Connect Sources"),
        ("reconstruct", "🧠 2. Reconstruct"),
        ("employee", "👤 3. Employee Hub"),
        ("review", "✅ 4. Manager Review"),
        ("handover", "📦 5. Handover Package"),
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

    st.markdown("---")
    st.caption("🏃‍♂️ Baton • Knowledge Handover Platform")
    st.caption("Preserving Institutional Context")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 1: CONNECT (Split-Panel Layout: Style B Tool + Style A Spacing)
# ═══════════════════════════════════════════════════════════════════════════════
if st.session_state.page == "connect":
    step_indicator("connect")

    if not st.session_state.api_key:
        st.markdown("""
        <div class="kb-banner-demo">
            <span>🎭</span>
            <div><b>Demo Mode Active:</b> Explore the complete 5-step handover journey with Sarah Chen's PayFlow microservice. All views, verifications, and downloads are fully functional.</div>
        </div>
        """, unsafe_allow_html=True)

    # Split-Panel Layout: Left inputs (White) & Right preview/result (Deep Plum)
    col_left, col_right = st.columns([7, 5], gap="large")

    with col_left:
        # Step 1: Ingest Sources
        st.markdown('<div class="kb-section-title"><span class="kb-step-badge">1</span> Connect Knowledge Sources</div>', unsafe_allow_html=True)

        tab1, tab2, tab3 = st.tabs(["📁 Upload Files", "🐙 GitHub Repository", "📝 Paste Content"])

        with tab1:
            uploaded_files = st.file_uploader(
                "Upload documents (PDF, TXT, MD, Markdown)",
                type=["pdf", "txt", "md", "markdown"],
                accept_multiple_files=True,
                help="Architecture specs, design decisions, runbooks, or transition docs"
            )
            if uploaded_files:
                st.session_state.uploaded_files = uploaded_files
                for f in uploaded_files:
                    st.markdown(f"📄 **{f.name}** &nbsp;<span style='color:#64748B;'>({round(f.size/1024, 1)} KB)</span>", unsafe_allow_html=True)

        with tab2:
            github_url = st.text_input(
                "GitHub Repository URL",
                value=st.session_state.github_url,
                placeholder="https://github.com/organization/microservice",
                help="Public repositories work automatically without tokens"
            )
            st.session_state.github_url = github_url

            github_token = st.text_input(
                "Personal Access Token (optional for private repos)",
                type="password",
                value=st.session_state.github_token,
                placeholder="ghp_...",
                help="Only required if the repository is private"
            )
            st.session_state.github_token = github_token

            if github_url:
                st.info(f"🐙 Connector will extract README, recent commits, open issues, and pull requests from `{github_url}`")

        with tab3:
            pasted_text = st.text_area(
                "Paste notes, emails, Slack threads, or meeting excerpts",
                value=st.session_state.pasted_text,
                height=180,
                placeholder="Paste informal transition notes, architecture rationale, or unwritten rules...\n\nExample:\n- Chose PostgreSQL for ACID transactional ledger guarantee\n- Stripe webhook signing secret rotates every 6 months\n- Known issue: Redis session keys lack explicit eviction runbook"
            )
            st.session_state.pasted_text = pasted_text

        st.markdown("<br>", unsafe_allow_html=True)

        # Step 2: Persona Context
        st.markdown('<div class="kb-section-title"><span class="kb-step-badge">2</span> Scope & Departing Context</div>', unsafe_allow_html=True)

        col_p1, col_p2 = st.columns(2)
        with col_p1:
            employee_name = st.text_input(
                "Who is departing? 👋",
                value=st.session_state.employee_name,
                placeholder="e.g. Sarah Chen",
            )
            st.session_state.employee_name = employee_name

        with col_p2:
            project_role = st.text_input(
                "Role & Project Scope 💼",
                value=st.session_state.project_role,
                placeholder="e.g. Senior Backend Engineer — PayFlow",
            )
            st.session_state.project_role = project_role

    with col_right:
        # Style B: Deep Plum Right Panel with Live Preview & Orange Action Button
        emp_display = st.session_state.employee_name.strip() or ("Sarah Chen" if not st.session_state.api_key else "Pending input...")
        role_display = st.session_state.project_role.strip() or ("Senior Backend Engineer — PayFlow" if not st.session_state.api_key else "Pending input...")

        # Detect staged source count
        file_count = len(st.session_state.uploaded_files) if st.session_state.uploaded_files else 0
        has_gh = bool(st.session_state.github_url.strip())
        text_len = len(st.session_state.pasted_text.strip())

        st.markdown(f"""
        <div class="kb-panel-plum">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:1rem;">
                <h3 style="margin:0; font-size:1.2rem; font-weight:800;">⚡ Live Handover Preview</h3>
                <span style="background:rgba(255,255,255,0.15); padding:3px 10px; border-radius:9999px; font-size:0.75rem; font-weight:700;">READY</span>
            </div>
            
            <p style="font-size:0.88rem; margin-bottom:0.75rem;">Reconstruction engine aggregates implicit decisions, critical risks, and undocumented tribal knowledge.</p>
            
            <div class="kb-plum-pill-item">
                👤 <b>Departing:</b> {emp_display}
            </div>
            <div class="kb-plum-pill-item">
                💼 <b>Scope:</b> {role_display}
            </div>
            <div class="kb-plum-pill-item">
                📥 <b>Staged Sources:</b> {file_count} file(s) • {'GitHub connected' if has_gh else 'No repo'} • {text_len} chars text
            </div>

            <div style="border-top:1px solid rgba(255,255,255,0.15); margin:1.2rem 0; padding-top:1rem;">
                <div style="font-size:0.8rem; font-weight:700; text-transform:uppercase; letter-spacing:0.04em; margin-bottom:0.6rem; color:#A78BFA;">Engine Deliverables:</div>
                <div style="font-size:0.85rem; line-height:1.6; color:#E2E8F0;">
                    ✓ <b>Decision Log</b> with citation source linking<br>
                    ✓ <b>Risk & Landmine Radar</b> with confidence scores<br>
                    ✓ <b>Employee Verification Hub</b> to resolve gaps<br>
                    ✓ <b>Role-Based Handover Package</b> (Manager & Successor)
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # Standout Warm Orange Action Button (Style B)
        has_sources = bool(
            (st.session_state.uploaded_files) or
            (st.session_state.github_url.strip()) or
            (st.session_state.pasted_text.strip())
        )

        btn_label = "🔍 Analyze & Reconstruct Knowledge"
        if not st.session_state.api_key:
            btn_label = "🎭 Load Demo — See Full Example"

        analyze_btn = st.button(
            btn_label,
            type="primary",
            use_container_width=True,
            disabled=(not has_sources and bool(st.session_state.api_key)),
        )

        if analyze_btn:
            if not st.session_state.api_key:
                # DEMO MODE
                with st.spinner("🎭 Reconstructing synthetic knowledge profile..."):
                    time.sleep(1.2)
                st.session_state.knowledge_profile = DEMO_KNOWLEDGE_PROFILE
                st.session_state.employee_name = st.session_state.employee_name or "Sarah Chen"
                st.session_state.project_role = st.session_state.project_role or "Senior Backend Engineer — PayFlow payment microservice"
                st.session_state.is_demo = True
                st.session_state.manager_handover = DEMO_MANAGER_HANDOVER
                st.session_state.newhire_handover = DEMO_NEWHIRE_HANDOVER
                st.session_state.employee_handover = DEMO_EMPLOYEE_HANDOVER
                st.session_state.employee_gap_answers = dict(DEMO_EMPLOYEE_GAP_ANSWERS)
                st.session_state.employee_tribal_knowledge = list(DEMO_EMPLOYEE_TRIBAL_KNOWLEDGE)
                st.session_state.page = "reconstruct"
                st.rerun()
            else:
                # REAL GEMINI MODE
                all_sources = []
                errors = []

                with st.spinner("⚙️ Ingesting and parsing sources..."):
                    if st.session_state.uploaded_files:
                        try:
                            from utils.file_processor import process_files
                            file_results = process_files(st.session_state.uploaded_files)
                            all_sources.extend(file_results)
                        except Exception as e:
                            errors.append(f"File parsing: {e}")

                    if st.session_state.github_url.strip():
                        try:
                            from utils.github_connector import fetch_repo_knowledge
                            github_results = fetch_repo_knowledge(
                                st.session_state.github_url.strip(),
                                token=st.session_state.github_token.strip() or None
                            )
                            all_sources.extend(github_results)
                        except Exception as e:
                            errors.append(f"GitHub connector: {e}")

                    if st.session_state.pasted_text.strip():
                        all_sources.append({
                            "content": st.session_state.pasted_text.strip(),
                            "source": "Pasted Notes",
                            "source_type": "text"
                        })

                if errors:
                    for err in errors:
                        st.warning(f"⚠️ {err}")
                    if not all_sources:
                        st.error("No valid sources could be ingested.")
                        st.stop()

                if not all_sources:
                    st.error("Please add at least one file, repo, or note to proceed.")
                    st.stop()

                st.session_state.all_sources = all_sources

                with st.spinner(f"🤖 Reconstructing knowledge graph across {len(all_sources)} source(s)..."):
                    try:
                        from utils.gemini_engine import analyze_sources
                        profile = analyze_sources(all_sources, st.session_state.api_key)
                        st.session_state.knowledge_profile = profile
                        st.session_state.is_demo = False
                        st.session_state.page = "reconstruct"
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Gemini analysis error: {e}")
                        st.info("Check your key at aistudio.google.com")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 2: RECONSTRUCT (Dashboard Layout: Style A Stat Cards & Content Grid)
# ═══════════════════════════════════════════════════════════════════════════════
elif st.session_state.page == "reconstruct":
    step_indicator("reconstruct")

    profile = st.session_state.knowledge_profile
    if not profile:
        st.error("No knowledge profile found. Please start by connecting sources.")
        st.stop()

    if st.session_state.is_demo:
        st.markdown("""
        <div class="kb-banner-demo">
            <span>🎭</span>
            <div><b>Demo Mode:</b> Displaying AI reconstruction for <b>Sarah Chen</b> (PayFlow Microservice). Inspect the citations, confidence scores, and identified knowledge gaps below.</div>
        </div>
        """, unsafe_allow_html=True)

    # Executive Hero Banner
    st.markdown(f"""
    <div class="kb-card-hero">
        <div style="display:flex; justify-content:space-between; align-items:flex-start; flex-wrap:wrap; gap:1rem;">
            <div>
                <h2 style="font-size:1.6rem; font-weight:800; color:var(--color-plum); margin:0 0 6px 0;">🧠 Reconstructed Knowledge Profile</h2>
                <div style="color:var(--color-text-secondary); font-size:0.92rem;">
                    <b>Departing:</b> {st.session_state.employee_name or 'Unknown'} &nbsp;|&nbsp;
                    <b>Project Scope:</b> {st.session_state.project_role or 'Unknown'}
                </div>
            </div>
            <div style="background:var(--color-plum); color:#FFFFFF; padding:6px 16px; border-radius:9999px; font-size:0.8rem; font-weight:700;">
                CITATION-LINKED
            </div>
        </div>
        <p style="font-size:0.95rem; line-height:1.6; color:var(--color-text); margin-top:1rem; margin-bottom:0;">
            {profile.get("summary", "")}
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Style A Row of Stat Cards (small icon chip, label, large number)
    st.markdown('<div class="kb-stat-grid">', unsafe_allow_html=True)
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.markdown(render_stat_card("📋", "Decisions", str(len(profile.get("decisions", []))), "#FAF5FF"), unsafe_allow_html=True)
    with c2:
        st.markdown(render_stat_card("⚠️", "Risks", str(len(profile.get("risks", []))), "#FFFBEB"), unsafe_allow_html=True)
    with c3:
        st.markdown(render_stat_card("❓", "Gaps Identified", str(len(profile.get("unresolved", []))), "#EFF6FF"), unsafe_allow_html=True)
    with c4:
        st.markdown(render_stat_card("👥", "Contacts", str(len(profile.get("contacts", []))), "#ECFDF5"), unsafe_allow_html=True)
    with c5:
        st.markdown(render_stat_card("🔗", "Dependencies", str(len(profile.get("dependencies", []))), "#EEF2FF"), unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Soft-Gradient Distribution Bar (Style A chart aesthetic)
    high_count = sum(1 for d in profile.get("decisions", []) if d.get("confidence") == "HIGH")
    med_count = sum(1 for d in profile.get("decisions", []) if d.get("confidence") == "MEDIUM")
    low_count = sum(1 for d in profile.get("decisions", []) if d.get("confidence") == "LOW")
    total_d = max(1, len(profile.get("decisions", [])))
    high_pct = int((high_count / total_d) * 100)
    med_pct = int((med_count / total_d) * 100)
    low_pct = 100 - high_pct - med_pct

    st.markdown(f"""
    <div style="background:#F8FAFC; border:1px solid var(--color-border); border-radius:var(--radius-lg); padding:1rem 1.4rem; margin-bottom:1.75rem;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.5rem;">
            <span style="font-size:0.82rem; font-weight:700; color:var(--color-text-secondary); text-transform:uppercase; letter-spacing:0.04em;">Evidence Confidence Breakdown</span>
            <span style="font-size:0.82rem; font-weight:600; color:var(--color-text);">{high_pct}% High • {med_pct}% Medium • {low_pct}% Inferred</span>
        </div>
        <div style="height:10px; border-radius:9999px; display:flex; overflow:hidden; background:#E2E8F0;">
            <div style="width:{high_pct}%; background:linear-gradient(90deg, #10B981, #059669);" title="High Confidence: {high_count}"></div>
            <div style="width:{med_pct}%; background:linear-gradient(90deg, #F59E0B, #D97706);" title="Medium Confidence: {med_count}"></div>
            <div style="width:{low_pct}%; background:linear-gradient(90deg, #EF4444, #DC2626);" title="Low Confidence: {low_count}"></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Content Grid: Split into Two Columns (Decisions & Dependencies vs Risks & Gaps)
    col_grid1, col_grid2 = st.columns([1, 1], gap="large")

    with col_grid1:
        st.markdown('<div class="kb-section-title">📋 Architectural Decision Log</div>', unsafe_allow_html=True)
        for i, decision in enumerate(profile.get("decisions", [])):
            conf = decision.get("confidence", "MEDIUM")
            stype = decision.get("source_type", "file")
            with st.expander(f"**Decision #{i+1}:** {decision.get('text', '')[:75]}...", expanded=(i < 2)):
                st.markdown(f"""
                <div class="kb-card kb-card-blue-tint">
                    <p style="font-size:1.02rem; font-weight:700; color:var(--color-text); margin-bottom:0.6rem;">{decision.get('text', '')}</p>
                    <p>{source_badge(stype)} {confidence_badge(conf)} &nbsp;<span style="color:var(--color-text-muted); font-size:0.82rem;">Source: {decision.get('source', '')}</span></p>
                </div>
                """, unsafe_allow_html=True)
                excerpt = decision.get("excerpt", "")
                if excerpt:
                    st.markdown(f"> *\"{excerpt}\"*")

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<div class="kb-section-title">🔗 Key Dependencies</div>', unsafe_allow_html=True)
        for dep in profile.get("dependencies", []):
            st.markdown(f"""
            <div class="kb-card kb-card-blue-tint">
                <b>🔗 {dep.get('item', '')}</b> — {dep.get('description', '')}
                <br/><small style="color:var(--color-text-muted);">Source citation: {dep.get('source', '')}</small>
            </div>
            """, unsafe_allow_html=True)

    with col_grid2:
        st.markdown('<div class="kb-section-title">⚠️ Critical Risks & Landmines</div>', unsafe_allow_html=True)
        for j, risk in enumerate(profile.get("risks", [])):
            conf = risk.get("confidence", "MEDIUM")
            card_tint = "kb-card-red-tint" if conf == "HIGH" else "kb-card-orange-tint"
            with st.expander(f"**Risk #{j+1}:** {risk.get('text', '')[:75]}...", expanded=(j < 2)):
                st.markdown(f"""
                <div class="kb-card {card_tint}">
                    <p style="font-size:1.02rem; font-weight:700; color:var(--color-text); margin-bottom:0.6rem;">{risk.get('text', '')}</p>
                    <p>{confidence_badge(conf)} &nbsp;<span style="color:var(--color-text-muted); font-size:0.82rem;">Source: {risk.get('source', '')}</span></p>
                </div>
                """, unsafe_allow_html=True)
                excerpt = risk.get("excerpt", "")
                if excerpt:
                    st.markdown(f"> *\"{excerpt}\"*")

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<div class="kb-section-title">❓ Unresolved Knowledge Gaps</div>', unsafe_allow_html=True)
        for q in profile.get("unresolved", []):
            st.markdown(f"""
            <div class="kb-card kb-card-orange-tint">
                <p style="font-weight:700; color:#B45309; margin-bottom:4px;">⚠️ {q.get('question', '')}</p>
                <p style="color:var(--color-text-secondary); font-size:0.85rem; margin-bottom:0;">
                    <i>AI Gap Note: {q.get('why_unknown', '')}</i>
                </p>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<div class="kb-section-title">👥 Stakeholders & Key Contacts</div>', unsafe_allow_html=True)
        for contact in profile.get("contacts", []):
            st.markdown(f"""
            <div class="kb-card kb-card-green-tint">
                <div style="font-weight:700; color:var(--color-text);">👤 {contact.get('name', '')}</div>
                <div style="font-size:0.88rem; color:var(--color-text-secondary);">{contact.get('role', '')}</div>
                <small style="color:var(--color-text-muted);">Source: {contact.get('source', '')}</small>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("---")
    col_act1, col_act2 = st.columns([2, 1])
    with col_act1:
        if st.button("➡️ Proceed to Employee View (Verify & Add Tribal Knowledge)", type="primary", use_container_width=True):
            st.session_state.page = "employee"
            st.rerun()
    with col_act2:
        if st.button("⏩ Skip to Manager Review", use_container_width=True):
            st.session_state.page = "review"
            st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 3: EMPLOYEE VIEW (Interactive Verification & Tacit Knowledge Capture)
# ═══════════════════════════════════════════════════════════════════════════════
elif st.session_state.page == "employee":
    step_indicator("employee")

    profile = st.session_state.knowledge_profile
    if not profile:
        st.error("No knowledge profile found. Please start by connecting sources.")
        st.stop()

    if st.session_state.is_demo:
        st.markdown("""
        <div class="kb-banner-demo">
            <span>🎭</span>
            <div><b>Demo Mode Active:</b> You are interacting as <b>Sarah Chen</b>. Pre-populated decision assessments, resolved questions, and critical tribal tips are loaded for demonstration.</div>
        </div>
        """, unsafe_allow_html=True)

    employee = st.session_state.employee_name or "Departing Engineer"
    project = st.session_state.project_role or "Key System Contributor"

    st.markdown(f"""
    <div class="kb-card-hero">
        <h2 style="font-size:1.6rem; font-weight:800; color:var(--color-plum); margin:0 0 6px 0;">👤 Employee Knowledge Hub</h2>
        <div style="color:var(--color-text-secondary); font-size:0.95rem; margin-bottom:0.75rem;">
            <b>Welcome, {employee}!</b> Your tacit knowledge is essential to prevent operational disruptions. Verify AI extractions, resolve documentation blind spots, and share unwritten rules before your departure.
        </div>
        <span class="badge badge-file">{project}</span>
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

    # Style A Stat Cards Row
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(render_stat_card("📋", "Verified Items", f"{verified_count}/{total_verifiable}", "#FAF5FF"), unsafe_allow_html=True)
    with c2:
        st.markdown(render_stat_card("❓", "Gaps Resolved", f"{gaps_resolved}/{total_gaps}", "#EFF6FF"), unsafe_allow_html=True)
    with c3:
        st.markdown(render_stat_card("💡", "Tribal Notes", str(len(tribal_items)), "#FFFBEB"), unsafe_allow_html=True)
    with c4:
        st.markdown(render_stat_card("🎯", "Readiness Score", f"{readiness_score}%", "#ECFDF5"), unsafe_allow_html=True)

    st.progress(readiness_score / 100.0)
    st.markdown("---")

    emp_tab1, emp_tab2, emp_tab3 = st.tabs([
        "📋 1. Verify Extracted Findings",
        "❓ 2. Answer Knowledge Gaps",
        "💡 3. Share Tribal Knowledge"
    ])

    with emp_tab1:
        st.markdown('<div class="kb-section-title">📋 Architectural Decisions Verification</div>', unsafe_allow_html=True)
        st.caption("Confirm accuracy or add context explaining the trade-offs that led to each decision.")

        for i, decision in enumerate(decisions):
            conf = decision.get("confidence", "MEDIUM")
            stype = decision.get("source_type", "file")
            d_key = f"decision_{i}"
            saved_verif = st.session_state.employee_verifications.get(d_key, {})
            current_status = saved_verif.get("status", "Confirmed Accurate")
            current_note = saved_verif.get("note", "")

            with st.expander(f"**Decision #{i+1}:** {decision.get('text', '')[:75]}...", expanded=(i == 0)):
                st.markdown(f"""
                <div class="kb-card kb-card-blue-tint">
                    <p style="font-size:1.02rem; font-weight:700; color:var(--color-text); margin-bottom:0.5rem;">{decision.get('text', '')}</p>
                    <p>{source_badge(stype)} {confidence_badge(conf)} &nbsp;<span style="color:var(--color-text-muted); font-size:0.82rem;">Source: {decision.get('source', '')}</span></p>
                </div>
                """, unsafe_allow_html=True)
                excerpt = decision.get("excerpt", "")
                if excerpt:
                    st.markdown(f"> *\"{excerpt}\"*")

                col_stat, col_note = st.columns([1, 2])
                with col_stat:
                    status_choice = st.radio(
                        "Your Assessment:",
                        ["Confirmed Accurate", "Needs Context", "Inaccurate / Outdated"],
                        index=["Confirmed Accurate", "Needs Context", "Inaccurate / Outdated"].index(current_status) if current_status in ["Confirmed Accurate", "Needs Context", "Inaccurate / Outdated"] else 0,
                        key=f"status_dec_{i}"
                    )
                with col_note:
                    note_input = st.text_area(
                        "Your Additional Context / Nuance (Why was this built this way?):",
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
        st.markdown('<div class="kb-section-title">⚠️ Critical Risks Verification</div>', unsafe_allow_html=True)
        st.caption("Confirm known risks and specify concrete mitigation steps.")

        for j, risk in enumerate(risks):
            conf = risk.get("confidence", "MEDIUM")
            r_key = f"risk_{j}"
            saved_r_verif = st.session_state.employee_verifications.get(r_key, {})
            current_r_status = saved_r_verif.get("status", "Active Risk")
            current_r_note = saved_r_verif.get("note", "")

            with st.expander(f"**Risk #{j+1}:** {risk.get('text', '')[:75]}...", expanded=(j == 0)):
                card_tint = "kb-card-red-tint" if conf == "HIGH" else "kb-card-orange-tint"
                st.markdown(f"""
                <div class="kb-card {card_tint}">
                    <p style="font-size:1.02rem; font-weight:700; color:var(--color-text); margin-bottom:0.5rem;">{risk.get('text', '')}</p>
                    <p>{confidence_badge(conf)} &nbsp;<span style="color:var(--color-text-muted); font-size:0.82rem;">Source: {risk.get('source', '')}</span></p>
                </div>
                """, unsafe_allow_html=True)
                excerpt = risk.get("excerpt", "")
                if excerpt:
                    st.markdown(f"> *\"{excerpt}\"*")

                col_r_stat, col_r_note = st.columns([1, 2])
                with col_r_stat:
                    r_status_choice = st.radio(
                        "Severity & State:",
                        ["Active Risk", "Mitigated / Low Priority", "False Alarm / Resolved"],
                        index=["Active Risk", "Mitigated / Low Priority", "False Alarm / Resolved"].index(current_r_status) if current_r_status in ["Active Risk", "Mitigated / Low Priority", "False Alarm / Resolved"] else 0,
                        key=f"status_risk_{j}"
                    )
                with col_r_note:
                    r_note_input = st.text_area(
                        "Mitigation Guidance / Next Steps:",
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
        st.markdown('<div class="kb-section-title">❓ Resolve Knowledge Gaps</div>', unsafe_allow_html=True)
        st.info("💡 **Tacit Knowledge Opportunity:** The AI discovered these unanswered questions across your codebase and documents. Only you hold the context to resolve them before leaving.")

        if unresolved:
            for k, q in enumerate(unresolved):
                q_text = q.get("question", "")
                why = q.get("why_unknown", "")
                existing_ans = st.session_state.employee_gap_answers.get(q_text, "")

                st.markdown(f"""
                <div class="kb-card kb-card-orange-tint">
                    <p style="font-size:1.05rem; font-weight:700; color:#B45309; margin-bottom:4px;">❓ Question #{k+1}: {q_text}</p>
                    <p style="color:var(--color-text-secondary); font-size:0.84rem; margin-bottom:0;"><i>AI reason: {why}</i></p>
                </div>
                """, unsafe_allow_html=True)

                ans_input = st.text_area(
                    f"Your Resolution for Question #{k+1}:",
                    value=existing_ans,
                    key=f"gap_response_{k}",
                    height=100,
                    placeholder="Provide the unwritten answer, internal discussions, or current standard operating procedure..."
                )
                st.session_state.employee_gap_answers[q_text] = ans_input

                if ans_input.strip():
                    st.success("✅ Resolved & Added to Handover")
                else:
                    st.caption("⏳ Awaiting your input")
                st.markdown("<br>", unsafe_allow_html=True)
        else:
            st.success("🎉 No unresolved knowledge gaps identified in this repository!")

    with emp_tab3:
        st.markdown('<div class="kb-section-title">💡 Add Tribal Knowledge & Gotchas</div>', unsafe_allow_html=True)
        st.markdown("Record informal wisdom that isn't written down anywhere — deployment freezes, vendor quirks, debugging shortcuts, and unspoken team practices.")

        with st.form("add_tribal_knowledge_form", clear_on_submit=True):
            col_t1, col_t2 = st.columns([1, 2])
            with col_t1:
                category = st.selectbox(
                    "Category",
                    ["⚠️ Warning / Landmine", "💡 Pro Tip", "📋 Undocumented Process", "📚 Historical Context", "👤 Key Contact / Stakeholder"]
                )
            with col_t2:
                t_title = st.text_input("Title / Topic", placeholder="e.g. Stripe webhook secret rotation trap")

            t_content = st.text_area(
                "Detailed Guidance & Practical Advice",
                placeholder="Explain what happened, why it matters, and how your successor can avoid pitfalls...",
                height=105
            )

            submit_tribal = st.form_submit_button("➕ Add Tribal Knowledge Item", use_container_width=True)
            if submit_tribal:
                if t_title.strip() and t_content.strip():
                    cat_clean = category.split(" ")[1] if " " in category else category
                    st.session_state.employee_tribal_knowledge.append({
                        "category": cat_clean,
                        "title": t_title.strip(),
                        "content": t_content.strip()
                    })
                    st.toast(f"✅ Added: {t_title.strip()}")
                    st.rerun()
                else:
                    st.error("Please provide both a title and description.")

        if st.session_state.employee_tribal_knowledge:
            st.markdown("#### 📚 Recorded Tribal Knowledge Items:")
            for idx, item in enumerate(st.session_state.employee_tribal_knowledge):
                cat = item.get("category", "Tip")
                border_class = "kb-card-red-tint" if "Warning" in cat else ("kb-card-green-tint" if "Contact" in cat else "kb-card-blue-tint")

                c_item, c_del = st.columns([6, 1])
                with c_item:
                    st.markdown(f"""
                    <div class="kb-card {border_class}">
                        <div style="font-weight:700; color:var(--color-text);">[{cat.upper()}] {item.get('title', '')}</div>
                        <p style="font-size:0.92rem; color:var(--color-text-secondary); margin-top:6px; margin-bottom:0;">{item.get('content', '')}</p>
                    </div>
                    """, unsafe_allow_html=True)
                with c_del:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("🗑️ Remove", key=f"del_tk_{idx}"):
                        st.session_state.employee_tribal_knowledge.pop(idx)
                        st.rerun()

    st.markdown("---")
    col_nav1, col_nav2 = st.columns([2, 1])
    with col_nav1:
        if st.button("🚀 Complete Employee Review & Proceed to Manager Review", type="primary", use_container_width=True):
            st.session_state.page = "review"
            st.rerun()
    with col_nav2:
        if st.button("← Back to Reconstruct", use_container_width=True):
            st.session_state.page = "reconstruct"
            st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 4: REVIEW & APPROVE (Manager Review & Multi-Perspective Sign-Off)
# ═══════════════════════════════════════════════════════════════════════════════
elif st.session_state.page == "review":
    step_indicator("review")

    profile = st.session_state.knowledge_profile
    if not profile:
        st.error("No knowledge profile found. Please start by connecting sources.")
        st.stop()

    if st.session_state.is_demo:
        st.markdown("""
        <div class="demo-banner">
        🎭 <b>Demo Mode Active:</b> Review and sign off on each section to unlock the multi-perspective handover package.
        </div>
        """, unsafe_allow_html=True)

    st.markdown("""
    <div class="kb-card-hero">
        <h2 style="font-size:1.6rem; font-weight:800; color:var(--color-plum); margin:0 0 6px 0;">✅ Manager Review & Executive Sign-Off</h2>
        <div style="color:var(--color-text-secondary); font-size:0.95rem;">
            Inspect verified claims, employee gap resolutions, and tribal knowledge. Add managerial follow-ups, then approve each section.
        </div>
    </div>
    """, unsafe_allow_html=True)

    sections = [
        ("decisions", "📋 Decision Log", profile.get("decisions", [])),
        ("risks", "⚠️ Risks & Dependencies", profile.get("risks", [])),
        ("unresolved", "❓ Resolved & Open Questions", profile.get("unresolved", [])),
        ("tribal", "💡 Tribal Knowledge & Gotchas", st.session_state.employee_tribal_knowledge),
        ("contacts", "👥 Key Contacts & Dependencies", profile.get("contacts", [])),
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
                        verif_badge = f" — 👤 *Employee: {verif.get('status', 'Confirmed')}*"
                        if verif.get("note"):
                            verif_badge += f" (Note: \"{verif.get('note')}\")"
                    st.markdown(f"- **{item.get('text', '')[:100]}** _{source_badge(item.get('source_type','file'))} {confidence_badge(item.get('confidence','MEDIUM'))}_{verif_badge}",
                               unsafe_allow_html=True)
            elif section_id == "risks":
                for idx, item in enumerate(section_data):
                    verif = st.session_state.employee_verifications.get(f"risk_{idx}")
                    verif_badge = ""
                    if verif:
                        verif_badge = f" — 👤 *Employee: {verif.get('status', 'Confirmed')}*"
                        if verif.get("note"):
                            verif_badge += f" (Note: \"{verif.get('note')}\")"
                    st.markdown(f"- **{item.get('text', '')[:100]}** _{confidence_badge(item.get('confidence','MEDIUM'))}_{verif_badge}",
                               unsafe_allow_html=True)
            elif section_id == "unresolved":
                for item in section_data:
                    q_text = item.get('question', '')
                    emp_ans = st.session_state.employee_gap_answers.get(q_text, "")
                    if emp_ans:
                        st.markdown(f"- ❓ **{q_text}**<br>&nbsp;&nbsp;&nbsp;&nbsp;✅ **Employee Context:** _{emp_ans}_", unsafe_allow_html=True)
                    else:
                        st.markdown(f"- ⚠️ **{q_text}** *(Unresolved — awaiting input)*")
            elif section_id == "tribal":
                if section_data:
                    for item in section_data:
                        st.markdown(f"- 💡 **[{item.get('category', 'Tip')}] {item.get('title', '')}**: {item.get('content', '')}")
                else:
                    st.markdown("_- No extra tribal knowledge recorded._")
            elif section_id == "contacts":
                for item in section_data:
                    st.markdown(f"- 👤 **{item.get('name', '')}** — {item.get('role', '')}")

        col_rev1, col_rev2 = st.columns([2, 1])
        with col_rev1:
            corrections = st.text_area(
                f"📝 Manager notes / Action assignments for {section_title}:",
                value=st.session_state.corrections.get(section_id, ""),
                key=f"correction_{section_id}",
                placeholder="Assign owner, link Jira ticket, or add sign-off caveats...",
                height=85
            )
            st.session_state.corrections[section_id] = corrections

        with col_rev2:
            st.markdown("<br>", unsafe_allow_html=True)
            approved = st.checkbox(
                f"✅ Sign off on {section_title}",
                value=st.session_state.approvals.get(section_id, False),
                key=f"approve_{section_id}"
            )
            st.session_state.approvals[section_id] = approved

            if approved:
                st.success("✅ Section Approved")
            else:
                st.warning("⏳ Pending Approval")
                all_approved = False

        st.markdown("---")

    approved_count = sum(1 for v in st.session_state.approvals.values() if v)
    total_sections = len(sections)

    st.markdown(f"### 📊 Approval Status: {approved_count}/{total_sections} sections approved")
    progress = approved_count / total_sections if total_sections > 0 else 0
    st.progress(progress)

    if all_approved:
        st.success("🎉 All sections signed off! You can now generate the complete multi-perspective handover package.")
    else:
        remaining = total_sections - approved_count
        st.info(f"⏳ {remaining} section(s) still require approval.")

    st.markdown("---")
    btn_disabled = not all_approved

    col_gen1, col_gen2 = st.columns([2, 1])
    with col_gen1:
        if st.button(
            "🚀 Generate Final Handover Package (Manager, Successor & Employee)",
            type="primary",
            use_container_width=True,
            disabled=btn_disabled,
        ):
            if st.session_state.is_demo:
                st.session_state.employee_handover = DEMO_EMPLOYEE_HANDOVER
                st.session_state.page = "handover"
                st.rerun()
            else:
                # Real Gemini generation

                # ── Build reviewed_profile: apply employee verifications and
                #    attach manager notes before passing to Gemini ──────────────
                reviewed_profile = copy.deepcopy(profile)

                # Decisions: iterate original list by index to keep key alignment
                filtered_decisions = []
                for idx, decision in enumerate(profile.get("decisions", [])):
                    verif = st.session_state.employee_verifications.get(
                        f"decision_{idx}", {}
                    )
                    status = verif.get("status", "")
                    if status == "Inaccurate / Outdated":
                        continue  # drop entirely
                    item = copy.deepcopy(decision)
                    if status == "Needs Context" and verif.get("note"):
                        item["text"] = item["text"] + f" [Employee note: {verif['note']}]"
                    filtered_decisions.append(item)
                reviewed_profile["decisions"] = filtered_decisions

                # Risks: use original list indices; different status labels
                filtered_risks = []
                for idx, risk in enumerate(profile.get("risks", [])):
                    verif = st.session_state.employee_verifications.get(
                        f"risk_{idx}", {}
                    )
                    status = verif.get("status", "")
                    if status == "False Alarm / Resolved":
                        continue  # drop entirely
                    item = copy.deepcopy(risk)
                    if status == "Mitigated / Low Priority":
                        suffix = " [Employee: mitigated / low priority]"
                        if verif.get("note"):
                            suffix += f" [Employee note: {verif['note']}]"
                        item["text"] = item["text"] + suffix
                    elif status == "Active Risk" and verif.get("note"):
                        item["text"] = item["text"] + f" [Employee note: {verif['note']}]"
                    filtered_risks.append(item)
                reviewed_profile["risks"] = filtered_risks

                # Manager notes: map section_id → note text
                reviewed_profile["manager_notes"] = dict(st.session_state.corrections)
                # ─────────────────────────────────────────────────────────────

                with st.spinner("🤖 Generating Manager Handover with Gemini..."):
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
                        st.error(f"❌ Manager handover generation failed: {e}")
                        st.stop()

                with st.spinner("🤖 Generating Technical Successor Handover with Gemini..."):
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
                        st.error(f"❌ New hire handover generation failed: {e}")
                        st.stop()

                with st.spinner("🤖 Weaving Employee Notes & Tribal Knowledge with Gemini..."):
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
                        st.warning(f"Employee handover note: {e}")
                        st.session_state.employee_handover = DEMO_EMPLOYEE_HANDOVER

                st.session_state.page = "handover"
                st.rerun()

    with col_gen2:
        if st.button("← Back to Employee View", use_container_width=True):
            st.session_state.page = "employee"
            st.rerun()

    if btn_disabled:
        st.caption("⬆️ Sign off on all sections above to unlock handover generation.")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 5: HANDOVER PACKAGE (Executive Handover Document Presentation)
# ═══════════════════════════════════════════════════════════════════════════════
elif st.session_state.page == "handover":
    step_indicator("handover")

    if not st.session_state.manager_handover or not st.session_state.newhire_handover:
        st.error("Handover documents not yet generated. Please complete Review first.")
        if st.button("← Back to Review"):
            st.session_state.page = "review"
            st.rerun()
        st.stop()

    if st.session_state.is_demo:
        st.markdown("""
        <div class="kb-banner-demo">
            <span>🎭</span>
            <div><b>Demo Mode:</b> Displaying finalized, multi-perspective handover documents for <b>Sarah Chen</b> (PayFlow). Ready for Markdown export.</div>
        </div>
        """, unsafe_allow_html=True)

    employee = st.session_state.employee_name or "Departing Engineer"
    project = st.session_state.project_role or "Key System Contributor"

    # Executive Plum Container
    st.markdown(f"""
    <div class="kb-panel-plum" style="margin-bottom:1.5rem;">
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:0.5rem;">
            <div>
                <h2 style="font-size:1.6rem; font-weight:800; margin:0 0 4px 0;">📦 Handover Package Finalized</h2>
                <div style="font-size:0.92rem; color:#E2E8F0;">
                    ✅ All sections reviewed, enriched with employee context, and approved by management.
                </div>
            </div>
            <div style="background:var(--color-orange); color:#1E1B26; padding:6px 16px; border-radius:9999px; font-size:0.8rem; font-weight:800;">
                AUDITED & APPROVED
            </div>
        </div>
        <div style="margin-top:1rem; font-size:0.88rem; color:#CBD5E1;">
            <b>Knowledge Holder:</b> {employee} &nbsp;|&nbsp; <b>Scope:</b> {project}
        </div>
    </div>
    """, unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs(["👔 Manager View", "👩‍💻 Technical Successor View", "👤 Employee Notes"])

    with tab1:
        st.markdown("### 👔 Manager Handover Document")
        st.markdown("*Executive risk summary, business impact, vendor expiration timeline, and required management actions.*")
        st.markdown("---")
        st.markdown(st.session_state.manager_handover)
        st.markdown("---")

        manager_md = st.session_state.manager_handover
        st.download_button(
            label="📥 Download Manager Handover (Markdown)",
            data=manager_md,
            file_name=f"handover_manager_{employee.replace(' ', '_')}.md",
            mime="text/markdown",
            use_container_width=True,
        )

    with tab2:
        st.markdown("### 👩‍💻 Technical Successor Handover")
        st.markdown("*Deep architectural rationale, known landmines, critical paths, and local setup checklist.*")
        st.markdown("---")
        st.markdown(st.session_state.newhire_handover)
        st.markdown("---")

        newhire_md = st.session_state.newhire_handover
        st.download_button(
            label="📥 Download Successor Handover (Markdown)",
            data=newhire_md,
            file_name=f"handover_successor_{employee.replace(' ', '_')}.md",
            mime="text/markdown",
            use_container_width=True,
        )

    with tab3:
        st.markdown("### 👤 Employee Notes & Tribal Knowledge")
        st.markdown("*First-person context, verified architectural decisions, resolved blind spots, and unwritten operational tips.*")
        st.markdown("---")
        emp_notes_content = st.session_state.employee_handover or DEMO_EMPLOYEE_HANDOVER
        st.markdown(emp_notes_content)
        st.markdown("---")

        st.download_button(
            label="📥 Download Employee Notes (Markdown)",
            data=emp_notes_content,
            file_name=f"handover_employee_{employee.replace(' ', '_')}.md",
            mime="text/markdown",
            use_container_width=True,
        )

    st.markdown("---")
    col_reset1, col_reset2 = st.columns(2)
    with col_reset1:
        if st.button("🔄 Start New Handover", use_container_width=True):
            for key in ["knowledge_profile", "is_demo", "approvals", "corrections",
                        "manager_handover", "newhire_handover", "employee_handover",
                        "employee_verifications", "employee_gap_answers", "employee_tribal_knowledge",
                        "all_sources", "employee_name", "project_role", "github_url", "github_token",
                        "pasted_text", "uploaded_files"]:
                if "approvals" in key or "corrections" in key or "verifications" in key or "gap_answers" in key:
                    st.session_state[key] = {}
                elif "sources" in key or "tribal_knowledge" in key:
                    st.session_state[key] = []
                elif key == "uploaded_files":
                    st.session_state[key] = None
                elif key == "is_demo":
                    st.session_state[key] = False
                else:
                    st.session_state[key] = ""
            st.session_state.page = "connect"
            st.rerun()

    with col_reset2:
        if st.button("← Back to Manager Review", use_container_width=True):
            st.session_state.page = "review"
            st.rerun()
