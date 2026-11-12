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
        return raw.decode("utf-8", errors="replace")
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
