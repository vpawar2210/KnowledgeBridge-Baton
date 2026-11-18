"""Tests verifying that HTML rendering helpers properly escape user-supplied strings.
Enforces constraint 4: Never add unescaped interpolation.
"""

import html
import pytest
from app import (
    render_file_row,
    render_citation,
    render_audit_entry,
    render_receipt_card,
    render_stat_card,
    source_badge,
    confidence_badge,
)

MALICIOUS_INPUT = '<script>alert("xss")</script>&<"test">'


def test_render_file_row_escaping():
    """Verify filename is escaped in render_file_row."""
    out = render_file_row(MALICIOUS_INPUT, 1024)
    assert "<script>" not in out
    assert html.escape(MALICIOUS_INPUT) in out or "&lt;script&gt;" in out


def test_render_citation_escaping():
    """Verify source and excerpt are escaped in render_citation."""
    out = render_citation(MALICIOUS_INPUT, f"some text {MALICIOUS_INPUT}")
    assert "<script>" not in out
    assert "&lt;script&gt;" in out


def test_render_audit_entry_escaping():
    """Verify who, action, and reason are escaped in render_audit_entry."""
    entry = {
        "timestamp": "2026-11-18 20:00:00",
        "who": MALICIOUS_INPUT,
        "action": f"Action {MALICIOUS_INPUT}",
        "reason": f"Reason {MALICIOUS_INPUT}",
    }
    out = render_audit_entry(entry)
    assert "<script>" not in out
    assert "&lt;script&gt;" in out


def test_render_receipt_card_escaping():
    """Verify name, project, and employee are escaped in render_receipt_card."""
    out = render_receipt_card(
        name=MALICIOUS_INPUT,
        timestamp="2026-11-18 20:00:00",
        project=MALICIOUS_INPUT,
        employee=MALICIOUS_INPUT,
    )
    assert "<script>" not in out
    assert "&lt;script&gt;" in out


def test_render_stat_card_escaping():
    """Verify label and number are escaped in render_stat_card."""
    out = render_stat_card(label=MALICIOUS_INPUT, number=MALICIOUS_INPUT)
    assert "<script>" not in out
    assert "&lt;script&gt;" in out
