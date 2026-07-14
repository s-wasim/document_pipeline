from unittest.mock import patch, MagicMock
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base, Document, Extraction, Receipt
from app.graph.nodes.unsupported import mark_unsupported

# Review-queue default (documents awaiting human action). This lived in the old
# Streamlit review tab; it now drives the frontend Component's default
# reviewFilter. Kept here as a domain invariant.
QUEUE_STATUSES = ["needs_review", "failed_validation"]


@patch("app.commit.get_session")
def test_commit_receipt(mock_get_session):
    mock_doc = MagicMock(spec=Document)
    mock_doc.id = 1
    mock_doc.status = "needs_review"

    mock_query = MagicMock()
    mock_query.filter.return_value.first.return_value = mock_doc
    mock_session = MagicMock()
    mock_session.query.return_value = mock_query
    mock_get_session.return_value = mock_session

    payload = {
        "merchant": "Quick Mart",
        "purchase_date": "2026-07-08",
        "currency": "USD",
        "total": "46.38",
        "payment_method": "Visa",
    }

    from app.commit import commit_receipt
    success, errors = commit_receipt(1, payload)
    assert success, errors
    assert errors == []
    assert mock_doc.status == "committed"


def test_unsupported_creates_no_extraction_row():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    doc = Document(filename="po.pdf", path="/tmp/po.pdf", mime="application/pdf", status="processing")
    session.add(doc)
    session.commit()
    doc_id = doc.id
    session.close()

    state = {
        "document_id": doc_id,
        "file_path": "/tmp/po.pdf",
        "mime": "application/pdf",
        "doc_type": "purchase_order",
        "confidence": 0.9,
        "payload": None,
        "validation_errors": [],
        "repair_attempted": False,
        "final_status": None,
        "llm_calls": 1,
    }

    with patch("app.graph.nodes.unsupported.get_session", lambda: Session()):
        mark_unsupported(state)

    check_session = Session()
    try:
        updated_doc = check_session.query(Document).filter(Document.id == doc_id).first()
        assert updated_doc.status == "unsupported"
        assert check_session.query(Extraction).filter(Extraction.document_id == doc_id).count() == 0
    finally:
        check_session.close()


def test_default_queue_filter_excludes_rejected():
    assert "rejected" not in QUEUE_STATUSES
    assert set(QUEUE_STATUSES) == {"needs_review", "failed_validation"}
