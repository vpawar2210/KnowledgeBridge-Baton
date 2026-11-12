# 🏃‍♂️ Baton — Knowledge Handover Platform

> **Prevent Critical Knowledge From Leaving With People**  
> Built for the Knowledge Handover Hackathon by **Codepunethinkers** (Vaibhav Pawar)

Baton is an AI-powered institutional memory preservation platform that captures, verifies, and transfers critical engineering and project context when a team member departs.

---

## 🎯 The Core Problem

When an employee or key contributor leaves, years of undocumented decisions, architecture trade-offs, deployment gotchas ("tribal knowledge"), and vendor context leave with them. 

Baton converts scattered project activity (GitHub commits, PRs, issues, architecture docs, and team communications) into **auditable, evidence-backed, human-approved handover packages**.

---

## 🏆 The 5-Step Judging Workflow

```
01 Connect ──> 02 Reconstruct ──> 03 Employee Hub ──> 04 Manager Review ──> 05 Handover Packages
```

1. **01 Connect:** Ingest authorized project sources — GitHub repositories (README, commits, issues, PRs), architecture docs (PDF, Markdown, text), and pasted communications.
2. **02 Reconstruct:** Gemini 1.5 Flash reconstructs the decision log, identifies critical risks, scores confidence (🟢 High, 🟡 Medium, 🔴 Low), and flags missing blind spots.
3. **03 Employee Hub (Tacit Knowledge Capture):** The departing employee confirms or clarifies AI findings, answers questions the AI couldn't find, and records unwritten tribal knowledge.
4. **04 Manager Review:** The manager audits the risk radar, notes mitigation plans, and performs mandatory section sign-offs. Handover generation is gated until 100% approved.
5. **05 Handover Packages:** Generates 3 distinct, tailored handover packages ready for view or `.md` download:
   - 👔 **Executive / Manager Handover:** Business impact, vendor contract deadlines, staffing action items.
   - 👩‍💻 **Technical Successor Handover:** Deep architectural rationale, *"What NOT To Break"*, gotchas, and local setup checklist.
   - 👤 **Employee Notes & Tribal Knowledge:** First-person context, verified trade-offs, and resolved open questions.

---

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Launch the Application
```bash
python -m streamlit run app.py
```
Open your browser at `http://localhost:8501`.

### 3. Demo Mode vs. Live Gemini
- **Demo Mode:** Click **"🎭 Load Demo — See Full Example"** to explore the complete 5-step workflow with a comprehensive synthetic dataset (Sarah Chen / PayFlow microservice) with zero API keys required.
- **Live Gemini Mode:** Enter your Google Gemini API key (free tier available at [aistudio.google.com](https://aistudio.google.com/app/apikey)) to analyze live GitHub repositories and custom documents.

---

## 📁 Project Architecture

```
KnowledgeBridge/
├── app.py                      # Main Streamlit application (5-step interactive workflow)
├── requirements.txt            # Python dependencies
├── .streamlit/
│   └── config.toml             # Clean SaaS theme configuration
├── utils/
│   ├── __init__.py
│   ├── gemini_engine.py        # Gemini extraction & synthesis prompts
│   ├── github_connector.py     # GitHub REST API v3 parser (commits, PRs, issues)
│   └── file_processor.py       # PDF/TXT/MD ingestion engine
├── report.md                   # Full technical architecture and delivery report
├── Round1_Submission.md        # Problem definition, user research, and feasibility
└── README.md                   # Project documentation
```

---

## 🎨 Design System
Baton follows an accessible, high-clarity SaaS interface:
- **Clean Neutral Canvas:** `#EDF2F5` background with elevated white cards (`#FFFFFF`).
- **Brand Identity:** Deep plum framing (`#29102F`) with electric blue accents (`#245BEA`).
- **High-Contrast Primary Actions:** Warm orange CTAs (`#F49B54`) delivering a 10.5:1 contrast ratio (exceeding WCAG AAA).
- **Evidence Badges:** Color-coded confidence indicators and source citations for total auditability.
