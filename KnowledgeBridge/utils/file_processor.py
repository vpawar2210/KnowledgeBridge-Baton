"""
File processor for Baton (Knowledge Handover Platform).
Handles PDF, TXT, and MD file parsing.
"""

import io


def process_files(uploaded_files) -> list[dict]:
    """
    Process uploaded Streamlit file objects.

    Args:
        uploaded_files: List of Streamlit UploadedFile objects

    Returns:
        List of dicts with keys: content, source, source_type
    """
    results = []
    for uploaded_file in uploaded_files:
        filename = uploaded_file.name
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

        try:
            content = _extract_content(uploaded_file, ext, filename)
            results.append({
                "content": content,
                "source": filename,
                "source_type": "file"
            })
        except Exception as e:
            results.append({
                "content": f"[Error reading {filename}: {e}]",
                "source": filename,
                "source_type": "file"
            })
    return results


def _extract_content(uploaded_file, ext: str, filename: str) -> str:
    """Extract text content based on file type."""
    if ext == "pdf":
        return _extract_pdf(uploaded_file, filename)
    elif ext in ("txt", "md", "markdown", "rst", "log"):
        raw = uploaded_file.read()
        return raw.decode("utf-8-sig", errors="replace")
    else:
        # Try to decode as text for unknown types
        try:
            raw = uploaded_file.read()
            return raw.decode("utf-8", errors="replace")
        except Exception:
            raise ValueError(f"Unsupported file type: .{ext}")


def _extract_pdf(uploaded_file, filename: str) -> str:
    """Extract text from a PDF file using pdfplumber."""
    try:
        import pdfplumber
        pdf_bytes = uploaded_file.read()
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            pages = []
            for i, page in enumerate(pdf.pages, 1):
                text = page.extract_text() or ""
                if text.strip():
                    pages.append(f"[Page {i}]\n{text}")
            if not pages:
                return f"[PDF {filename} appears to be image-based or empty — no text extracted]"
            return "\n\n".join(pages)
    except ImportError:
        raise RuntimeError("pdfplumber not installed. Run: pip install pdfplumber")
    except Exception as e:
        raise RuntimeError(f"Failed to parse PDF {filename}: {e}")


def _extract_pdf_from_bytes(pdf_bytes: bytes, filename: str) -> str:
    """
    Internal helper: extract text from PDF bytes using pdfplumber.
    Returns the page-joined text, or raises RuntimeError on failure.
    """
    import pdfplumber
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        pages = []
        for i, page in enumerate(pdf.pages, 1):
            text = page.extract_text() or ""
            if text.strip():
                pages.append(f"--- Page {i} ---\n{text}")
        if not pages:
            return ""
        return "\n\n".join(pages)


# ── Safety checks ─────────────────────────────────────────────────────────────
_REPLACEMENT_CHAR = "\ufffd"
_CTRL_CHARS = set(range(0, 32)) - {9, 10, 13}  # allow tab, LF, CR


def _is_garbage(text: str) -> bool:
    """Return True if the text looks like garbled binary decoded as text."""
    if not text:
        return False
    replacement_ratio = text.count(_REPLACEMENT_CHAR) / len(text)
    if replacement_ratio > 0.05:
        return True
    ctrl_count = sum(1 for ch in text if ord(ch) in _CTRL_CHARS)
    if len(text) > 0 and ctrl_count / len(text) > 0.05:
        return True
    return False


# ── Public preview API ────────────────────────────────────────────────────────

def get_preview(file_name: str, data: bytes, max_chars: int = 20000) -> dict:
    """
    Return a preview dict for file bytes.

    Shape:
        {
          "kind": "text" | "pdf_text" | "pdf_no_text" | "unsupported",
          "text": str,
          "pages": int | None,
          "truncated": bool,
          "note": str,
        }
    """
    ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
    _empty = {"text": "", "pages": None, "truncated": False, "note": ""}

    # ── PDF ──────────────────────────────────────────────────────────────────
    if ext == "pdf":
        try:
            raw_text = _extract_pdf_from_bytes(data, file_name)
        except Exception:
            return {**_empty, "kind": "pdf_no_text",
                    "note": "This PDF could not be read."}

        if not raw_text or len(raw_text.strip()) < 20:
            return {**_empty, "kind": "pdf_no_text",
                    "note": "This PDF has no readable text. It may be a scanned image."}

        if _is_garbage(raw_text):
            return {**_empty, "kind": "pdf_no_text",
                    "note": "This PDF could not be read."}

        # Count pages (number of "--- Page N ---" markers)
        page_count = raw_text.count("--- Page ")
        truncated = len(raw_text) > max_chars
        display_text = raw_text[:max_chars] if truncated else raw_text
        return {
            "kind": "pdf_text",
            "text": display_text,
            "pages": page_count if page_count > 0 else None,
            "truncated": truncated,
            "note": "",
        }

    # ── Plain text / Markdown ─────────────────────────────────────────────────
    if ext in ("txt", "md", "markdown"):
        # Try UTF-8 with BOM first, then fall back to errors="replace"
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = data.decode("utf-8", errors="replace")

        if _is_garbage(text):
            return {**_empty, "kind": "unsupported",
                    "note": "Preview is not available for this file type. Use Download."}

        truncated = len(text) > max_chars
        display_text = text[:max_chars] if truncated else text
        return {
            "kind": "text",
            "text": display_text,
            "pages": None,
            "truncated": truncated,
            "note": "",
        }

    # ── Everything else ───────────────────────────────────────────────────────
    return {**_empty, "kind": "unsupported",
            "note": "Preview is not available for this file type. Use Download."}
