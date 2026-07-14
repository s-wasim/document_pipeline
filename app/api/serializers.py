"""Row -> dict serializers.

Field names and value types are chosen to match exactly what the frontend
Component (VeloAdapter mock) originally produced, so `renderVals()` and the
template need no shape changes.

Note the deliberate money-type split:
- Committed Invoice/Receipt records feed template code that calls `.toFixed(2)`
  directly on item unit_price/line_total, so those must be JSON *numbers*.
- Extraction payloads feed the review editor, which reads values through
  `String(...)`/`Number(...)`; they are passed through as-is (money as strings,
  exactly as `InvoicePayload.to_dict()` produced them).
"""

from __future__ import annotations

from decimal import Decimal


def _num(value) -> float | None:
    if value is None:
        return None
    return float(Decimal(str(value)))


def _ymd(dt) -> str | None:
    return dt.strftime("%Y-%m-%d") if dt else None


def document_to_dict(doc) -> dict:
    return {
        "id": doc.id,
        "filename": doc.filename,
        "doc_type": doc.doc_type,
        "pages": doc.pages,
        "llm_calls": doc.llm_calls,
        "status": doc.status,
        "note": doc.note,
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
    }


def invoice_item_to_dict(item) -> dict:
    return {
        "description": item.description,
        "qty": _num(item.qty),
        "unit_price": _num(item.unit_price),
        "line_total": _num(item.line_total),
    }


def invoice_to_dict(inv) -> dict:
    return {
        "id": inv.id,
        "document_id": inv.document_id,
        "vendor": inv.vendor,
        "invoice_no": inv.invoice_no,
        "invoice_date": _ymd(inv.invoice_date),
        "due_date": _ymd(inv.due_date),
        "currency": inv.currency,
        "subtotal": _num(inv.subtotal),
        "tax": _num(inv.tax),
        "total": _num(inv.total),
        "items": [invoice_item_to_dict(it) for it in inv.items],
        "source_filename": inv.document.filename if inv.document else None,
    }


def receipt_to_dict(rc) -> dict:
    return {
        "id": rc.id,
        "document_id": rc.document_id,
        "merchant": rc.merchant,
        "purchase_date": _ymd(rc.purchase_date),
        "currency": rc.currency,
        "total": _num(rc.total),
        "payment_method": rc.payment_method,
        "source_filename": rc.document.filename if rc.document else None,
    }


def extraction_to_dict(ext, doc_type: str | None) -> dict:
    return {
        "payload": ext.payload,
        "validation_errors": ext.validation_errors or [],
        "repair_attempted": bool(ext.repair_attempted),
        "doc_type": doc_type,
    }
