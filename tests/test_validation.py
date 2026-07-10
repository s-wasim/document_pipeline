from decimal import Decimal

import pytest
from app.validation import validate_payload
from app.schemas.invoice import InvoicePayload, InvoiceItemPayload


def _make_invoice(items=None, subtotal="100.00", tax="8.00", total="108.00"):
    items = items or [
        {"description": "Item A", "qty": "2", "unit_price": "50.00", "line_total": "100.00"},
    ]
    data = {
        "vendor": "Test Corp",
        "invoice_no": "INV-001",
        "currency": "USD",
        "items": items,
        "subtotal": subtotal,
        "tax": tax,
        "total": total,
    }
    return InvoicePayload.from_dict(data)


def test_clean_invoice_passes():
    inv = _make_invoice()
    errors = validate_payload("invoice", inv)
    assert errors == []


def test_broken_totals():
    items = [
        {"description": "Item A", "qty": "2", "unit_price": "50.00", "line_total": "100.00"},
        {"description": "Item B", "qty": "1", "unit_price": "200.00", "line_total": "200.00"},
    ]
    inv = _make_invoice(items=items, subtotal="295.00", tax="23.60", total="318.60")
    errors = validate_payload("invoice", inv)
    assert any("Subtotal mismatch" in e for e in errors)


def test_tolerance_boundary():
    """Exactly 0.02 off should pass (tolerance)."""
    inv = _make_invoice(items=[
        {"description": "Item A", "qty": "1", "unit_price": "100.00", "line_total": "99.98"},
    ], subtotal="99.98", tax="8.00", total="107.98")
    errors = validate_payload("invoice", inv)
    assert errors == []


def test_tolerance_exceeded():
    """0.03 off should fail."""
    inv = _make_invoice(items=[
        {"description": "Item A", "qty": "1", "unit_price": "100.00", "line_total": "99.97"},
    ], subtotal="99.97", tax="8.00", total="107.97")
    errors = validate_payload("invoice", inv)
    assert any("line_total" in e for e in errors)


def test_errors_are_readable():
    inv = _make_invoice(items=[
        {"description": "Item A", "qty": "1", "unit_price": "50.00", "line_total": "100.00"},
    ], subtotal="999.00", tax="10.00", total="1009.00")
    errors = validate_payload("invoice", inv)
    assert all(isinstance(e, str) for e in errors)
    assert all(len(e) > 10 for e in errors)
