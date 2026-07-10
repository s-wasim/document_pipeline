from unittest.mock import patch, MagicMock

from app.graph.state import DocState
from app.graph.nodes.classify import classify_node


def _state(**kw) -> DocState:
    base: DocState = {
        "document_id": 1,
        "file_path": "/tmp/test.pdf",
        "mime": "application/pdf",
        "doc_type": None,
        "confidence": None,
        "payload": None,
        "validation_errors": [],
        "repair_attempted": False,
        "final_status": None,
        "llm_calls": 0,
    }
    base.update(kw)
    return base


@patch("app.graph.nodes.classify.get_llm")
@patch("app.graph.nodes.classify.make_page_preview_block")
def test_classify_invoice(mock_preview, mock_get_llm):
    mock_preview.return_value = {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "fake"}}
    mock_llm = MagicMock()
    mock_llm.invoke.return_value.content = (
        '{"doc_type": "invoice", "confidence": 0.95, "reasoning": "Has invoice header"}'
    )
    mock_get_llm.return_value = mock_llm

    state = _state()
    result = classify_node(state)

    assert result["doc_type"] == "invoice"
    assert result["confidence"] == 0.95
    assert result["llm_calls"] == 1


@patch("app.graph.nodes.classify.get_llm")
@patch("app.graph.nodes.classify.make_page_preview_block")
def test_classify_unsupported(mock_preview, mock_get_llm):
    mock_preview.return_value = {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "fake"}}
    mock_llm = MagicMock()
    mock_llm.invoke.return_value.content = (
        '{"doc_type": "purchase_order", "confidence": 0.88, "reasoning": "Has PO header"}'
    )
    mock_get_llm.return_value = mock_llm

    state = _state()
    result = classify_node(state)

    assert result["doc_type"] == "purchase_order"
    assert result["llm_calls"] == 1


@patch("app.graph.nodes.classify.get_llm")
@patch("app.graph.nodes.classify.make_page_preview_block")
def test_classify_bad_json_falls_back(mock_preview, mock_get_llm):
    mock_preview.return_value = {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "fake"}}
    mock_llm = MagicMock()
    mock_llm.invoke.return_value.content = "not json at all"
    mock_get_llm.return_value = mock_llm

    state = _state()
    result = classify_node(state)

    assert result["doc_type"] == "other"
    assert result["llm_calls"] == 1
