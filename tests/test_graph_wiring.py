from app.graph.state import DocState
from app.graph.build import _is_supported, _route_from_validate, build_graph


def _make_state(**overrides) -> DocState:
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
    base.update(overrides)
    return base


def test_is_supported_invoice():
    state = _make_state(doc_type="invoice")
    assert _is_supported(state) == "supported"


def test_is_supported_receipt():
    state = _make_state(doc_type="receipt")
    assert _is_supported(state) == "supported"


def test_is_unsupported_po():
    state = _make_state(doc_type="purchase_order")
    assert _is_supported(state) == "unsupported"


def test_is_unsupported_other():
    state = _make_state(doc_type="other")
    assert _is_supported(state) == "unsupported"


def test_route_valid_to_review():
    state = _make_state(validation_errors=[])
    assert _route_from_validate(state) == "queue_for_review"


def test_route_invalid_not_repaired():
    state = _make_state(validation_errors=["Totals don't match"], repair_attempted=False)
    assert _route_from_validate(state) == "repair_extract"


def test_route_invalid_already_repaired():
    state = _make_state(validation_errors=["Still wrong"], repair_attempted=True)
    assert _route_from_validate(state) == "queue_failed"


def test_graph_builds():
    graph = build_graph()
    assert graph is not None
    # Verify entry point and node count
    nodes = list(graph.nodes.keys())
    assert "load_doc" in nodes
    assert "classify" in nodes
    assert "extract" in nodes
    assert "validate" in nodes
    assert "mark_unsupported" in nodes
    assert "repair_extract" in nodes
    assert "queue_for_review" in nodes
    assert "queue_failed" in nodes
