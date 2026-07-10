import logging

from app.graph.state import DocState
from app.db import get_session, Document, Extraction

logger = logging.getLogger(__name__)


def _persist_extraction(state: DocState, status: str):
    session = get_session()
    try:
        doc = session.query(Document).filter(Document.id == state["document_id"]).first()
        if doc:
            doc.status = status
            doc.doc_type = state["doc_type"]
            doc.llm_calls = state["llm_calls"]

            if state["validation_errors"]:
                doc.note = "; ".join(state["validation_errors"][:3])

            extraction = Extraction(
                document_id=state["document_id"],
                payload=state["payload"],
                validation_errors=state["validation_errors"],
                repair_attempted=state["repair_attempted"],
            )
            session.add(extraction)
            session.commit()
    except Exception as e:
        session.rollback()
        logger.warning("Failed to persist extraction: %s", e)
    finally:
        session.close()


def queue_for_review(state: DocState) -> DocState:
    logger.info("Queueing document %s for review", state["document_id"])
    state["final_status"] = "needs_review"
    _persist_extraction(state, "needs_review")
    return state


def queue_failed(state: DocState) -> DocState:
    logger.info("Queueing document %s as failed validation", state["document_id"])
    state["final_status"] = "failed_validation"
    _persist_extraction(state, "failed_validation")
    return state
