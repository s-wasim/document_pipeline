import logging

from app.graph.state import DocState
from app.db import get_session, Document

logger = logging.getLogger(__name__)


def mark_unsupported(state: DocState) -> DocState:
    logger.info("Marking document %s as unsupported", state["document_id"])
    state["final_status"] = "unsupported"

    session = get_session()
    try:
        doc = session.query(Document).filter(Document.id == state["document_id"]).first()
        if doc:
            doc.status = "unsupported"
            doc.doc_type = state["doc_type"]
            doc.llm_calls = state["llm_calls"]
            doc.note = f"Document classified as '{state['doc_type']}' — unsupported type. Only invoices and receipts are supported."
            session.commit()
    except Exception as e:
        session.rollback()
        logger.warning("Failed to mark unsupported: %s", e)
    finally:
        session.close()

    return state
