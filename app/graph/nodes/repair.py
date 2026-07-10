import logging

from langchain_core.messages import HumanMessage

from app.graph.state import DocState
from app.llm import get_llm, content_block_for_file
from app.schemas.invoice import InvoicePayload
from app.schemas.receipt import ReceiptPayload

logger = logging.getLogger(__name__)

REPAIR_PROMPT = """You are a data extraction specialist. The previous extraction had validation errors.
Re-examine the document and fix the following errors:

{errors}

Return a corrected result matching the required schema. Pay close attention to the math — line item
totals, subtotal, tax, and total must be consistent."""


def repair_extract(state: DocState) -> DocState:
    logger.info("Repairing extraction for document %s", state["document_id"])

    doc_type = state["doc_type"]
    schema = InvoicePayload if doc_type == "invoice" else ReceiptPayload
    llm = get_llm().with_structured_output(schema)

    errors_text = "\n".join(f"- {e}" for e in state["validation_errors"])
    prompt = REPAIR_PROMPT.format(errors=errors_text)

    doc_block = content_block_for_file(state["file_path"], state["mime"])

    msg = HumanMessage(
        content=[{"type": "text", "text": prompt}, doc_block]
    )

    try:
        payload = llm.invoke([msg])
        state["payload"] = payload.to_dict()
        state["llm_calls"] += 1
        state["repair_attempted"] = True
        logger.info("Repair extraction successful")
    except Exception as e:
        logger.warning("Repair extraction failed: %s", e)
        state["llm_calls"] += 1
        state["repair_attempted"] = True
        new_errors = state["validation_errors"] + [f"Repair failed: {str(e)}"]
        state["validation_errors"] = new_errors

    return state
