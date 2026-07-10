from decimal import Decimal

from app.db import get_session, Document, Extraction, Invoice, InvoiceItem, Receipt
from app.schemas.invoice import InvoicePayload
from app.schemas.receipt import ReceiptPayload
from app.validation import validate_payload


def commit_invoice(document_id: int, edited_payload: dict) -> tuple[bool, list[str]]:
    session = get_session()
    try:
        doc = session.query(Document).filter(Document.id == document_id).first()
        if not doc:
            return False, ["Document not found"]
        if doc.status == "committed":
            return False, ["Document already committed"]

        payload = InvoicePayload.from_dict(edited_payload)
        errors = validate_payload("invoice", payload)
        if errors:
            return False, errors

        inv = Invoice(
            document_id=document_id,
            vendor=payload.vendor,
            invoice_no=payload.invoice_no,
            invoice_date=payload.invoice_date,
            due_date=payload.due_date,
            currency=payload.currency,
            subtotal=payload.subtotal,
            tax=payload.tax,
            total=payload.total,
        )
        session.add(inv)
        session.flush()

        for item in payload.items:
            inv_item = InvoiceItem(
                invoice_id=inv.id,
                description=item.description,
                qty=item.qty,
                unit_price=item.unit_price,
                line_total=item.line_total,
            )
            session.add(inv_item)

        doc.status = "committed"
        session.commit()
        return True, []
    except Exception as e:
        session.rollback()
        return False, [str(e)]
    finally:
        session.close()


def commit_receipt(document_id: int, edited_payload: dict) -> tuple[bool, list[str]]:
    session = get_session()
    try:
        doc = session.query(Document).filter(Document.id == document_id).first()
        if not doc:
            return False, ["Document not found"]
        if doc.status == "committed":
            return False, ["Document already committed"]

        payload = ReceiptPayload.from_dict(edited_payload)
        errors = validate_payload("receipt", payload)
        if errors:
            return False, errors

        rcpt = Receipt(
            document_id=document_id,
            merchant=payload.merchant,
            purchase_date=payload.purchase_date,
            currency=payload.currency,
            total=payload.total,
            payment_method=payload.payment_method,
        )
        session.add(rcpt)

        doc.status = "committed"
        session.commit()
        return True, []
    except Exception as e:
        session.rollback()
        return False, [str(e)]
    finally:
        session.close()


def reject_document(document_id: int, note: str = "Rejected by user") -> bool:
    session = get_session()
    try:
        doc = session.query(Document).filter(Document.id == document_id).first()
        if not doc:
            return False
        doc.status = "rejected"
        doc.note = note
        session.commit()
        return True
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
