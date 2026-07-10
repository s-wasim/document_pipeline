import logging
from typing import Any, Iterator

from app.graph.build import build_graph
from app.graph.state import DocState
from app.db import get_session, Document

logger = logging.getLogger(__name__)


def stream_pipeline(document_id: int) -> Iterator[dict[str, Any]]:
    """Run the graph, yielding one event dict per completed node so callers
    (the Upload tab) can render a live trace as the pipeline actually runs,
    then a final {"final": True, ...} summary event."""
    session = get_session()
    try:
        doc = session.query(Document).filter(Document.id == document_id).first()
        if not doc:
            yield {"error": f"Document {document_id} not found", "final": True, "success": False}
            return
    finally:
        session.close()

    initial: DocState = {
        "document_id": document_id,
        "file_path": doc.path,
        "mime": doc.mime,
        "doc_type": None,
        "confidence": None,
        "payload": None,
        "validation_errors": [],
        "repair_attempted": False,
        "final_status": None,
        "llm_calls": 0,
    }

    graph = build_graph()
    events = []
    final_state = None

    try:
        for event in graph.stream(initial):
            summary = _summarize_event(event)
            events.append(summary)
            for node_name, state in event.items():
                final_state = state
            yield {"final": False, "event": summary}

        if final_state:
            _update_document_status(final_state)

        yield {
            "final": True,
            "success": True,
            "document_id": document_id,
            "final_status": final_state.get("final_status") if final_state else None,
            "llm_calls": final_state.get("llm_calls") if final_state else 0,
            "events": events,
            "validation_errors": final_state.get("validation_errors") if final_state else [],
        }
    except Exception as e:
        logger.exception("Pipeline failed for document %d", document_id)
        _mark_failed(document_id, str(e))
        yield {
            "final": True,
            "success": False,
            "document_id": document_id,
            "error": str(e),
            "events": events,
        }


def run_pipeline(document_id: int) -> dict[str, Any]:
    """Run the graph to completion and return the final summary (no live trace)."""
    result = None
    for event in stream_pipeline(document_id):
        if event.get("final"):
            result = event
    return result


def _summarize_event(event: dict) -> dict:
    summaries = {}
    for node_name, state in event.items():
        summaries[node_name] = {
            "doc_type": state.get("doc_type"),
            "llm_calls": state.get("llm_calls"),
            "validation_errors": len(state.get("validation_errors", [])),
            "repair_attempted": state.get("repair_attempted"),
        }
    return summaries


def _update_document_status(state: DocState):
    session = get_session()
    try:
        doc = session.query(Document).filter(Document.id == state["document_id"]).first()
        if doc and state.get("final_status"):
            doc.status = state["final_status"]
            doc.llm_calls = state["llm_calls"]
            session.commit()
    except Exception as e:
        session.rollback()
        logger.warning("Failed to update document status: %s", e)
    finally:
        session.close()


def _mark_failed(document_id: int, error: str):
    session = get_session()
    try:
        doc = session.query(Document).filter(Document.id == document_id).first()
        if doc:
            doc.status = "failed_validation"
            doc.note = f"Pipeline error: {error}"
            session.commit()
    except Exception as e:
        session.rollback()
        logger.warning("Failed to mark document failed: %s", e)
    finally:
        session.close()
