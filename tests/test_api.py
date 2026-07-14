from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.db as db
from app.db import Base, Document, Extraction, Invoice, InvoiceItem, Receipt
from app.api.health import router as health_router
from app.api.documents import router as documents_router
from app.api.records import router as records_router
from app.api.actions import router as actions_router


@pytest.fixture(scope="function")
def client():
    # StaticPool + a single shared connection so the in-memory DB is visible
    # from the TestClient worker thread (endpoints run off the main thread).
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    db.engine = engine
    db.SessionLocal = sessionmaker(bind=engine)

    session = db.get_session()
    try:
        # 1) Invoice awaiting review, with an extraction payload.
        d1 = Document(filename="northwind.pdf", path="/tmp/n.pdf", mime="application/pdf",
                      pages=2, doc_type="invoice", status="needs_review", llm_calls=2)
        session.add(d1)
        session.flush()
        session.add(Extraction(
            document_id=d1.id,
            payload={
                "vendor": "Northwind Supply Co.", "invoice_no": "INV-10432",
                "invoice_date": "2026-06-18", "due_date": "2026-07-18", "currency": "USD",
                "items": [{"description": "Widget A", "qty": "10", "unit_price": "12.50", "line_total": "125.00"}],
                "subtotal": "125.00", "tax": "10.00", "total": "135.00",
            },
            validation_errors=[], repair_attempted=False,
        ))

        # 2) Already-committed invoice (Database tab).
        d2 = Document(filename="acme.pdf", path="/tmp/a.pdf", mime="application/pdf",
                      pages=1, doc_type="invoice", status="committed", llm_calls=2)
        session.add(d2)
        session.flush()
        inv = Invoice(document_id=d2.id, vendor="Acme Fixtures Inc.", invoice_no="INV-9001",
                      currency="USD", subtotal=Decimal("90.00"), tax=Decimal("7.20"), total=Decimal("97.20"))
        session.add(inv)
        session.flush()
        session.add(InvoiceItem(invoice_id=inv.id, description="Steel Brackets",
                                qty=Decimal("20"), unit_price=Decimal("4.50"), line_total=Decimal("90.00")))

        # 3) Committed receipt.
        d3 = Document(filename="cafe.jpg", path="/tmp/c.jpg", mime="image/jpeg",
                      pages=1, doc_type="receipt", status="committed", llm_calls=2)
        session.add(d3)
        session.flush()
        session.add(Receipt(document_id=d3.id, merchant="Corner Cafe", currency="USD",
                            total=Decimal("11.00"), payment_method="VISA ****4242"))

        session.commit()
        ids = {"invoice_doc": d1.id, "committed_doc": d2.id}
    finally:
        session.close()

    api = FastAPI()
    api.include_router(health_router)
    api.include_router(documents_router)
    api.include_router(records_router)
    api.include_router(actions_router)

    tc = TestClient(api)
    tc.seed_ids = ids
    yield tc

    db.engine = None
    db.SessionLocal = None


def test_health_ok(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"db_ok": True, "db_error": None}


def test_list_documents(client):
    rows = client.get("/api/documents").json()
    assert len(rows) == 3
    row = next(r for r in rows if r["status"] == "needs_review")
    assert row["doc_type"] == "invoice"
    assert set(["id", "filename", "doc_type", "pages", "llm_calls", "status", "note", "created_at"]) <= set(row)


def test_list_documents_status_filter(client):
    rows = client.get("/api/documents?status=committed").json()
    assert len(rows) == 2
    assert all(r["status"] == "committed" for r in rows)


def test_extraction_and_404(client):
    did = client.seed_ids["invoice_doc"]
    r = client.get(f"/api/documents/{did}/extraction")
    assert r.status_code == 200
    body = r.json()
    assert body["doc_type"] == "invoice"
    assert body["payload"]["vendor"] == "Northwind Supply Co."
    assert body["repair_attempted"] is False
    # committed doc has no extraction row
    assert client.get(f"/api/documents/{client.seed_ids['committed_doc']}/extraction").status_code == 404
    assert client.get("/api/documents/999999/extraction").status_code == 404


def test_invoices_records(client):
    rows = client.get("/api/invoices").json()
    assert len(rows) == 1
    inv = rows[0]
    assert inv["vendor"] == "Acme Fixtures Inc."
    assert inv["source_filename"] == "acme.pdf"
    # money and item numbers must be JSON numbers (template calls .toFixed on them)
    assert isinstance(inv["total"], (int, float))
    assert isinstance(inv["items"][0]["unit_price"], (int, float))


def test_receipts_records(client):
    rows = client.get("/api/receipts").json()
    assert len(rows) == 1
    assert rows[0]["merchant"] == "Corner Cafe"
    assert rows[0]["source_filename"] == "cafe.jpg"
    assert isinstance(rows[0]["total"], (int, float))


def test_upload_rejects_bad_type(client):
    r = client.post("/api/documents", files={"file": ("note.txt", b"hello", "text/plain")})
    assert r.status_code == 400
    assert "Unsupported file type" in r.json()["error"]


def test_sample_unknown_404(client):
    assert client.post("/api/documents/sample/does_not_exist").status_code == 404


def test_preview_missing_page_404(client, monkeypatch, tmp_path):
    # Point PREVIEWS_DIR at an empty temp dir so the check is deterministic and
    # isolated from any real previews left on disk under data/previews/.
    import app.api.documents as docs_mod
    monkeypatch.setattr(docs_mod, "PREVIEWS_DIR", tmp_path)
    did = client.seed_ids["invoice_doc"]
    body = client.get(f"/api/documents/{did}/preview").json()
    assert body == {"pageCount": 0, "pages": []}
    assert client.get(f"/api/documents/{did}/preview/0").status_code == 404


def test_commit_invoice_success(client):
    did = client.seed_ids["invoice_doc"]
    payload = {
        "vendor": "Northwind Supply Co.", "invoice_no": "INV-10432",
        "invoice_date": "2026-06-18", "due_date": "2026-07-18", "currency": "USD",
        "items": [{"description": "Widget A", "qty": "10", "unit_price": "12.50", "line_total": "125.00"}],
        "subtotal": "125.00", "tax": "10.00", "total": "135.00",
    }
    r = client.post(f"/api/documents/{did}/commit", json={"doc_type": "invoice", "payload": payload})
    assert r.status_code == 200
    assert r.json() == {"success": True, "errors": []}
    # document flips to committed and shows up in the invoices list
    doc = next(d for d in client.get("/api/documents").json() if d["id"] == did)
    assert doc["status"] == "committed"
    assert any(i["invoice_no"] == "INV-10432" for i in client.get("/api/invoices").json())


def test_commit_invoice_validation_errors(client):
    did = client.seed_ids["invoice_doc"]
    bad = {
        "vendor": "X", "invoice_no": "Y", "currency": "USD",
        "items": [{"description": "A", "qty": "1", "unit_price": "10.00", "line_total": "10.00"}],
        "subtotal": "10.00", "tax": "0.00", "total": "999.00",  # total mismatch
    }
    r = client.post(f"/api/documents/{did}/commit", json={"doc_type": "invoice", "payload": bad})
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is False
    assert any("Total mismatch" in e for e in body["errors"])


def test_reject(client):
    did = client.seed_ids["invoice_doc"]
    r = client.post(f"/api/documents/{did}/reject", json={"note": "blurry scan"})
    assert r.json() == {"success": True}
    doc = next(d for d in client.get("/api/documents").json() if d["id"] == did)
    assert doc["status"] == "rejected"
    assert doc["note"] == "blurry scan"


def test_process_stream_frames(client, monkeypatch):
    """The SSE endpoint relays stream_pipeline node events then a final frame."""

    def fake_stream(document_id):
        yield {"final": False, "event": {"load_doc": {"doc_type": None, "llm_calls": 0, "validation_errors": 0, "repair_attempted": False}}}
        yield {"final": False, "event": {"classify": {"doc_type": "invoice", "llm_calls": 1, "validation_errors": 0, "repair_attempted": False}}}
        yield {"final": True, "success": True, "document_id": document_id,
               "final_status": "needs_review", "llm_calls": 2, "validation_errors": []}

    monkeypatch.setattr("app.api.documents.stream_pipeline", fake_stream)

    did = client.seed_ids["invoice_doc"]
    with client.stream("POST", f"/api/documents/{did}/process") as resp:
        assert resp.status_code == 200
        body = "".join(resp.iter_text())

    assert "event: node" in body
    assert '"node": "classify"' in body
    assert "event: final" in body
    assert '"final_status": "needs_review"' in body


def test_process_stream_error_frame(client, monkeypatch):
    def fake_stream(document_id):
        yield {"final": True, "success": False, "document_id": document_id, "error": "boom"}

    monkeypatch.setattr("app.api.documents.stream_pipeline", fake_stream)
    did = client.seed_ids["invoice_doc"]
    with client.stream("POST", f"/api/documents/{did}/process") as resp:
        body = "".join(resp.iter_text())
    assert "event: error" in body
    assert "boom" in body
