from decimal import Decimal
from datetime import date

import pytest
from pydantic import ValidationError

from app.schemas.invoice import InvoicePayload, InvoiceItemPayload
from app.schemas.receipt import ReceiptPayload
from app.schemas.common import parse_money, parse_date


def test_parse_money_from_string():
    assert parse_money("1234.50") == Decimal("1234.50")


def test_parse_money_with_commas():
    assert parse_money("1,234.50") == Decimal("1234.50")


def test_parse_money_with_symbol():
    assert parse_money("$99.99") == Decimal("99.99")


def test_parse_money_with_currency():
    assert parse_money("USD 50.00") == Decimal("50.00")


def test_parse_date_iso():
    assert parse_date("2026-07-01") == date(2026, 7, 1)


def test_parse_date_us_format():
    assert parse_date("01/07/2026") == date(2026, 1, 7)


def test_parse_date_none():
    assert parse_date(None) is None


def test_invoice_payload_valid():
    data = {
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
    payload = InvoicePayload.from_dict(data)
    assert payload.vendor == "Test Corp"
    assert payload.subtotal == Decimal("200.00")
    assert payload.tax == Decimal("16.00")
    assert payload.total == Decimal("216.00")
    assert len(payload.items) == 1
    assert isinstance(payload.items[0].qty, Decimal)


def test_invoice_empty_vendor_creates():
    payload = InvoicePayload.from_dict({"vendor": "", "invoice_no": "", "subtotal": "0", "tax": "0", "total": "0"})
    assert payload.vendor == ""


def test_invoice_missing_vendor_raises_field_named_error():
    with pytest.raises(ValidationError) as exc_info:
        InvoicePayload.from_dict({"invoice_no": "INV-001", "subtotal": "0", "tax": "0", "total": "0"})
    assert "vendor" in str(exc_info.value)


def test_invoice_missing_invoice_no_raises_field_named_error():
    with pytest.raises(ValidationError) as exc_info:
        InvoicePayload.from_dict({"vendor": "Test Corp", "subtotal": "0", "tax": "0", "total": "0"})
    assert "invoice_no" in str(exc_info.value)


def test_receipt_missing_merchant_raises_field_named_error():
    with pytest.raises(ValidationError) as exc_info:
        ReceiptPayload.from_dict({"total": "10.00"})
    assert "merchant" in str(exc_info.value)


def test_receipt_payload():
    data = {
        "merchant": "Quick Mart",
        "purchase_date": "2026-07-08",
        "currency": "USD",
        "total": "46.38",
        "payment_method": "Visa",
    }
    payload = ReceiptPayload.from_dict(data)
    assert payload.merchant == "Quick Mart"
    assert payload.total == Decimal("46.38")
    assert payload.payment_method == "Visa"
