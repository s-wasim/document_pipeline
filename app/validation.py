from decimal import Decimal
from typing import Any

from app.schemas.invoice import InvoicePayload
from app.schemas.receipt import ReceiptPayload

TOLERANCE = Decimal("0.02")


def validate_payload(doc_type: str, payload: Any) -> list[str]:
    errors: list[str] = []
    if doc_type == "invoice":
        errors = _validate_invoice(payload)
    elif doc_type == "receipt":
        errors = _validate_receipt(payload)
    else:
        errors.append(f"Unknown document type: {doc_type}")
    return errors


def _validate_invoice(inv: InvoicePayload) -> list[str]:
    errors: list[str] = []

    if not inv.vendor:
        errors.append("Vendor is required")
    if not inv.invoice_no:
        errors.append("Invoice number is required")

    if inv.items:
        for i, item in enumerate(inv.items):
            if not item.description:
                errors.append(f"Item {i + 1}: description is required")
            expected_line = (item.qty * item.unit_price).quantize(Decimal("0.01"))
            if abs(expected_line - item.line_total) > TOLERANCE:
                errors.append(
                    f"Item {i + 1} ('{item.description}'): "
                    f"qty {item.qty} × unit_price {item.unit_price} = {expected_line}, "
                    f"but line_total is {item.line_total} (diff {expected_line - item.line_total})"
                )

        items_sum = sum((it.line_total for it in inv.items), Decimal("0.00"))
        if abs(items_sum - inv.subtotal) > TOLERANCE:
            errors.append(
                f"Subtotal mismatch: sum of line items = {items_sum}, "
                f"declared subtotal = {inv.subtotal} (diff {items_sum - inv.subtotal})"
            )

    calc_total = (inv.subtotal + inv.tax).quantize(Decimal("0.01"))
    if abs(calc_total - inv.total) > TOLERANCE:
        errors.append(
            f"Total mismatch: subtotal {inv.subtotal} + tax {inv.tax} = {calc_total}, "
            f"but declared total is {inv.total} (diff {calc_total - inv.total})"
        )

    if inv.subtotal < 0:
        errors.append(f"Subtotal cannot be negative: {inv.subtotal}")
    if inv.tax < 0:
        errors.append(f"Tax cannot be negative: {inv.tax}")
    if inv.total < 0:
        errors.append(f"Total cannot be negative: {inv.total}")

    return errors


def _validate_receipt(rcpt: ReceiptPayload) -> list[str]:
    errors: list[str] = []
    if not rcpt.merchant:
        errors.append("Merchant is required")
    if rcpt.total < 0:
        errors.append(f"Total cannot be negative: {rcpt.total}")
    return errors
