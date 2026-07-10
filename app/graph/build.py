from typing import Literal

from langgraph.graph import StateGraph, END

from app.graph.state import DocState
from app.graph.nodes.classify import classify_node
from app.graph.nodes.extract import extract_node
from app.graph.nodes.validate import validate_node
from app.graph.nodes.unsupported import mark_unsupported
from app.graph.nodes.queue import queue_for_review, queue_failed
from app.graph.nodes.repair import repair_extract


def _is_supported(state: DocState) -> Literal["supported", "unsupported"]:
    if state["doc_type"] in ("invoice", "receipt"):
        return "supported"
    return "unsupported"


def _route_from_validate(state: DocState) -> Literal["queue_for_review", "repair_extract", "queue_failed"]:
    if not state["validation_errors"]:
        return "queue_for_review"
    if state["repair_attempted"]:
        return "queue_failed"
    return "repair_extract"


def build_graph() -> StateGraph:
    builder = StateGraph(DocState)

    builder.add_node("load_doc", _stub_load_doc)
    builder.add_node("classify", classify_node)
    builder.add_node("extract", extract_node)
    builder.add_node("validate", validate_node)
    builder.add_node("mark_unsupported", mark_unsupported)
    builder.add_node("repair_extract", repair_extract)
    builder.add_node("queue_for_review", queue_for_review)
    builder.add_node("queue_failed", queue_failed)

    builder.set_entry_point("load_doc")
    builder.add_edge("load_doc", "classify")

    builder.add_conditional_edges("classify", _is_supported, {
        "supported": "extract",
        "unsupported": "mark_unsupported",
    })

    builder.add_edge("extract", "validate")

    builder.add_conditional_edges("validate", _route_from_validate, {
        "queue_for_review": "queue_for_review",
        "repair_extract": "repair_extract",
        "queue_failed": "queue_failed",
    })

    builder.add_edge("repair_extract", "validate")

    builder.add_edge("mark_unsupported", END)
    builder.add_edge("queue_for_review", END)
    builder.add_edge("queue_failed", END)

    return builder.compile()


def _stub_load_doc(state: DocState) -> DocState:
    return state
