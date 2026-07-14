"""Committed-record reads for the Database tab: invoices and receipts."""

from fastapi import APIRouter

from app.db import get_session, Document, Invoice, Receipt
from app.api.serializers import invoice_to_dict, receipt_to_dict

router = APIRouter()


@router.get("/api/invoices")
def list_invoices():
    session = get_session()
    try:
        invoices = (
            session.query(Invoice)
            .join(Document)
            .order_by(Document.created_at.desc(), Invoice.id.desc())
            .all()
        )
        return [invoice_to_dict(inv) for inv in invoices]
    finally:
        session.close()


@router.get("/api/receipts")
def list_receipts():
    session = get_session()
    try:
        receipts = (
            session.query(Receipt)
            .join(Document)
            .order_by(Document.created_at.desc(), Receipt.id.desc())
            .all()
        )
        return [receipt_to_dict(rc) for rc in receipts]
    finally:
        session.close()
