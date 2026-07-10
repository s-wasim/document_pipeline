import os
from pathlib import Path

import streamlit as st

from app.upload import validate_upload, save_document
from app.db import get_session, Document
from app.graph.runner import stream_pipeline

SAMPLES_DIR = Path(__file__).parent.parent.parent / "samples"


def render():
    st.header("Upload Document")

    uploaded_file = st.file_uploader(
        "Choose a PDF or image",
        type=["pdf", "png", "jpg", "jpeg"],
        key="file_uploader",
    )

    if uploaded_file is not None:
        content = uploaded_file.getvalue()
        err = validate_upload(uploaded_file.name, content)
        if err:
            st.error(err)
        else:
            with st.spinner("Saving document..."):
                doc_id = save_document(uploaded_file.name, content)
            st.success(f"Document saved (ID: {doc_id})")
            if st.button("Run Pipeline", key="run_uploaded"):
                _run_and_show(doc_id)

    st.divider()
    st.subheader("Quick-load Samples")

    samples = [
        ("invoice_clean.pdf", "Invoice (Clean)"),
        ("receipt.jpg", "Receipt"),
        ("invoice_broken_totals.pdf", "Invoice (Broken Totals)"),
        ("purchase_order.pdf", "Purchase Order"),
    ]

    cols = st.columns(len(samples))
    for col, (filename, label) in zip(cols, samples):
        with col:
            filepath = SAMPLES_DIR / filename
            if filepath.exists():
                if st.button(label, use_container_width=True, key=f"sample_{filename}"):
                    content = filepath.read_bytes()
                    err = validate_upload(filename, content)
                    if err:
                        st.error(err)
                    else:
                        doc_id = save_document(filename, content)
                        _run_and_show(doc_id)
            else:
                st.button(label, disabled=True, use_container_width=True)


def _run_and_show(doc_id: int):
    st.session_state.last_doc_id = doc_id
    st.session_state.pipeline_running = True
    st.rerun()


if st.session_state.get("pipeline_running"):
    doc_id = st.session_state.last_doc_id
    st.divider()
    st.subheader("Pipeline Trace")

    status_placeholder = st.status("Running pipeline...", expanded=True)

    result = None
    with status_placeholder:
        st.write("Starting...")
        for update in stream_pipeline(doc_id):
            if update.get("final"):
                result = update
                break
            for node_name, info in update["event"].items():
                st.write(f"**{node_name}**")
                st.json(info)

    if result.get("success"):
        status_placeholder.update(label="Pipeline complete", state="complete")
        st.success(f"Status: **{result['final_status']}**")
    else:
        status_placeholder.update(label="Pipeline failed", state="error")
        st.error(f"Error: {result.get('error')}")

    st.metric("LLM Calls", result.get("llm_calls", 0))

    if result.get("validation_errors"):
        with st.expander("Validation Errors", expanded=True):
            for err in result["validation_errors"]:
                st.error(err)

    st.session_state.pipeline_running = False
