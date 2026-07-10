from pathlib import Path

import streamlit as st
import pandas as pd

from app.db import get_session, Document, Invoice, InvoiceItem, Receipt

PREVIEWS_DIR = Path(__file__).parent.parent.parent / "data" / "previews"


def render():
    st.header("Database")

    invoices_tab, receipts_tab = st.tabs(["Invoices", "Receipts"])

    with invoices_tab:
        _render_invoices()

    with receipts_tab:
        _render_receipts()


def _render_invoices():
    session = get_session()
    try:
        invoices = (
            session.query(Invoice)
            .join(Document)
            .order_by(Document.created_at.desc())
            .all()
        )
    finally:
        session.close()

    if not invoices:
        st.info("No committed invoices yet.")
        return

    for inv in invoices:
        with st.container(border=True):
            st.write(f"**{inv.vendor}** — {inv.invoice_no}")
            cols = st.columns(5)
            cols[0].metric("Subtotal", f"{inv.currency} {inv.subtotal}")
            cols[1].metric("Tax", f"{inv.currency} {inv.tax}")
            cols[2].metric("Total", f"{inv.currency} {inv.total}")
            cols[3].write(f"Date: {inv.invoice_date.strftime('%Y-%m-%d') if inv.invoice_date else '—'}")
            cols[4].write(f"Due: {inv.due_date.strftime('%Y-%m-%d') if inv.due_date else '—'}")

            if inv.items:
                items_data = [
                    {
                        "Description": item.description,
                        "Qty": float(item.qty),
                        "Unit Price": float(item.unit_price),
                        "Line Total": float(item.line_total),
                    }
                    for item in inv.items
                ]
                st.dataframe(pd.DataFrame(items_data), use_container_width=True, hide_index=True)

            src = inv.document
            if src:
                st.caption(f"Source: {src.filename}")
                if st.button("View Document", key=f"view_doc_{inv.id}"):
                    st.session_state.view_doc_id = src.id
                    st.rerun()

            if st.session_state.get("view_doc_id") == src.id:
                _show_doc_preview(src.id)


def _render_receipts():
    session = get_session()
    try:
        receipts = (
            session.query(Receipt)
            .join(Document)
            .order_by(Document.created_at.desc())
            .all()
        )
    finally:
        session.close()

    if not receipts:
        st.info("No committed receipts yet.")
        return

    for rcpt in receipts:
        with st.container(border=True):
            st.write(f"**{rcpt.merchant}**")
            cols = st.columns(4)
            cols[0].metric("Total", f"{rcpt.currency} {rcpt.total}")
            cols[1].write(f"Date: {rcpt.purchase_date.strftime('%Y-%m-%d') if rcpt.purchase_date else '—'}")
            cols[2].write(f"Payment: {rcpt.payment_method or '—'}")
            cols[3].write(f"Currency: {rcpt.currency}")

            src = rcpt.document
            if src:
                st.caption(f"Source: {src.filename}")
                if st.button("View Document", key=f"view_rcpt_{rcpt.id}"):
                    st.session_state.view_doc_id = src.id
                    st.rerun()

            if st.session_state.get("view_doc_id") == rcpt.document_id:
                _show_doc_preview(rcpt.document_id)


def _show_doc_preview(doc_id: int):
    preview_dir = PREVIEWS_DIR / str(doc_id)
    if preview_dir.exists():
        images = sorted(preview_dir.glob("*.png"))
        if images:
            for img_path in images:
                st.image(str(img_path), use_container_width=True)
        else:
            st.info("No preview available.")
    else:
        st.info("Preview not available.")
