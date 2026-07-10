from unittest.mock import patch, MagicMock

from app.graph.state import DocState
from app.graph.nodes.queue import queue_for_review, queue_failed


def _state(**kw) -> DocState:
    base: DocState = {
        "document_id": 1,
        "file_path": "/tmp/test.pdf",
        "mime": "application/pdf",
        "doc_type": "invoice",
        "confidence": 0.95,
        "payload": {"vendor": "Test"},
        "validation_errors": [],
        "repair_attempted": False,
        "final_status": None,
        "llm_calls": 2,
    }
    base.update(kw)
    return base


@patch("app.graph.nodes.queue.get_session")
def test_queue_for_review_sets_status(mock_get_session):
    mock_session = MagicMock()
    mock_get_session.return_value = mock_session

    state = _state()
    result = queue_for_review(state)
    assert result["final_status"] == "needs_review"


@patch("app.graph.nodes.queue.get_session")
def test_queue_failed_sets_status(mock_get_session):
    mock_session = MagicMock()
    mock_get_session.return_value = mock_session

    state = _state(validation_errors=["Totals don't match"])
    result = queue_failed(state)
    assert result["final_status"] == "failed_validation"
