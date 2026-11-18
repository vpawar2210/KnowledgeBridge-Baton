"""utils/verifier.py

Grounding and citation verification engine for Baton.
Mathematically validates that quotes, decisions, and risks are strictly
grounded in underlying source documents, detecting:
- Fabricated / hallucinated quotes
- Tampered quotes (altered numbers, modified words)
- Nonexistent or mismatched source citations
- Adversarial prompt injection payloads in quotes
- Vacuous or trivially short quotes (< 15 characters)
"""

import re
from typing import Dict, Any, Tuple, Optional

MIN_QUOTE_LENGTH = 15

# Adversarial prompt injection signatures commonly attempted via malicious documents or model output
INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|prior)\s+instructions",
    r"you\s+are\s+now\s+in\s+developer\s+mode",
    r"system\s*prompt\s*override",
    r"<script[\s\S]*?>",
    r"admin\s*=\s*true",
    r"drop\s+table",
]


def normalize_text(text: str) -> str:
    """Normalize whitespace and case for deterministic substring checking."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip().lower()


def verify_quote(quote: str, source_text: str) -> Tuple[bool, str]:
    """Verify that a quote string is genuinely grounded in source_text.

    Returns:
        (is_valid: bool, reason: str)
    """
    if not quote or not quote.strip():
        return False, "Empty or missing quote"

    cleaned_quote = quote.strip()
    if len(cleaned_quote) < MIN_QUOTE_LENGTH:
        return False, f"Quote is too short (< {MIN_QUOTE_LENGTH} chars) to serve as verified evidence"

    # Detect adversarial injection payloads
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, cleaned_quote, re.IGNORECASE):
            return False, "Adversarial prompt injection pattern detected in quote"

    norm_quote = normalize_text(cleaned_quote)
    norm_source = normalize_text(source_text)

    if norm_quote not in norm_source:
        return False, "Fabricated or tampered quote: quote text does not exist in source document"

    return True, "Verified: quote is grounded in source document"


def verify_claim(claim: Dict[str, Any], source_documents: Dict[str, str]) -> Tuple[bool, str]:
    """Verify that a claim (decision/risk) is grounded in its cited source document.

    Args:
        claim: Dict with keys 'source' (or 'source_document_id'), and 'excerpt' (or 'source_quote')
        source_documents: Dict mapping source_id -> document text

    Returns:
        (is_valid: bool, reason: str)
    """
    source_id = (
        claim.get("source")
        or claim.get("source_document_id")
        or claim.get("source_note_id")
    )
    if not source_id:
        return False, "Missing source citation in claim"

    if source_id not in source_documents:
        return False, f"Cited source '{source_id}' does not exist in project documents"

    quote = claim.get("excerpt") or claim.get("source_quote") or claim.get("text")
    if not quote:
        return False, "Missing supporting quote in claim"

    source_text = source_documents[source_id]
    return verify_quote(quote, source_text)
