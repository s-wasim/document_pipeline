"""Documents router: upload, sample-load, list, extraction, preview, and the
SSE pipeline-processing stream. Every handler delegates to the existing,
unchanged backend functions in app.upload / app.graph.runner / app.db.
"""

import json
import os
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse

from app.db import get_session, Document, Extraction
from app.upload import validate_upload, save_document
from app.graph.runner import stream_pipeline
from app.api.serializers import document_to_dict, extraction_to_dict

router = APIRouter()

SAMPLES_DIR = Path(__file__).resolve().parent.parent.parent / "samples"
PREVIEWS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "previews"

# Frontend sample chip id -> real file shipped in samples/.
SAMPLE_FILES = {
    "invoice_clean": "invoice_clean.pdf",
    "receipt": "receipt.jpg",
    "invoice_broken": "invoice_broken_totals.pdf",
    "purchase_order": "purchase_order.pdf",
}


def _saved_response(filename: str, content: bytes):
    err = validate_upload(filename, content)
    if err:
        return JSONResponse(status_code=400, content={"error": err})
    doc_id = save_document(filename, content)
    session = get_session()
    try:
        doc = session.query(Document).filter(Document.id == doc_id).first()
        return {
            "document_id": doc.id,
            "filename": doc.filename,
            "pages": doc.pages,
            "mime": doc.mime,
        }
    finally:
        session.close()


@router.post("/api/documents")
async def upload_document(file: UploadFile = File(...)):
    content = await file.read()
    return _saved_response(file.filename, content)


@router.post("/api/documents/sample/{sample_id}")
def load_sample(sample_id: str):
    name = SAMPLE_FILES.get(sample_id)
    if not name:
        raise HTTPException(status_code=404, detail="Unknown sample")
    path = SAMPLES_DIR / name
    if not path.exists():
        raise HTTPException(status_code=404, detail="Sample file missing")
    return _saved_response(name, path.read_bytes())


@router.get("/api/documents")
def list_documents(status: str | None = None):
    session = get_session()
    try:
        q = session.query(Document)
        if status:
            wanted = [s for s in status.split(",") if s]
            q = q.filter(Document.status.in_(wanted))
        docs = q.order_by(Document.created_at.desc(), Document.id.desc()).all()
        return [document_to_dict(d) for d in docs]
    finally:
        session.close()


@router.get("/api/documents/{document_id}/extraction")
def get_extraction(document_id: int):
    session = get_session()
    try:
        doc = session.query(Document).filter(Document.id == document_id).first()
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        ext = (
            session.query(Extraction)
            .filter(Extraction.document_id == document_id)
            .order_by(Extraction.created_at.desc(), Extraction.id.desc())
            .first()
        )
        if not ext:
            raise HTTPException(status_code=404, detail="No extraction for document")
        return extraction_to_dict(ext, doc.doc_type)
    finally:
        session.close()


@router.get("/api/documents/{document_id}/preview")
def list_preview_pages(document_id: int):
    preview_dir = PREVIEWS_DIR / str(document_id)
    pages = []
    if preview_dir.exists():
        images = sorted(preview_dir.glob("page_*.png"))
        for i, _ in enumerate(images):
            pages.append({"num": i + 1, "src": f"/api/documents/{document_id}/preview/{i}"})
    return {"pageCount": len(pages), "pages": pages}


@router.get("/api/documents/{document_id}/preview/{page}")
def get_preview_page(document_id: int, page: int):
    # page is an int path param, so traversal is impossible; still constrain to
    # the document's own preview directory.
    img = PREVIEWS_DIR / str(document_id) / f"page_{page}.png"
    if not img.exists():
        raise HTTPException(status_code=404, detail="Preview page not found")
    return FileResponse(str(img), media_type="image/png")


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.post("/api/documents/{document_id}/process")
def process_document(document_id: int):
    """Stream real node-completion events from stream_pipeline as SSE frames.

    Starlette iterates this sync generator in its threadpool, so the blocking
    LLM calls inside the graph do not block the event loop.
    """

    def gen():
        try:
            for update in stream_pipeline(document_id):
                if update.get("final"):
                    if update.get("success"):
                        yield _sse("final", {
                            "document_id": update.get("document_id"),
                            "final_status": update.get("final_status"),
                            "llm_calls": update.get("llm_calls") or 0,
                            "validation_errors": update.get("validation_errors") or [],
                        })
                    else:
                        yield _sse("error", {"message": update.get("error", "Pipeline failed")})
                else:
                    for node, summary in update.get("event", {}).items():
                        yield _sse("node", {"node": node, "summary": summary})
        except Exception as e:  # pragma: no cover - defensive
            yield _sse("error", {"message": str(e)})

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
