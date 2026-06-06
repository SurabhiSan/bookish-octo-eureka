import io
import os
from pathlib import Path
from typing import Tuple


def parse_document(filename: str, content: bytes) -> str:
    """Return plain text from raw file bytes."""
    ext = Path(filename).suffix.lower()

    if ext in (".txt", ".md"):
        return content.decode("utf-8", errors="replace")

    if ext == ".csv":
        import csv
        text = content.decode("utf-8", errors="replace")
        reader = csv.reader(io.StringIO(text))
        return "\n".join(", ".join(row) for row in reader)

    if ext == ".pdf":
        try:
            from docling.document_converter import DocumentConverter
            conv = DocumentConverter()
            result = conv.convert(io.BytesIO(content), filename=filename)
            return result.document.export_to_markdown()
        except Exception:
            pass
        # Fallback: unstructured
        return _unstructured_parse(content, filename)

    if ext == ".docx":
        try:
            from docx import Document as DocxDocument
            doc = DocxDocument(io.BytesIO(content))
            return "\n".join(p.text for p in doc.paragraphs)
        except Exception:
            pass
        return _unstructured_parse(content, filename)

    return _unstructured_parse(content, filename)


def _unstructured_parse(content: bytes, filename: str) -> str:
    try:
        from unstructured.partition.auto import partition
        elements = partition(file=io.BytesIO(content), metadata_filename=filename)
        return "\n".join(str(e) for e in elements)
    except Exception as e:
        raise ValueError(f"Could not parse {filename}: {e}")
