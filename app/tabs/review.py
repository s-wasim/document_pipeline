from decimal import Decimal
from pathlib import Path

import streamlit as st
import pandas as pd

from app.db import get_session, Document, Extraction
from app.schemas.invoice import InvoicePayload, InvoiceItemPayload
from app.schemas.receipt import ReceiptPayload
from app.validation import validate_payload
from app.commit import commit_invoice, commit_receipt, reject_document

PREVIEWS_DIR = Path(__file__).parent.parent.parent / "data" / "previews"

QUEUE_STATUSES = ["needs_review", "failed_validation"]


def render():
    st.header("Review Queue")

    status_filter = st.multiselect(
        "Status filter",
        ["needs_review", "failed_validation", "unsupported", "committed", "rejected"],
        default=QUEUE_STATUSES,
    )

    session = get_session()
    try:
        docs = (
            session.query(Document)
            .filter(Document.status.in_(status_filter))
            .order_by(Document.created_at.desc())
            .all()
        )
    finally:
        session.close()

    if not docs:
        st.info("No documents match the current filter.")
        return

    for doc in docs:
        _render_doc_card(doc)


def _render_doc_card(doc: Document):
    with st.container(border=True):
        cols = st.columns([3, 1, 1, 1, 1])
        cols[0].write(f"**{doc.filename}**")
        cols[1].write(f"Type: {doc.doc_type or '—'}")
        cols[2].write(f"Pages: {doc.pages}")
        cols[3].write(f"LLM: {doc.llm_calls}")
        cols[4].caption(doc.status.replace("_", " ").title())

        if doc.status in ("needs_review", "failed_validation"):
            if st.button("Review", key=f"review_{doc.id}"):
                st.session_state.review_doc_id = doc.id
                st.rerun()

        if doc.note:
            st.caption(f"Note: {doc.note}")

    if st.session_state.get("review_doc_id") == doc.id:
        _render_review_detail(doc)


def _get_validation_badge(is_valid: bool):
    if is_valid:
        return "🟢"
    return "🔴"


def _revalidate(payload_dict: dict, doc_type: str) -> dict[str, list[str]]:
    field_errors: dict[str, list[str]] = {}
    if doc_type == "invoice":
        try:
            payload = InvoicePayload.from_dict(payload_dict)
        except Exception as e:
            return {"_all": [str(e)]}
        errors = validate_payload("invoice", payload)

        field_errors["vendor"] = [e for e in errors if "vendor" in e.lower() or "Vendor" in e]
        field_errors["invoice_no"] = [e for e in errors if "invoice" in e.lower() and "number" in e.lower()]
        field_errors["items"] = [e for e in errors if "Item" in e]
        field_errors["subtotal"] = [e for e in errors if "Subtotal" in e]
        field_errors["total"] = [e for e in errors if "Total" in e]
        field_errors["tax"] = [e for e in errors if "tax" in e.lower()]
    elif doc_type == "receipt":
        try:
            payload = ReceiptPayload.from_dict(payload_dict)
        except Exception as e:
            return {"_all": [str(e)]}
        errors = validate_payload("receipt", payload)
        field_errors["merchant"] = [e for e in errors if "merchant" in e.lower()]
        field_errors["total"] = [e for e in errors if "Total" in e]

    return field_errors


def _render_review_detail(doc: Document):
    st.divider()
    st.subheader(f"Review: {doc.filename}")

    session = get_session()
    try:
        extraction = (
            session.query(Extraction)
            .filter(Extraction.document_id == doc.id)
            .order_by(Extraction.created_at.desc())
            .first()
        )
    finally:
        session.close()

    if not extraction or not extraction.payload:
        st.warning("No extraction data available for this document.")
        return

    payload = extraction.payload
    doc_type = doc.doc_type or "invoice"

    left_col, right_col = st.columns([1, 1])

    with left_col:
        _render_preview(doc.id)

    with right_col:
        with st.container(border=True):
            if doc_type == "invoice":
                edited = _render_invoice_editor(payload, doc.id)
            else:
                edited = _render_receipt_editor(payload, doc.id)

        if edited:
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Approve & Commit", type="primary", use_container_width=True, key=f"approve_{doc.id}"):
                    _handle_approve(doc.id, edited, doc_type)
            with col2:
                reject_note = st.text_input("Rejection note", key=f"reject_note_{doc.id}")
                if st.button("Reject", use_container_width=True, key=f"reject_{doc.id}"):
                    reject_document(doc.id, note=reject_note or "Rejected by user")
                    st.success("Document rejected.")
                    st.session_state.review_doc_id = None
                    st.rerun()


def _render_preview(doc_id: int):
    preview_dir = PREVIEWS_DIR / str(doc_id)
    if preview_dir.exists():
        images = sorted(preview_dir.glob("*.png"))
        if images:
            for img_path in images:
                st.image(str(img_path), use_container_width=True)
        else:
            st.info("No preview images available.")
    else:
        st.info("Preview not available.")


def _render_invoice_editor(payload: dict, doc_id: int) -> dict | None:
    edited = {}
    badge_slots = {}

    edited["vendor"], badge_slots["vendor"] = _editable_field("vendor", "Vendor", payload.get("vendor", ""), doc_id)
    edited["invoice_no"], badge_slots["invoice_no"] = _editable_field("invoice_no", "Invoice No", payload.get("invoice_no", ""), doc_id)
    edited["invoice_date"], badge_slots["invoice_date"] = _editable_field("invoice_date", "Invoice Date", payload.get("invoice_date", ""), doc_id)
    edited["due_date"], badge_slots["due_date"] = _editable_field("due_date", "Due Date", payload.get("due_date", ""), doc_id)
    edited["currency"], badge_slots["currency"] = _editable_field("currency", "Currency", payload.get("currency", "USD"), doc_id)
    edited["subtotal"], badge_slots["subtotal"] = _editable_field("subtotal", "Subtotal", payload.get("subtotal", "0.00"), doc_id)
    edited["tax"], badge_slots["tax"] = _editable_field("tax", "Tax", payload.get("tax", "0.00"), doc_id)
    edited["total"], badge_slots["total"] = _editable_field("total", "Total", payload.get("total", "0.00"), doc_id)

    st.subheader("Line Items")
    items = payload.get("items", [])
    items_status_slot = st.empty()
    if items:
        df = pd.DataFrame(items)
        edited_df = st.data_editor(
            df,
            num_rows="dynamic",
            key=f"items_editor_{doc_id}",
            use_container_width=True,
            column_config={
                "description": st.column_config.TextColumn("Description", width="large"),
                "qty": st.column_config.NumberColumn("Qty", format="%.2f"),
                "unit_price": st.column_config.NumberColumn("Unit Price", format="%.2f"),
                "line_total": st.column_config.NumberColumn("Line Total", format="%.2f"),
            },
        )

        edited["items"] = edited_df.to_dict("records")

        for item in edited["items"]:
            for key in ("qty", "unit_price", "line_total"):
                if key in item and item[key] is not None:
                    item[key] = str(item[key])
    else:
        edited["items"] = []

    # Re-validate against the values the user just edited (not the stale
    # extraction payload), so badges reflect live edits on every rerun.
    field_errors = _revalidate(edited, "invoice")

    for key, slot in badge_slots.items():
        _render_badge(slot, field_errors.get(key, []))

    items_errors = field_errors.get("items", [])
    if items:
        if items_errors:
            for err in items_errors:
                items_status_slot.error(err)
        elif not field_errors.get("_all"):
            items_status_slot.success("Line items valid")

    return edited


def _render_receipt_editor(payload: dict, doc_id: int) -> dict | None:
    edited = {}
    badge_slots = {}

    edited["merchant"], badge_slots["merchant"] = _editable_field("merchant", "Merchant", payload.get("merchant", ""), doc_id)
    edited["purchase_date"], badge_slots["purchase_date"] = _editable_field("purchase_date", "Purchase Date", payload.get("purchase_date", ""), doc_id)
    edited["currency"], badge_slots["currency"] = _editable_field("currency", "Currency", payload.get("currency", "USD"), doc_id)
    edited["total"], badge_slots["total"] = _editable_field("total", "Total", payload.get("total", "0.00"), doc_id)
    edited["payment_method"], badge_slots["payment_method"] = _editable_field("payment_method", "Payment Method", payload.get("payment_method", ""), doc_id)

    field_errors = _revalidate(edited, "receipt")
    for key, slot in badge_slots.items():
        _render_badge(slot, field_errors.get(key, []))

    return edited


def _editable_field(key: str, label: str, value: str, doc_id: int):
    col1, col2 = st.columns([0.85, 0.15])
    with col1:
        edited = st.text_input(label, value=value or "", key=f"field_{key}_{doc_id}")
    with col2:
        slot = st.empty()
    return edited, slot


def _render_badge(slot, errors: list[str]):
    is_valid = len(errors) == 0
    with slot:
        st.markdown(f"<div style='padding-top:28px;text-align:center;font-size:20px;'>{_get_validation_badge(is_valid)}</div>", unsafe_allow_html=True)
        if not is_valid:
            st.caption(" ".join(errors))


def _handle_approve(doc_id: int, edited: dict, doc_type: str):
    if doc_type == "invoice":
        success, errors = commit_invoice(doc_id, edited)
    else:
        success, errors = commit_receipt(doc_id, edited)

    if success:
        st.success("Document committed successfully!")
        st.session_state.review_doc_id = None
        st.rerun()
    else:
        st.error("Commit failed:")
        for err in errors:
            st.error(err)
