"""
Gemini AI engine for Baton (Knowledge Handover Platform).
Uses google-genai SDK (v3.0.0+) on v1beta with gemini-3.8-flash,
with automatic REST fallback to ensure seamless compatibility with AQ. keys.
"""

import json
import re
import requests
from google import genai
from google.genai import types

# Modern Google Gemini Models for 2026
PRIMARY_MODEL = "gemini-3.8-flash"
FALLBACK_MODELS = ["gemini-3.8-flash", "gemini-3.5-flash", "gemini-flash-latest"]

ANALYZE_PROMPT = """
You are a Knowledge Extraction AI. You analyze documents and conversations left behind by a departing employee and reconstruct a structured knowledge profile.

Given the following source materials, extract and structure ALL useful knowledge.

SOURCE MATERIALS:
{sources_text}

Extract and return a JSON object with EXACTLY this structure:
{{
  "decisions": [
    {{
      "text": "Description of the decision made",
      "source": "exact source name/filename",
      "source_type": "file|github|text",
      "confidence": "HIGH|MEDIUM|LOW",
      "excerpt": "verbatim or close excerpt from source that supports this"
    }}
  ],
  "risks": [
    {{
      "text": "Description of the risk or dependency concern",
      "source": "exact source name",
      "confidence": "HIGH|MEDIUM|LOW",
      "excerpt": "supporting excerpt"
    }}
  ],
  "unresolved": [
    {{
      "question": "What is unknown or unclear?",
      "why_unknown": "Why this information could not be found in the sources"
    }}
  ],
  "contacts": [
    {{
      "name": "Person name",
      "role": "Their role or relationship to the project",
      "source": "exact source name"
    }}
  ],
  "dependencies": [
    {{
      "item": "Name of dependency (service, team, vendor, library)",
      "description": "What it does and why it matters",
      "source": "exact source name"
    }}
  ],
  "summary": "A 3-5 sentence executive summary of the knowledge being handed over"
}}

CONFIDENCE RULES:
- HIGH: Multiple sources agree on the same information
- MEDIUM: Single source mentions it explicitly
- LOW: Inferred or mentioned ambiguously

Extract at minimum 4-6 decisions, 2-4 risks, 2-3 unresolved questions, any contacts, and any dependencies.
Return ONLY valid JSON. No markdown. No explanation. Just the JSON object.
"""


MANAGER_HANDOVER_PROMPT = """
You are writing a **Manager-level Knowledge Handover Document**.

Based on this knowledge profile:
{knowledge_json}

Employee: {employee_name}
Project/Role: {project_role}

Write a professional Markdown document with these sections:
1. ## Executive Summary
2. ## Key Decisions & Rationale (high-level, with business impact)
3. ## Critical Risks & Mitigation (what could go wrong, what to watch)
4. ## Ownership & Contacts (who to call for what)
5. ## External Dependencies & Vendor Relationships
6. ## Timeline Considerations (what needs attention soon)
7. ## Open Items Requiring Management Action

Write for a non-technical manager. Focus on business risk, ownership, and timeline.
Use clear, professional language. Include ⚠️ for urgent items.
"""


NEWHIRE_HANDOVER_PROMPT = """
You are writing a **New Hire / Technical Successor Knowledge Handover Document**.

Based on this knowledge profile:
{knowledge_json}

Employee: {employee_name}
Project/Role: {project_role}

Write a comprehensive Markdown document with these sections:
1. ## Welcome & Context
2. ## Architecture & Technical Decisions (WHY things were built this way)
3. ## What NOT To Break (critical paths, gotchas, known landmines)
4. ## Who To Call (contacts with context on when/why to reach them)
5. ## Unresolved Technical Debt & Open Questions
6. ## External Dependencies & Integration Points
7. ## Things That Were Tried (and failed — save yourself the time)
8. ## Getting Started Checklist

Write for a technical successor. Be detailed, honest, and practical.
Use ⚠️ for landmines, 💡 for tips, 🔗 for important links/references.
"""


EMPLOYEE_HANDOVER_PROMPT = """
You are writing an **Employee Notes & Tribal Knowledge Addendum** for a knowledge handover.

The departing employee has reviewed the AI-extracted knowledge profile and provided corrections,
gap answers, and tribal knowledge. Weave these into a well-structured Markdown document.

Knowledge profile:
{knowledge_json}

Employee: {employee_name}
Project/Role: {project_role}

Employee's corrections and context:
{employee_corrections}

Employee's answers to unresolved questions:
{gap_answers}

Employee's tribal knowledge items:
{tribal_knowledge}

Write a comprehensive Markdown document with these sections:
1. ## Employee Notes & Corrections — Items the employee flagged as incorrect or added context to
2. ## Resolved Questions — Questions the AI couldn't answer that the employee has now answered
3. ## Tribal Knowledge — Tips, warnings, undocumented processes, history, and relationship context
4. ## Additional Recommendations — Final thoughts from the departing employee

Write in first person from the employee's perspective. Be practical, honest, and detailed.
Use ⚠️ for warnings, 💡 for tips, 📝 for notes, 🚫 for "don't do this" items.
"""


def _build_client(api_key: str) -> genai.Client:
    """Create a Gemini client configured for v1beta with the given API key."""
    return genai.Client(api_key=api_key.strip(), http_options={"api_version": "v1beta"})


def _call_gemini(prompt: str, api_key: str, temperature: float = 0.2, max_output_tokens: int = 4096) -> str:
    """
    Call Gemini using official google-genai SDK (v1beta), with fallback across
    modern models and direct REST endpoint to guarantee compatibility with AQ. keys.
    """
    key = api_key.strip()
    client = _build_client(key)

    # 1. Try SDK with candidate models
    for model_name in FALLBACK_MODELS:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=temperature,
                    max_output_tokens=max_output_tokens,
                ),
            )
            if response and response.text:
                return response.text
        except Exception:
            continue

    # 2. Try Direct Google Generative Language REST Endpoint (v1beta)
    for model_name in FALLBACK_MODELS:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={key}"
            headers = {
                "Content-Type": "application/json",
                "x-goog-api-key": key,
            }
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": temperature,
                    "maxOutputTokens": max_output_tokens,
                }
            }
            res = requests.post(url, headers=headers, json=payload, timeout=60)
            if res.status_code == 200:
                data = res.json()
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts:
                        return parts[0].get("text", "")
        except Exception:
            continue

    raise RuntimeError(
        "Gemini API request failed across all candidate models (gemini-3.8-flash, gemini-3.5-flash). "
        "Please verify your AQ. API key has the Generative Language API enabled."
    )


def analyze_sources(texts: list[dict], api_key: str) -> dict:
    """
    Analyze a list of source texts and extract structured knowledge.

    Args:
        texts: List of dicts with keys: content, source, source_type
        api_key: Gemini API key (supports AQ. keys)

    Returns:
        Structured knowledge profile dict
    """
    # Build the sources text block
    sources_text = ""
    for i, t in enumerate(texts, 1):
        icon = {"file": "📁", "github": "🐙", "text": "📝"}.get(t.get("source_type", "text"), "📄")
        sources_text += f"\n\n--- SOURCE {i}: {icon} [{t['source_type'].upper()}] {t['source']} ---\n"
        content = t["content"]
        if len(content) > 8000:
            content = content[:8000] + "\n... [truncated for brevity]"
        sources_text += content

    prompt = ANALYZE_PROMPT.format(sources_text=sources_text)
    raw = _call_gemini(prompt, api_key, temperature=0.2, max_output_tokens=4096).strip()

    # Strip markdown code fences if present
    raw = re.sub(r'^```(?:json)?\s*', '', raw, flags=re.MULTILINE)
    raw = re.sub(r'\s*```$', '', raw, flags=re.MULTILINE)
    raw = raw.strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Gemini returned invalid JSON: {e}\nRaw response: {raw[:500]}")


def generate_manager_handover(knowledge_profile: dict, employee_name: str, project_role: str, api_key: str) -> str:
    """Generate a manager-level handover document."""
    prompt = MANAGER_HANDOVER_PROMPT.format(
        knowledge_json=json.dumps(knowledge_profile, indent=2),
        employee_name=employee_name,
        project_role=project_role,
    )
    return _call_gemini(prompt, api_key, temperature=0.4, max_output_tokens=3000)


def generate_newhire_handover(knowledge_profile: dict, employee_name: str, project_role: str, api_key: str) -> str:
    """Generate a new hire technical handover document."""
    prompt = NEWHIRE_HANDOVER_PROMPT.format(
        knowledge_json=json.dumps(knowledge_profile, indent=2),
        employee_name=employee_name,
        project_role=project_role,
    )
    return _call_gemini(prompt, api_key, temperature=0.4, max_output_tokens=3000)


def generate_employee_handover(
    knowledge_profile: dict,
    employee_name: str,
    project_role: str,
    employee_corrections: dict,
    gap_answers: dict,
    tribal_knowledge: list,
    api_key: str
) -> str:
    """Generate an employee notes and tribal knowledge handover document."""
    prompt = EMPLOYEE_HANDOVER_PROMPT.format(
        knowledge_json=json.dumps(knowledge_profile, indent=2),
        employee_name=employee_name,
        project_role=project_role,
        employee_corrections=json.dumps(employee_corrections, indent=2) if isinstance(employee_corrections, (dict, list)) else str(employee_corrections),
        gap_answers=json.dumps(gap_answers, indent=2) if isinstance(gap_answers, (dict, list)) else str(gap_answers),
        tribal_knowledge=json.dumps(tribal_knowledge, indent=2) if isinstance(tribal_knowledge, (dict, list)) else str(tribal_knowledge),
    )
    return _call_gemini(prompt, api_key, temperature=0.4, max_output_tokens=3000)
