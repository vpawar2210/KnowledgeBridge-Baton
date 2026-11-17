"""Safe table rendering fallback for environments where pyarrow/pandas is blocked."""

import os
from typing import Any, Dict, List, Optional


def format_table_markdown(rows: Optional[List[Dict[str, Any]]]) -> str:
    """Format a list of dicts as a Markdown table string.
    
    Rules:
    - Empty list or falsy input returns 'No data'.
    - Column order matches the keys of the first row.
    - Missing keys in subsequent rows are rendered as empty strings.
    - Pipe characters '|' and newlines inside cell values are escaped.
    - Lists and tuples are converted to comma-separated text.
    """
    if not rows or not isinstance(rows, list):
        return "No data"

    first_row = rows[0]
    if not isinstance(first_row, dict) or not first_row:
        return "No data"

    columns = list(first_row.keys())

    def _format_cell(val: Any) -> str:
        if val is None:
            return ""
        if isinstance(val, (list, tuple)):
            s = ", ".join(str(item) for item in val)
        else:
            s = str(val)
        # Escape pipe and newlines
        s = s.replace("|", "\\|")
        s = s.replace("\r\n", "\\n").replace("\n", "\\n").replace("\r", "\\n")
        return s

    headers = [_format_cell(c) for c in columns]
    header_line = "| " + " | ".join(headers) + " |"
    separator_line = "| " + " | ".join(["---"] * len(columns)) + " |"

    data_lines = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        cells = [_format_cell(r.get(c, "")) for c in columns]
        data_lines.append("| " + " | ".join(cells) + " |")

    return "\n".join([header_line, separator_line] + data_lines)


def safe_table(rows: Any) -> None:
    """Render rows as a table, falling back to Markdown if pandas/pyarrow is blocked or BATON_SAFE_TABLES=1.
    
    If BATON_SAFE_TABLES is set to '1' or st.table raises ImportError / OSError,
    it safely renders a Markdown table via st.markdown.
    Otherwise it calls st.table(rows) exactly as before.
    """
    import streamlit as st

    if os.environ.get("BATON_SAFE_TABLES") == "1":
        st.markdown(format_table_markdown(rows))
        return

    try:
        st.table(rows)
    except (ImportError, OSError):
        st.markdown(format_table_markdown(rows))
