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

def _read_pdf(file_bytes: bytes) -> str:
    parts = []
    reader = PdfReader(BytesIO(file_bytes))
    for page in reader.pages:
        try:
            parts.append(page.extract_text() or "")
        except Exception:
            continue
    return "\n".join(parts).strip()

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
        "chunks": [{"id": str, "filename": str, "text": str}]
      }
    """
    docs, chunks = [], []
    for fi, f in enumerate(files):
        name = getattr(f, "name", f"file_{fi}")
        raw = f.getvalue() if hasattr(f, "getvalue") else (f.read() or b"")
        ext = _ext(name)

        if ext == ".pdf":
            text = _read_pdf(raw)
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

        # Chunk and label
        for ci, chunk in enumerate(_chunk_text(text)):
            chunks.append({
                "id": f"{name}__chunk_{ci:04d}",
                "filename": name,
                "text": chunk
            })

    return {"docs": docs, "chunks": chunks}
