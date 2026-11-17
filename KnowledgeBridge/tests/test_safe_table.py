import os
from unittest.mock import patch, MagicMock
import pytest
from utils.safe_table import format_table_markdown, safe_table


def test_markdown_normal_rows():
    """Verify normal rows format into a standard markdown table."""
    rows = [
        {"Name": "Alice", "Role": "Engineer", "Status": "Active"},
        {"Name": "Bob", "Role": "Manager", "Status": "Pending"}
    ]
    md = format_table_markdown(rows)
    lines = md.split("\n")
    assert len(lines) == 4
    assert lines[0] == "| Name | Role | Status |"
    assert lines[1] == "| --- | --- | --- |"
    assert lines[2] == "| Alice | Engineer | Active |"
    assert lines[3] == "| Bob | Manager | Pending |"


def test_markdown_empty_list():
    """Verify empty list, None, or empty input returns 'No data'."""
    assert format_table_markdown([]) == "No data"
    assert format_table_markdown(None) == "No data"
    assert format_table_markdown([{}]) == "No data"


def test_markdown_missing_keys():
    """Verify missing keys in rows are replaced with empty strings without raising errors."""
    rows = [
        {"Name": "Sarah Chen", "Role": "Employee", "Access": "Full"},
        {"Name": "Marcus Vance"}  # missing 'Role' and 'Access'
    ]
    md = format_table_markdown(rows)
    lines = md.split("\n")
    assert lines[2] == "| Sarah Chen | Employee | Full |"
    assert lines[3] == "| Marcus Vance |  |  |"


def test_markdown_pipe_and_newline_escaping():
    """Verify pipe characters and newlines are safely escaped inside table cells."""
    rows = [
        {
            "Title": "Pipe | Test",
            "Description": "Line 1\nLine 2\r\nLine 3"
        }
    ]
    md = format_table_markdown(rows)
    lines = md.split("\n")
    # Must not contain unescaped pipes breaking column count
    assert "\\|" in lines[2]
    assert "\\n" in lines[2]
    # Total table rows must still be 3 (header, separator, 1 data row)
    assert len(lines) == 3


def test_markdown_list_values():
    """Verify lists or tuples in cell values are converted to comma-separated text."""
    rows = [
        {"Role": "Manager", "Grants": ["read", "write", "admin"]}
    ]
    md = format_table_markdown(rows)
    lines = md.split("\n")
    assert lines[2] == "| Manager | read, write, admin |"


def test_markdown_column_order():
    """Verify column order strictly preserves the key order of the first row."""
    rows = [
        {"Z": "1", "A": "2", "M": "3"},
        {"Z": "4", "A": "5", "M": "6"}
    ]
    md = format_table_markdown(rows)
    lines = md.split("\n")
    assert lines[0] == "| Z | A | M |"
    assert lines[2] == "| 1 | 2 | 3 |"


def test_safe_table_env_var(monkeypatch):
    """Verify BATON_SAFE_TABLES=1 directly renders via st.markdown."""
    monkeypatch.setenv("BATON_SAFE_TABLES", "1")
    rows = [{"Name": "Sarah", "Role": "Employee"}]

    with patch("streamlit.markdown") as mock_md, patch("streamlit.table") as mock_table:
        safe_table(rows)
        mock_table.assert_not_called()
        mock_md.assert_called_once()
        assert "| Sarah | Employee |" in mock_md.call_args[0][0]


def test_safe_table_fallback_on_import_error(monkeypatch):
    """Verify safe_table catches pyarrow/pandas ImportError and falls back to st.markdown."""
    monkeypatch.delenv("BATON_SAFE_TABLES", raising=False)
    rows = [{"Name": "David", "Role": "Manager"}]

    with patch("streamlit.table", side_effect=ImportError("DLL load failed: pyarrow")), patch("streamlit.markdown") as mock_md:
        safe_table(rows)
        mock_md.assert_called_once()
        assert "| David | Manager |" in mock_md.call_args[0][0]


def test_safe_table_fallback_on_os_error(monkeypatch):
    """Verify safe_table catches OSError and falls back to st.markdown."""
    monkeypatch.delenv("BATON_SAFE_TABLES", raising=False)
    rows = [{"Name": "Marcus", "Role": "Successor"}]

    with patch("streamlit.table", side_effect=OSError("Application Control blocked")):
        with patch("streamlit.markdown") as mock_md:
            safe_table(rows)
            mock_md.assert_called_once()
            assert "| Marcus | Successor |" in mock_md.call_args[0][0]
