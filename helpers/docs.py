# helpers/docs.py
# Minimal text extraction for PDF/DOCX/TXT/MD + chunking

from typing import List, Dict
from io import BytesIO
import os

from pypdf import PdfReader
try:
    from docx import Document as DocxDocument
except Exception:
    DocxDocument = None

CHUNK_SIZE = 900        # ~600–1200 chars works well
CHUNK_OVERLAP = 120     # small overlap to preserve context

def _ext(name: str) -> str:
    return os.path.splitext(name or "")[1].lower()

def _read_pdf_with_pages(file_bytes: bytes) -> List[Dict[str, any]]:
    """Returns a list of {'page': int, 'text': str}."""
    pages = []
    reader = PdfReader(BytesIO(file_bytes))
    for i, page in enumerate(reader.pages, 1):
        try:
            text = page.extract_text() or ""
            if text.strip():
                pages.append({'page': i, 'text': text})
        except Exception:
            continue
    return pages

def _read_docx(file_bytes: bytes) -> str:
    if DocxDocument is None:
        return ""
    doc = DocxDocument(BytesIO(file_bytes))
    return "\n".join(p.text for p in doc.paragraphs).strip()

def _read_text(file_bytes: bytes) -> str:
    # best-effort decode
    for enc in ("utf-8", "utf-16", "latin-1"):
        try:
            return file_bytes.decode(enc)
        except Exception:
            pass
    return ""

def _chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    text = (text or "").strip()
    if not text:
        return []
    chunks, start, n = [], 0, len(text)
    while start < n:
        end = min(n, start + size)
        chunks.append(text[start:end])
        if end == n:
            break
        start = max(end - overlap, start + 1)
    return chunks

def process_uploads(files) -> Dict[str, List[Dict]]:
    """
    Returns:
      {
        "docs":   [{"filename": str, "text": str}],
        "chunks": [{"id": str, "filename": str, "text": str, "page": int}]
      }
    """
    docs, chunks = [], []
    for fi, f in enumerate(files):
        name = getattr(f, "name", f"file_{fi}")
        raw = f.getvalue() if hasattr(f, "getvalue") else (f.read() or b"")
        ext = _ext(name); text = ""

        if ext == ".pdf":
            pages_data = _read_pdf_with_pages(raw)
            text = "\n".join(p['text'] for p in pages_data)
        elif ext in (".docx",):
            text = _read_docx(raw)
        elif ext in (".txt", ".md", ".csv", ".log"):
            text = _read_text(raw)
        else:
            text = _read_text(raw)  # fallback

        if not text.strip():
            # Skip completely empty files (or return a placeholder if you prefer)
            continue

        docs.append({"filename": name, "text": text})

        # Chunk and label with page numbers
        if ext == ".pdf" and pages_data:
            for page_info in pages_data:
                page_num = page_info['page']
                page_text = page_info['text']
                for ci, chunk_text in enumerate(_chunk_text(page_text)):
                    chunks.append({
                        "id": f"{name}__p{page_num}_chunk_{ci:04d}",
                        "filename": name,
                        "text": chunk_text,
                        "page": page_num
                    })
        else: # For non-PDF files, chunk the whole text
            for ci, chunk_text in enumerate(_chunk_text(text)):
                chunks.append({
                    "id": f"{name}__chunk_{ci:04d}",
                    "filename": name, "text": chunk_text, "page": 1
                })

    return {"docs": docs, "chunks": chunks}
