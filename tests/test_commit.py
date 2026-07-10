from unittest.mock import patch, MagicMock
from decimal import Decimal

from app.db import Document, Invoice, InvoiceItem


@patch("app.commit.get_session")
def test_commit_valid_invoice(mock_get_session):
    mock_session = MagicMock()

    mock_doc = MagicMock(spec=Document)
    mock_doc.id = 1
    mock_doc.status = "needs_review"

    mock_query = MagicMock()
    mock_query.filter.return_value.first.return_value = mock_doc
    mock_session.query.return_value = mock_query
    mock_get_session.return_value = mock_session

    payload = {
        "vendor": "Test Corp",
        "invoice_no": "INV-001",
        "invoice_date": "2026-07-01",
        "due_date": "2026-07-31",
        "currency": "USD",
        "items": [
            {"description": "Item A", "qty": "2", "unit_price": "100.00", "line_total": "200.00"},
        ],
        "subtotal": "200.00",
        "tax": "16.00",
        "total": "216.00",
    }

    from app.commit import commit_invoice
    success, errors = commit_invoice(1, payload)
    assert success, errors
    assert errors == []
    assert mock_doc.status == "committed"


@patch("app.commit.get_session")
def test_commit_invalid_payload_blocked(mock_get_session):
    mock_doc = MagicMock(spec=Document)
    mock_doc.id = 1
    mock_doc.status = "needs_review"

    mock_query = MagicMock()
    mock_query.filter.return_value.first.return_value = mock_doc
    mock_session = MagicMock()
    mock_session.query.return_value = mock_query
    mock_get_session.return_value = mock_session

    payload = {
        "vendor": "",
        "invoice_no": "",
        "items": [],
        "subtotal": "100",
        "tax": "10",
        "total": "200",
    }

    from app.commit import commit_invoice
    success, errors = commit_invoice(1, payload)
    assert not success
    assert len(errors) > 0


@patch("app.commit.get_session")
def test_commit_item_insert_failure_rolls_back_header(mock_get_session):
    """A forced failure while inserting invoice_items must roll back the
    whole transaction — no orphan invoice header left behind (FR-8)."""
    mock_doc = MagicMock(spec=Document)
    mock_doc.id = 1
    mock_doc.status = "needs_review"

    mock_query = MagicMock()
    mock_query.filter.return_value.first.return_value = mock_doc
    mock_session = MagicMock()
    mock_session.query.return_value = mock_query
    # First add() call (the invoice header) succeeds; second add() call
    # (the first invoice_item) raises, forcing a rollback.
    mock_session.add.side_effect = [None, Exception("forced item-insert failure")]
    mock_get_session.return_value = mock_session

    payload = {
        "vendor": "Test Corp",
        "invoice_no": "INV-001",
        "invoice_date": "2026-07-01",
        "due_date": "2026-07-31",
        "currency": "USD",
        "items": [
            {"description": "Item A", "qty": "2", "unit_price": "100.00", "line_total": "200.00"},
        ],
        "subtotal": "200.00",
        "tax": "16.00",
        "total": "216.00",
    }

    from app.commit import commit_invoice
    success, errors = commit_invoice(1, payload)

    assert not success
    assert "forced item-insert failure" in errors[0]
    mock_session.rollback.assert_called_once()
    mock_session.commit.assert_not_called()
    assert mock_doc.status == "needs_review"
