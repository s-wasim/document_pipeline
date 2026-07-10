import os
import uuid
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image

from app.db import get_session, Document

DATA_DIR = Path(__file__).parent.parent / "data"
DOCS_DIR = DATA_DIR / "docs"
PREVIEWS_DIR = DATA_DIR / "previews"
ALLOWED_MIMES = {
    "application/pdf": ".pdf",
    "image/png": ".png",
    "image/jpeg": ".jpg",
}
MAX_SIZE = 15 * 1024 * 1024
MAX_PAGES = 20


def guess_mime(filename: str) -> str:
    lower = filename.lower()
    if lower.endswith(".pdf"):
        return "application/pdf"
    elif lower.endswith(".png"):
        return "image/png"
    elif lower.endswith((".jpg", ".jpeg")):
        return "image/jpeg"
    return "application/octet-stream"


def validate_upload(filename: str, content: bytes) -> str | None:
    if len(content) > MAX_SIZE:
        return f"File exceeds 15 MB limit ({len(content) / 1024 / 1024:.1f} MB)"
    mime = guess_mime(filename)
    if mime not in ALLOWED_MIMES:
        return "Unsupported file type. Accepted: PDF, PNG, JPG"
    pages = get_page_count(content, mime)
    if pages > MAX_PAGES:
        return f"Document exceeds {MAX_PAGES}-page limit ({pages} pages)"
    return None


def get_page_count(content: bytes, mime: str) -> int:
    if mime == "application/pdf":
        try:
            pdf = pdfium.PdfDocument(content)
            return len(pdf)
        except Exception:
            return 1
    return 1


def render_previews(content: bytes, mime: str, doc_id: int) -> list[str]:
    preview_dir = PREVIEWS_DIR / str(doc_id)
    preview_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    if mime == "application/pdf":
        pdf = pdfium.PdfDocument(content)
        for i in range(len(pdf)):
            page = pdf[i]
            bitmap = page.render(scale=2)
            pil_image = bitmap.to_pil()
            page_path = str(preview_dir / f"page_{i}.png")
            pil_image.save(page_path, "PNG")
            paths.append(page_path)
    else:
        img = Image.open(__import__("io").BytesIO(content))
        page_path = str(preview_dir / "page_0.png")
        img.save(page_path, "PNG")
        paths.append(page_path)
    return paths


def save_document(filename: str, content: bytes) -> int:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    PREVIEWS_DIR.mkdir(parents=True, exist_ok=True)

    mime = guess_mime(filename)
    pages = get_page_count(content, mime)
    ext = ALLOWED_MIMES[mime]
    stored_name = f"{uuid.uuid4().hex}{ext}"
    dest = DOCS_DIR / stored_name
    dest.write_bytes(content)

    session = get_session()
    try:
        doc = Document(
            filename=filename,
            path=str(dest),
            mime=mime,
            pages=pages,
            status="processing",
        )
        session.add(doc)
        session.flush()

        render_previews(content, mime, doc.id)

        session.commit()
        return doc.id
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
