import io
from pathlib import Path


def parse_document(filename: str, content: bytes) -> str:
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
            import PyPDF2
            reader = PyPDF2.PdfReader(io.BytesIO(content))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception:
            return _unstructured_parse(content, filename)

    if ext == ".docx":
        try:
            from docx import Document as DocxDocument
            doc = DocxDocument(io.BytesIO(content))
            return "\n".join(p.text for p in doc.paragraphs)
        except Exception:
            return _unstructured_parse(content, filename)

    return _unstructured_parse(content, filename)


def _unstructured_parse(content: bytes, filename: str) -> str:
    try:
        from unstructured.partition.auto import partition
        elements = partition(file=io.BytesIO(content), metadata_filename=filename)
        return "\n".join(str(e) for e in elements)
    except Exception as e:
        raise ValueError(f"Could not parse {filename}: {e}")
