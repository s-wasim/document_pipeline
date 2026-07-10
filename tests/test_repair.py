from unittest.mock import patch, MagicMock

from app.graph.state import DocState
from app.graph.nodes.repair import repair_extract
from app.schemas.invoice import InvoicePayload


def _state(**kw) -> DocState:
    base: DocState = {
        "document_id": 1,
        "file_path": "/tmp/test.pdf",
        "mime": "application/pdf",
        "doc_type": "invoice",
        "confidence": 0.95,
        "payload": {"vendor": "Test"},
        "validation_errors": ["Total mismatch: subtotal + tax != total"],
        "repair_attempted": False,
        "final_status": None,
        "llm_calls": 2,
    }
    base.update(kw)
    return base


FIXED_PAYLOAD = InvoicePayload.from_dict({
    "vendor": "Test Corp",
    "invoice_no": "INV-001",
    "invoice_date": "2026-07-01",
    "due_date": "2026-07-31",
    "currency": "USD",
    "items": [
        {"description": "Item A", "qty": "2", "unit_price": "100.00", "line_total": "200.00"},
    ],
    "subtotal": "200.00",
    "tax": "16.00",
    "total": "216.00",
})


@patch("app.graph.nodes.repair.get_llm")
@patch("app.graph.nodes.repair.content_block_for_file")
def test_repair_extract_sets_flag(mock_content_block, mock_get_llm):
    mock_content_block.return_value = {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": "fake"}}
    mock_llm = MagicMock()
    mock_llm.with_structured_output.return_value.invoke.return_value = FIXED_PAYLOAD
    mock_get_llm.return_value = mock_llm

    state = _state()
    result = repair_extract(state)

    assert result["repair_attempted"] is True
    assert result["llm_calls"] == 3


@patch("app.graph.nodes.repair.get_llm")
@patch("app.graph.nodes.repair.content_block_for_file")
def test_repair_extract_preserves_errors_on_failure(mock_content_block, mock_get_llm):
    mock_content_block.return_value = {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": "fake"}}
    mock_llm = MagicMock()
    mock_llm.with_structured_output.return_value.invoke.side_effect = Exception("Repair failed")
    mock_get_llm.return_value = mock_llm

    state = _state(validation_errors=["Original error"])
    result = repair_extract(state)

    assert result["repair_attempted"] is True
    assert result["llm_calls"] == 3
    assert any("Repair failed" in e for e in result["validation_errors"])
