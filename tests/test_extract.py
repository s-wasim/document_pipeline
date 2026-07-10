from unittest.mock import patch, MagicMock

from app.graph.state import DocState
from app.graph.nodes.extract import extract_node
from app.schemas.invoice import InvoicePayload
from app.schemas.receipt import ReceiptPayload


def _state(**kw) -> DocState:
    base: DocState = {
        "document_id": 1,
        "file_path": "/tmp/test.pdf",
        "mime": "application/pdf",
        "doc_type": "invoice",
        "confidence": 0.95,
        "payload": None,
        "validation_errors": [],
        "repair_attempted": False,
        "final_status": None,
        "llm_calls": 0,
    }
    base.update(kw)
    return base


INVOICE_PAYLOAD = InvoicePayload.from_dict({
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

RECEIPT_PAYLOAD = ReceiptPayload.from_dict({
    "merchant": "Quick Mart",
    "purchase_date": "2026-07-08",
    "currency": "USD",
    "total": "46.38",
    "payment_method": "Visa",
})


def _mock_llm(structured_response):
    mock_structured = MagicMock()
    mock_structured.invoke.return_value = structured_response
    mock_llm = MagicMock()
    mock_llm.with_structured_output.return_value = mock_structured
    return mock_llm, mock_structured


@patch("app.graph.nodes.extract.get_llm")
@patch("app.graph.nodes.extract.content_block_for_file")
def test_extract_invoice(mock_content_block, mock_get_llm):
    mock_content_block.return_value = {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": "fake"}}
    mock_llm, _ = _mock_llm(INVOICE_PAYLOAD)
    mock_get_llm.return_value = mock_llm

    state = _state()
    result = extract_node(state)

    mock_llm.with_structured_output.assert_called_once_with(InvoicePayload)
    assert result["llm_calls"] == 1
    assert result["payload"] is not None
    assert result["payload"]["vendor"] == "Test Corp"
    assert result["payload"]["invoice_no"] == "INV-001"


@patch("app.graph.nodes.extract.get_llm")
@patch("app.graph.nodes.extract.content_block_for_file")
def test_extract_receipt_uses_image_content_block(mock_content_block, mock_get_llm):
    mock_content_block.return_value = {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": "fake"}}
    mock_llm, mock_structured = _mock_llm(RECEIPT_PAYLOAD)
    mock_get_llm.return_value = mock_llm

    state = _state(doc_type="receipt", mime="image/jpeg", file_path="/tmp/receipt.jpg")
    result = extract_node(state)

    mock_content_block.assert_called_once_with("/tmp/receipt.jpg", "image/jpeg")
    mock_llm.with_structured_output.assert_called_once_with(ReceiptPayload)
    sent_message = mock_structured.invoke.call_args[0][0][0]
    assert sent_message.content[1] == mock_content_block.return_value
    assert result["payload"]["merchant"] == "Quick Mart"
    assert result["llm_calls"] == 1


@patch("app.graph.nodes.extract.get_llm")
@patch("app.graph.nodes.extract.content_block_for_file")
def test_extract_sets_errors_on_failure(mock_content_block, mock_get_llm):
    mock_content_block.return_value = {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": "fake"}}
    mock_llm = MagicMock()
    mock_llm.with_structured_output.return_value.invoke.side_effect = Exception("API error")
    mock_get_llm.return_value = mock_llm

    state = _state()
    result = extract_node(state)

    assert result["llm_calls"] == 1
    assert result["payload"] is None
    assert len(result["validation_errors"]) > 0
